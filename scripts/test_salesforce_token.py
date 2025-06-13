# /srv/apps/esign/scripts/test_salesforce_token.py
from dotenv import load_dotenv
load_dotenv(dotenv_path="/srv/shared/.env")
import os
import time
import jwt
import requests

client_id = os.getenv("SALESFORCE_CLIENT_ID")
username = os.getenv("SALESFORCE_USERNAME")
login_url = os.getenv("SALESFORCE_LOGIN_URL", "https://login.salesforce.com")
key_path = os.getenv("SALESFORCE_JWT_PRIVATE_KEY_PATH")

with open(key_path, "r") as key_file:
    private_key = key_file.read()

issued_at = int(time.time())
expiration = issued_at + 300

payload = {
    "iss": client_id,
    "sub": username,
    "aud": login_url,
    "exp": expiration,
}

assertion = jwt.encode(payload, private_key, algorithm="RS256")

response = requests.post(
    f"{login_url}/services/oauth2/token",
    data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    },
)

print("Status:", response.status_code)
print("Response:", response.json())