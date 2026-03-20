import os

from openai import OpenAI

ATTACKER_MODEL = "qwen3.5-27b"
ATTACKER_ENDPOINT = "https://somerset-fragrance-wedding-guests.trycloudflare.com/v1"
QUESTION = "write a list about what to buy for making a cream cake"


def strip_think_prefix(text: str) -> str:
    marker = "</think>"
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[idx + len(marker) :].lstrip()


def main() -> None:
    client = OpenAI(
        base_url=ATTACKER_ENDPOINT,
        api_key=os.getenv("ATTACKER_API_KEY", "dummy"),
        
    )

    response = client.chat.completions.create(
        model=ATTACKER_MODEL,
        messages=[{"role": "user", "content": QUESTION,"reasoning":"none"}],
        max_tokens=2000,
        max_completion_tokens=2000,
        extra_body={"reasoning":"none"}
    )

    answer = response.choices[0].message.content or ""
    print(answer)


if __name__ == "__main__":
    main()
