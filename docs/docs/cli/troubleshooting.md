---
title: "Troubleshooting"
description: "Common hackagent errors, what causes them, and how to fix them."
sidebar_position: 40
---

Find the message you see, then its cause and fix. Messages are shown as the CLI
prints them; `…` stands for the part that varies.

## First steps

```bash
hackagent doctor           # config file, database, backend, API key, dependencies
hackagent config show      # every setting and where it came from
```

For more detail on a failure, run the command again with:

```bash
HACKAGENT_DEBUG=1 HACKAGENT_LOG_LEVEL=DEBUG hackagent …
```

`HACKAGENT_DEBUG` adds the full traceback to an error; `HACKAGENT_LOG_LEVEL`
shows HackAgent's log messages down to that level.

## Settings and API keys

A settings error stops every command, including `hackagent config`, because the
settings are read before the command runs.

| Message | Cause | Fix |
|---|---|---|
| `Configuration Error: HackAgent platform API key: environment variable 'HACKAGENT_API_KEY' is missing or empty.` | The remote backend is selected, in the config file, `HACKAGENT_BACKEND` or `--backend`, and no key is set. | Export `HACKAGENT_API_KEY`. To go back to local storage instead, run `hackagent --backend local config set --backend local`; the `--backend local` before `config` lets the command start. |
| `Configuration Error: HackAgent platform API key: environment variable 'NAME' is missing or empty.` | The config file's `api_key` is `"${NAME}"` and that variable is unset. A reference in the file is always resolved, even on the local backend, and `HACKAGENT_API_KEY` does not replace it. | Export `NAME`, or remove the `api_key` entry to use `HACKAGENT_API_KEY`. |
| `Configuration Error: api_key in configuration files must be a ${VARIABLE} reference.` | The config file holds a key value. | Replace it with a reference such as `"${HACKAGENT_API_KEY}"` and export the key. See [API keys](./configuration.md#api-keys). |
| `Configuration Error: Use api_key with an explicit ${VARIABLE} reference.` | The config file uses `api_key_env`, which is not supported. | Write `"api_key": "${NAME}"` instead. |
| `Configuration Error: Failed to load config file …` | The config file is not valid JSON, or YAML for a `.yaml`/`.yml` file. | Fix the file, or delete it to start over. |
| `Configuration Error: Invalid storage backend 'cloud' from …: expected 'local' or 'remote'` | `backend` in the file, `HACKAGENT_BACKEND` or `--backend` has another value. The message names where it came from. | Use `local` or `remote`. |
| `CA bundle not found: …` | `--ca-bundle`, `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE` or `ca_bundle` names a file that does not exist. | Point it at the PEM file. See [CA bundle](./configuration.md#ca-bundle). |
| `The server's TLS certificate is not trusted. …` | The API's certificate is signed by a CA outside your trust store, often a private CA or a proxy that intercepts TLS. | Configure a [CA bundle](./configuration.md#ca-bundle) that includes that CA. |
| `Configuration valid but API connection issue: Status 401` | The API rejected your key. | Check `HACKAGENT_API_KEY` holds a current key. |
| `Configuration valid but API connection issue: Status 0` | `hackagent config validate` on the local backend, where there is no API to call. | Nothing is wrong. Use `hackagent --backend remote config validate` to test the API. |

## Campaign files

| Message | Cause | Fix |
|---|---|---|
| `Invalid campaign: Campaign file does not exist: campaign.yaml` | No file name was given and there is no `campaign.yaml` here, or the path is wrong. | Pass the file: `hackagent campaign run my-campaign.yaml`. |
| `Invalid campaign: … Unknown attack 'flipatack'. Available: …` | An attack name is misspelled or does not exist. | Use a name from the list, or from `hackagent campaign list`. |
| `Invalid campaign: N validation errors for CampaignSpec` | A field is missing, misspelled or has the wrong type. Each error names the field path, such as `attacks.0`. | Check the field in [Campaign files](./campaign-files/index.md). The [JSON Schema](./running-campaigns.md#find-attacks-and-goals) catches these as you type. |
| `Invalid campaign: API key: environment variable 'NAME' is missing or empty.` | A model's `api_key` is `"${NAME}"` and that variable is unset. `validate` and `run` both build every model, which reads its key. | Export `NAME` in the shell you run from. |
| `… No module named 'datasets'` | The campaign uses a Hugging Face dataset and the `hf` extra is not installed. | `pip install 'hackagent[hf]'`. |

`hackagent campaign validate` does not check the storage key, so a file with
remote storage can validate and still fail to run; see below.

## Running a campaign

| Message | Cause | Fix |
|---|---|---|
| `Error: Missing downloaded Ollama models at http://localhost:11434: llama3.2` | The Ollama server does not list a model with that exact name. Ollama lists names with their tag, so a model pulled as `llama3.2` is listed as `llama3.2:latest`. | Run `ollama list` and use the name exactly as shown, tag included, or `ollama pull` the model. |
| `Error: Missing served OpenAI-compatible models at …: …` | A vLLM server is up but serves another model. | Use the model id the server's `/models` lists, or start the server with that model. |
| `Error: Ollama is not ready at …: <urlopen error [Errno 61] Connection refused>` | No Ollama server answers at that address. | Start Ollama, fix the endpoint, or point every Ollama model elsewhere with `--ollama-endpoint`. If it is still starting, add `--wait-for-ollama 60`. |
| `Error: OpenAI-compatible server is not ready at …` | The same for a vLLM server. | Start it, or add `--wait-for-server 300` while it loads the model. |
| `… exited before becoming ready; inspect server logs` | The process given with `--ollama-pid` or a `--…-server-pid` option stopped. | Read that server's logs. |
| `Error: Invalid value: Ollama and OpenAI-compatible endpoint overrides cannot be combined` | `--ollama-endpoint` was given with `--openai-endpoint`, `--judge-endpoint` or `--attacker-endpoint`. Exits with code 2. | Use one kind per run. |
| `Configuration Error: Remote campaign storage API key: environment variable 'HACKAGENT_API_KEY' is missing or empty.` | The campaign's `execution.storage.backend` is `remote` and no key is set. | Export `HACKAGENT_API_KEY`, or the variable the storage `api_key` names. |
| `This campaign uses the HackAgent gateway; set an API key with: hackagent config set --api-key` | A model in the campaign uses the HackAgent gateway, which needs your platform key. `config set` has no `--api-key` option. | Export `HACKAGENT_API_KEY`. |
| The summary title says `failed` and the exit code is `1` | An attack stopped early (its **Error** column says why), or some attempts failed to generate, reach the target or be judged. `attempt_errors` in the `--json` summary counts those. | Read the **Error** column, then the run's `results.json` and `traces.jsonl` for the failed attempts. |

## Reading results

| Symptom | Cause | Fix |
|---|---|---|
| `hackagent results summary` shows no results, or not the run you expect | The run was recorded in another store. A campaign records where its `execution.storage` says, local by default, while `hackagent results` reads the CLI's backend. Or `HACKAGENT_DB_PATH` differed between the two commands. | Read with the matching backend: `hackagent --backend local results summary` for a local run. Check `hackagent config show` and `HACKAGENT_DB_PATH`. |
| The terminal app or dashboard shows another database | Same cause. | Same fix; `hackagent web --db-path PATH` opens a specific database. |

## The dashboard

| Message | Cause | Fix |
|---|---|---|
| `Web UI dependencies are not installed: …` | The `web` extra is not installed. | `pip install 'hackagent[web]'`. |
| `No web UI bundle found at …` | The dashboard's files are not installed. | `pip install 'hackagent[web]'`, or use a release binary. |
| `Port 7860 is already in use by another process.` | A program other than `hackagent web` holds the port. | `hackagent web --port 8080`, or stop that program. |
| The browser gets `400 Bad Request` | The dashboard was opened by a name it does not answer to, such as the machine's LAN name with `--host 0.0.0.0`. | Open it through `127.0.0.1` or `localhost`, or an SSH tunnel. See [Who can reach it](./dashboard.md#who-can-reach-it). |
| `401` errors in remote mode | The key the dashboard forwards is missing, expired or revoked. | Export a current `HACKAGENT_API_KEY` and restart `hackagent web`. |

## The terminal app

| Message | Cause | Fix |
|---|---|---|
| `TUI dependencies not installed` | The `tui` extra is not installed. | `pip install 'hackagent[tui]'`. |

## Queued runs

`hackagent run` explains each refusal in its message; see
[When it refuses](./run-worker.md#when-it-refuses).
