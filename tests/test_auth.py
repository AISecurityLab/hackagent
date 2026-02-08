import requests

headers = {
    "accept": "application/json",
    "Authorization": "Bearer YNYCDSK-J864527-HNRDP2Q-H0ED8JG",
}

response = requests.get("http://localhost:3001/api/v1/auth", headers=headers)
print(response.status_code)
