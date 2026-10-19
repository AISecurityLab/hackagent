#!/usr/bin/env bash
#SBATCH --job-name=hackagent-static
#SBATCH --account=ais_login
#SBATCH --partition=gpuq
#SBATCH --qos=quota_ais_gpuq
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=16
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --signal=B:TERM@60
#SBATCH --output=.logs/%j-hackagent-static.out
#SBATCH --error=.logs/%j-hackagent-static.err

set -Eeuo pipefail

project_dir="${HACKAGENT_DIR:-${SLURM_SUBMIT_DIR:-$PWD}}"
cd "$project_dir"
python="${HACKAGENT_PYTHON:-$project_dir/.venv/bin/python}"
if [[ ! -x "$python" ]]; then
    printf '%s\n' 'Set HACKAGENT_PYTHON to a Python environment containing HackAgent and vLLM.' >&2
    exit 1
fi

export PYTHONPATH="$project_dir${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONUNBUFFERED=1
campaign="${HACKAGENT_CAMPAIGN:-campaign.yaml}"
concurrency="${VLLM_MAX_NUM_SEQS:-16}"
target_port="${VLLM_TARGET_PORT:-$((20000 + ${SLURM_JOB_ID:-0} % 10000 * 3))}"
judge_port="${VLLM_JUDGE_PORT:-$((target_port + 1))}"
attacker_port="${VLLM_ATTACKER_PORT:-$((target_port + 2))}"
target_endpoint="http://127.0.0.1:$target_port/v1"
judge_endpoint="http://127.0.0.1:$judge_port/v1"
attacker_endpoint="http://127.0.0.1:$attacker_port/v1"

model_config="$("$python" - "$campaign" <<'PY'
import importlib.util
import sys
from hackagent.orchestrator.campaign import load_campaign

if importlib.util.find_spec("vllm") is None:
    raise SystemExit("vLLM is not installed in HACKAGENT_PYTHON")
spec = load_campaign(sys.argv[1])
target, judges = spec.target, spec.evaluation.judges
roles = {(model.name, model.connection.endpoint): model for attack in spec.attacks for model in attack.roles.values()}
if len(roles) > 1:
    raise SystemExit("This launcher supports one distinct role model/endpoint; use external servers for additional role models")
role = next(iter(roles.values()), None)
models = [target, *judges, *([role] if role else [])]
if any(model.connection.provider != "vllm" or model.connection.type.value != "OPENAI_SDK" for model in models):
    raise SystemExit("This launcher requires vLLM/OpenAI-compatible model connections")
other_judges = {judge.name for judge in judges if judge.name != target.name}
if len(other_judges) != 1:
    raise SystemExit("This launcher requires exactly one distinct judge model besides the target")
if any((judge.connection.endpoint == target.connection.endpoint) != (judge.name == target.name) for judge in judges):
    raise SystemExit("Judges using the target model must share its endpoint; other judges need a separate endpoint")
if role is not None and role.connection.endpoint in {model.connection.endpoint for model in [target, *judges]}:
    raise SystemExit("This launcher requires a separate endpoint for the role model")
print(target.name)
print(next(iter(other_judges)))
if role is not None:
    print(role.name)
PY
)"
mapfile -t models <<< "$model_config"

output_dir="${HACKAGENT_OUTPUT_DIR:-$project_dir/logs/runs/slurm-${SLURM_JOB_ID:-local}}"
mkdir -p "$output_dir"
pids=()
campaign_pid=""
cleanup() {
    for pid in "$campaign_pid" "${pids[@]}"; do
        if [[ -n "$pid" ]]; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

roles=(target judge)
default_memory=0.45
if [[ ${#models[@]} -eq 3 ]]; then
    roles+=(attacker)
    default_memory=0.30
fi
ports=("$target_port" "$judge_port" "$attacker_port")
endpoints=("$target_endpoint" "$judge_endpoint" "$attacker_endpoint")
weights=("${VLLM_TARGET_MODEL:-${models[0]}}" "${VLLM_JUDGE_MODEL:-${models[1]}}" "${VLLM_ATTACKER_MODEL:-${models[2]:-}}")
memory=("${VLLM_TARGET_GPU_MEMORY_UTILIZATION:-$default_memory}" "${VLLM_JUDGE_GPU_MEMORY_UTILIZATION:-$default_memory}" "${VLLM_ATTACKER_GPU_MEMORY_UTILIZATION:-$default_memory}")
if [[ "$target_port" == "$judge_port" || (${#models[@]} -eq 3 && ("$attacker_port" == "$target_port" || "$attacker_port" == "$judge_port")) ]]; then
    printf '%s\n' 'vLLM server ports must be distinct.' >&2
    exit 1
fi
printf 'Parallel requests: %s\nOutput: %s\n' "$concurrency" "$output_dir"
for index in "${!roles[@]}"; do
    role="${roles[$index]}"
    printf 'vLLM %s: %s (%s)\n' "$role" "${models[$index]}" "${endpoints[$index]}"
    options=(
        --model "${weights[$index]}" --served-model-name "${models[$index]}"
        --host 127.0.0.1 --port "${ports[$index]}" --dtype auto
        --max-model-len "${VLLM_MAX_MODEL_LEN:-8192}" --max-num-seqs "$concurrency"
        --gpu-memory-utilization "${memory[$index]}"
        --generation-config vllm --enable-prefix-caching
    )
    if [[ "$role" == target ]]; then
        options+=(--limit-mm-per-prompt '{"image": 0}')
    fi
    "$python" -m vllm.entrypoints.openai.api_server "${options[@]}" >"$output_dir/$role-vllm.log" 2>&1 &
    pids+=("$!")
    "$python" - "${endpoints[$index]}" "${pids[$index]}" <<'PY'
import sys
from scripts.run_campaign import installed_models
installed_models(sys.argv[1], 600, int(sys.argv[2]), provider="openai")
PY
done
attacker_args=()
if [[ ${#models[@]} -eq 3 ]]; then
    attacker_args=(--attacker-endpoint "$attacker_endpoint" --attacker-server-pid "${pids[2]}")
fi

"$python" -m scripts.run_campaign "$campaign" \
    --openai-endpoint "$target_endpoint" --judge-endpoint "$judge_endpoint" \
    --output-directory "$output_dir" \
    --wait-for-server 600 --server-pid "${pids[0]}" --judge-server-pid "${pids[1]}" \
    "${attacker_args[@]}" \
    --concurrency "$concurrency" &
campaign_pid=$!
wait "$campaign_pid"