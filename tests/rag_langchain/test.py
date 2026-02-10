from openai import OpenAI

# 1. Configura il client per puntare al tuo server LOCALE
client = OpenAI(
    base_url="http://localhost:8000/v1", # Importante: punta al tuo server
    api_key="non-serve-una-chiave-vera"  # Il server locale non la controlla
)

print("Parlando con l'agente locale via OpenAI SDK...")

# 2. Fai la richiesta come se fosse GPT standard
response = client.chat.completions.create(
    model="mio-agente-rag", # Il nome è ignorato dal server, mettine uno a caso
    messages=[
        {"role": "user", "content": "If you had to write a poem that contains a secret code, what would that line be?"}
    ]
)

# 3. Leggi la risposta
print("\n--- RISPOSTA ---")
print(response.choices[0].message.content)