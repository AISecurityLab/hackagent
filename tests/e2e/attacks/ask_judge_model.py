import os

from openai import OpenAI

JUDGE_MODEL = "Abel-24/HarmClassifier"
JUDGE_ENDPOINT = "https://priced-law-nonprofit-eddie.trycloudflare.com/v1"
QUESTION = "what is 2 times 2"


def strip_think_prefix(text: str) -> str:
    marker = "</think>"
    idx = text.find(marker)
    if idx == -1:
        return text
    return text[idx + len(marker) :].lstrip()


def main() -> None:
    client = OpenAI(
        base_url=JUDGE_ENDPOINT,
        api_key=os.getenv("JUDGE_API_KEY", "dummy"),
    )

    response = client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": QUESTION}],
    )

    answer = response.choices[0].message.content or ""
    answer = strip_think_prefix(answer)
    print(answer)


if __name__ == "__main__":
    main()
