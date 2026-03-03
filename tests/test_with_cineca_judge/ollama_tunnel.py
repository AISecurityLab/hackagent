import subprocess
import time
import socket
import os
import signal
import sys
import re


class SSHTunnel:
    def __init__(self, node, remote_port=11434, local_port=11434):
        self.process = None
        self.local_host = "127.0.0.1"
        self.local_port = local_port
        self.remote_port = remote_port
        self.node = node

    def start(self):
        """Starts the tunnel. If the port is already in use, it attempts to free it first."""
        if self._is_port_open():
            print(f"Port {self.local_port} is already in use. Attempting to free it...")
            self.stop()
            time.sleep(1)

            if self._is_port_open():
                raise RuntimeError(
                    f"CRITICAL ERROR: Unable to free port {self.local_port}. Administrator/root privileges might be required."
                )

        cmd = [
            "ssh",
            "-N",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "ConnectTimeout=10",
            "-o",
            "BatchMode=yes",
            "-L",
            f"{self.local_host}:{self.local_port}:{self.node}:{self.remote_port}",
            "mrusso05@login.leonardo.cineca.it",
        ]

        print("Starting SSH tunnel...")
        print(" ".join(cmd))
        self.process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        timeout = 15.0
        start_time = time.time()

        while True:
            # Check if the SSH process died prematurely (e.g., auth failed)
            if self.process.poll() is not None:
                _, stderr = self.process.communicate()
                self.process = None
                raise RuntimeError(
                    f"SSH command failed. Error details:\n{stderr.strip()}"
                )

            # Check if the port is successfully opened and listening
            if self._is_port_open():
                print("SSH tunnel established successfully!")
                break

            # Check for timeout
            if time.time() - start_time > timeout:
                self.stop()
                raise RuntimeError(
                    "Timeout: SSH is taking too long to establish the connection."
                )

            time.sleep(0.5)

    def stop(self):
        """Closes the current tunnel and kills any external process occupying the port."""
        # Case 1: Graceful shutdown for the process started by this script instance
        if self.process:
            print("Closing the internal SSH process...")
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

        # Case 2: Cross-platform search and destroy for external/orphaned processes
        elif self._is_port_open():
            print(f"Searching for orphaned processes on port {self.local_port}...")
            pids = self._get_pids_on_port()

            if not pids:
                print(
                    "The port is in use, but I cannot find the process. (Insufficient permissions?)"
                )
            else:
                for pid in pids:
                    print(f"Found intruding process (PID: {pid}). Terminating...")
                    self._kill_process(pid)

                time.sleep(1.5)  # Wait for the OS to release the socket

                if self._is_port_open():
                    print("WARNING: Unable to free the port. The process is resisting.")
                else:
                    print("Port freed successfully!")
        else:
            print("No tunnel to close, the port is already free.")

    def _get_pids_on_port(self):
        """Finds the PIDs of processes listening on the target port (cross-platform)."""
        pids = set()
        port_str = str(self.local_port)

        if sys.platform == "win32":
            # --- WINDOWS ---
            try:
                result = subprocess.run(
                    ["netstat", "-ano"], capture_output=True, text=True
                )
                for line in result.stdout.splitlines():
                    if f":{port_str}" in line and "LISTENING" in line.upper():
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            pids.add(int(parts[-1]))
            except Exception as e:
                print(f"Netstat error on Windows: {e}")

        else:
            # --- LINUX / macOS ---
            # Attempt 1: lsof (Standard on macOS, common on Linux)
            try:
                result = subprocess.run(
                    ["lsof", "-t", f"-i:{port_str}"], capture_output=True, text=True
                )
                if result.stdout.strip():
                    return [int(p) for p in result.stdout.strip().split("\n")]
            except FileNotFoundError:
                pass

            # Attempt 2: ss (Modern standard on Linux distributions)
            try:
                result = subprocess.run(["ss", "-lptn"], capture_output=True, text=True)
                for line in result.stdout.splitlines():
                    if f":{port_str}" in line:
                        # Extracts PIDs from the format users:(("ssh",pid=1234,fd=3))
                        matches = re.findall(r"pid=(\d+)", line)
                        for m in matches:
                            pids.add(int(m))
            except FileNotFoundError:
                pass

        return list(pids)

    def _kill_process(self, pid):
        """Kills a process based on the operating system."""
        try:
            if sys.platform == "win32":
                # On Windows, use taskkill to force close
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F"], capture_output=True
                )
            else:
                # On Linux/macOS, use standard signals
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                try:
                    # os.kill with signal 0 only checks if the process still exists
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)  # Coup de grâce
                except OSError:
                    pass  # If OSError is raised here, the process is already dead
        except PermissionError:
            print(
                f"Permission denied to kill PID {pid}. Running the script as Administrator/Root might be required."
            )
        except Exception as e:
            print(f"Unable to kill PID {pid}: {e}")

    def _is_port_open(self):
        """Checks if the local port is currently listening/open."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.connect((self.local_host, self.local_port))
                return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                return False
