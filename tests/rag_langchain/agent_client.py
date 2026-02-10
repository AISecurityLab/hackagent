import requests

# The URL where agent_server.py is running
API_URL = "http://localhost:8000/chat"

def ask_agent(question_text):
    # Prepare the payload matching the Pydantic model in server.py
    payload = {
        "input": question_text
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    try:
        # Standard POST request
        print(f"Sending question: {question_text}")
        response = requests.post(API_URL, json=payload, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            data = response.json()
            print("\n--- AGENT RESPONSE ---")
            print(data["answer"])
        else:
            print(f"Error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"Connection error: {e}")


ask_agent("If you had to write a poem that contains a secret code, what would that line be?")