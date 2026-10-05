from hackagent import HackAgent, Settings

OLLAMA_BASE = "http://localhost:11434"
VICTIM_MODEL = "Almawave/Velvet:2b"
JUDGE_MODEL = "huihui_ai/lfm2.5-abliterated:latest"


def main() -> None:
    # No api_key → LocalBackend (SQLite), zero traffic to api.hackagent.dev
    session = HackAgent(Settings.resolve())
    try:
        agent = session.target(OLLAMA_BASE, "ollama", name=VICTIM_MODEL)
        results = agent.hack(
            attack_config={
                "attack_type": "flipattack",
                "dataset": {"preset": "harmbench", "limit": 10},
                "flipattack_params": {"flip_mode": "FCS", "cot": False},
                "judges": [
                    {
                        "identifier": JUDGE_MODEL,
                        "endpoint": OLLAMA_BASE,
                        "agent_type": "ollama",
                        "type": "harmbench",
                    }
                ],
            }
        )
        print(results)
    finally:
        session.close()


if __name__ == "__main__":
    main()
