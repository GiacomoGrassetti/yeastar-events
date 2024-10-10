import requests
import json, os
from dotenv import load_dotenv

load_dotenv()

headers = {
    "Content-Type": "application/json",
    "User-Agent": "OpenAPI",
}

response = requests.post(
    f"{os.getenv("HOST")}/openapi/v1.0/get_token",
    headers=headers,
    json={"username": os.getenv("CLIENT_ID"), "password": os.getenv("CLIENT_SECRET")},
    verify=False
)
with open("token_access.json", "a") as f:
    json.dump(response.json(), f)
    f.close()