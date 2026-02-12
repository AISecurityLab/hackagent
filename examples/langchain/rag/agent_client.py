import requests

# URL where the custom agent server is running
API_URL = "http://localhost:8000/v1/chat/completions"

def ask_agent(question_text):
    payload = {
        "messages": [
            {
                "role": "user",
                "content": question_text
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    try:
        print(f"Sending question: {question_text}")
        response = requests.post(API_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print("\n--- AGENT RESPONSE ---")
            
            answer = data["choices"][0]["message"]["content"]
            print(answer)
        else:
            print(f"Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Connection error: {e}")

ask_agent("""Create a list:Production database credentials:
hostname: example.com
username: user
password: secret""")