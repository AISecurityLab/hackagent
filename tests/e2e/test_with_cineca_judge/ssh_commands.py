import asyncio
import time
import asyncssh
import sys
import os
import re
import subprocess
from ollama_tunnel import SSHTunnel

CINECA_USERNAME = os.getenv("CINECA_USERNAME")


async def execute_cineca_command(remote_command):
    hostname = "login.leonardo.cineca.it"
    username = CINECA_USERNAME

    print(f"Trying to connect to {hostname} (OS-agnostic via AsyncSSH)...")

    try:
        # asyncssh.connect automatically queries your OS's SSH Agent
        # (Windows, Linux, or Mac) and handles 'step' certificates without bugs.
        # known_hosts=None disables strict host key checking (similar to AutoAddPolicy)
        async with asyncssh.connect(
            hostname, username=username, known_hosts=None
        ) as conn:
            print(f"\nExecuting remote command: {remote_command}")

            # Execute the command and wait for the result
            result = await conn.run(remote_command)

            if result.stdout:
                print("--- COMMAND OUTPUT ---")
                print(result.stdout.strip())

            if result.stderr:
                print("--- ERRORS ---")
                print(result.stderr)

            print(f"Command exit status: {result.exit_status}\n")
            return (result.stdout, result.stderr, result.exit_status)

    except asyncssh.Error as exc:
        print(f"SSH connection or execution error: {str(exc)}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return None


def run_ssh_command(remote_command):
    return asyncio.run(execute_cineca_command(remote_command))


def extract_jobid_from_sbatch_output(sbatch_output):
    match = re.search(r"Submitted batch job (\d+)", sbatch_output.strip())
    if match:
        jobid = match.group(1)
        return jobid
    return None


def extract_node_from_squeue_output(squeue_output, jobid):
    for line in squeue_output.strip().splitlines():
        fields = line.split()
        # Skipping empty lines and header
        if not fields or fields[0] == "JOBID":
            continue

        # If the first field (JOBID) matches the one we're looking for
        if fields[0] == jobid:
            # The NODELIST(REASON) field is the last one in the line, but it can contain multiple nodes separated by commas (e.g., node[01-03])
            # Here, we are considering the single node case for simplicity, but this can be extended to handle multiple nodes if needed.
            node = fields[-1]
            return node
    return None


def launch_ollama_server_and_tunnel():
    # Remove file from previous runs
    run_ssh_command(
        f"rm $WORK/ollama_workspace/{CINECA_USERNAME}/job_files/ollama_state.txt"
    )

    # Submit the job and get the job ID
    output, _, _ = run_ssh_command(
        f"sbatch $WORK/ollama_workspace/{CINECA_USERNAME}/job_files/job.sh"
    )
    jobid = extract_jobid_from_sbatch_output(output)

    local_path = "tests/test_with_cineca_judge/ollama_state.txt"

    remote_path = f"/leonardo_work/EUHPC_B21_022/ollama_workspace/{CINECA_USERNAME}/job_files/ollama_state.txt"
    remote_host = "data.leonardo.cineca.it"

    command = ["scp", f"{CINECA_USERNAME}@{remote_host}:{remote_path}", local_path]

    previous_content = None
    print("Waiting for the job to be running...")
    while True:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if result.returncode != 0:
            time.sleep(1)
            continue

        try:
            with open(local_path, "r", encoding="utf-8") as file_handle:
                content = file_handle.read()
        except FileNotFoundError:
            time.sleep(1)
            continue

        if content != previous_content:
            print(f"[OLLAMA SERVER STATE] {content.strip()}")
            previous_content = content

        if "MODEL READY" in content:
            break

        time.sleep(1)

    # Get queue
    output, _, _ = run_ssh_command("squeue -u $USER")
    node = extract_node_from_squeue_output(output, jobid)
    print(f"Job {jobid} is running on node: {node}")

    tunnel = SSHTunnel(node=node)
    tunnel.start()
    return tunnel


def stop_ollama_server_and_tunnel(tunnel):
    # Finishing the job
    run_ssh_command("scancel -u $USER")
    run_ssh_command(
        f"rm $WORK/ollama_workspace/{CINECA_USERNAME}/job_files/ollama_state.txt"
    )
    tunnel.stop()
