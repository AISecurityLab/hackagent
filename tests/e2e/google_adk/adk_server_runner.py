# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0


import os
import signal
import subprocess
import time
from contextlib import contextmanager

import dotenv

from hackagent.logger import get_logger

dotenv.load_dotenv()

# Configure a logger for this utility module
logger = get_logger(__name__)


@contextmanager
def adk_agent_server(port: int):
    """Starts and stops the 'adk api_server' in a subprocess.

    Args:
        port: The port number on which the ADK server should run.
    """
    server_process = None
    # Use the directory of the current script as the working directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = ["adk", "api_server", f"--port={port}"]
    msg = f"Preparing ADK server in {script_dir} cmd: {' '.join(cmd)}"
    logger.info(msg)

    try:
        logger.info(f"Starting ADK server process on port {port}...")
        server_process = subprocess.Popen(
            cmd,
            cwd=script_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        )

        logger.info(f"Waiting for ADK server on http://localhost:{port}...")
        start_time = time.time()
        server_ready = False
        max_wait_adk = 20  # seconds to wait for ADK server readiness

        while time.time() - start_time < max_wait_adk:
            if server_process.poll() is not None:
                stdout, stderr = server_process.communicate()
                code = server_process.returncode
                err_msg = f"ADK server exited prematurely. Code: {code}.\nStdout: {stdout}\nStderr: {stderr}"
                logger.error(err_msg)
                raise RuntimeError(f"ADK server failed to start. Code: {code}")

            # Simple readiness check
            if time.time() - start_time > 3:  # Min wait time
                try:
                    log_msg = "ADK server process running. Assuming startup."
                    logger.info(log_msg)
                    server_ready = True
                    break
                except Exception:  # pylint: disable=broad-except
                    pass  # Keep waiting
            time.sleep(1)

        if not server_ready:
            if server_process.poll() is None:  # Still running but not "ready"
                err_p1 = f"ADK server http://localhost:{port} not ready"
                err_p2 = f"in {max_wait_adk}s. Terminating."
                logger.error(f"{err_p1} {err_p2}")
                if hasattr(os, "setsid"):
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                else:
                    server_process.terminate()
                server_process.communicate(timeout=5)  # Ensure process is reaped
            server_url = f"http://localhost:{port}"
            err_text = f"ADK server {server_url} failed to start or become ready."
            raise RuntimeError(err_text)

        logger.info(f"ADK server presumed started at http://localhost:{port}")
        yield f"http://localhost:{port}"

    finally:
        if server_process and server_process.poll() is None:
            pid_info = f"(PID: {server_process.pid})"
            stop_msg = f"Stopping ADK server process {pid_info} on port {port}..."
            logger.info(stop_msg)
            try:
                if hasattr(os, "setsid"):
                    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)
                else:
                    server_process.terminate()
                stdout, stderr = server_process.communicate(timeout=10)
                exit_code = server_process.returncode or "N/A"
                logger.info(f"ADK server stopped. Exit code: {exit_code}")
                if stdout or stderr:
                    log_details = f"ADK Server (port {port}) Final Output:\nStdout: {stdout}\nStderr: {stderr}"
                    logger.debug(log_details)
            except ProcessLookupError:
                warn_msg = f"ADK server process (port {port}) already stopped."
                logger.warning(warn_msg)
            except Exception as e:  # pylint: disable=broad-except
                err_stop = f"Error stopping ADK server (port {port}): {e}"
                logger.error(err_stop, exc_info=True)
                if server_process.poll() is None:
                    warn_force_kill = (
                        f"Attempting forceful kill for ADK (port {port})..."
                    )
                    logger.warning(warn_force_kill)
                    server_process.kill()
                    server_process.communicate(timeout=5)  # Ensure reaping
