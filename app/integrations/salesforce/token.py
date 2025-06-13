import os
import time
import jwt
import requests

def get_salesforce_access_token():
    client_id = os.getenv("SALESFORCE_CLIENT_ID")
    username = os.getenv("SALESFORCE_USERNAME")
    login_url = os.getenv("SALESFORCE_LOGIN_URL", "https://login.salesforce.com")
    key_path = os.getenv("SALESFORCE_JWT_PRIVATE_KEY_PATH")

    issued_at = int(time.time())
    expiration = issued_at + 300

    with open(key_path, "r") as key_file:
        private_key = key_file.read()

    payload = {
        "iss": client_id,
        "sub": username,
        "aud": login_url,
        "exp": expiration
    }

    assertion = jwt.encode(payload, private_key, algorithm="RS256")

    response = requests.post(
        f"{login_url}/services/oauth2/token",
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion
        },
    )

    if response.status_code != 200:
        raise Exception(f"Token request failed: {response.status_code} {response.text}")

    return response.json()["access_token"], response.json()["instance_url"]