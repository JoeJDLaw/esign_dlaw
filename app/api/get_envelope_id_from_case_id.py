# File: apps/esign/app/api/get_envelope_id_from_signing_url.py
import os
import time
import jwt
import requests
from simple_salesforce import Salesforce
import argparse

from dotenv import load_dotenv
load_dotenv("/srv/shared/.env")

def get_salesforce_token():
    client_id = os.environ["SALESFORCE_CLIENT_ID"]
    username = os.environ["SALESFORCE_USERNAME"]
    login_url = os.environ.get("SALESFORCE_LOGIN_URL", "https://login.salesforce.com")
    private_key_path = os.environ["SALESFORCE_JWT_PRIVATE_KEY_PATH"]

    with open(private_key_path, "r") as f:
        private_key = f.read()

    payload = {
        "iss": client_id,
        "sub": username,
        "aud": login_url,
        "exp": int(time.time()) + 300,
    }

    assertion = jwt.encode(payload, private_key, algorithm="RS256")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    response = requests.post(
        f"{login_url}/services/oauth2/token",
        headers=headers,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion
        }
    )
    response.raise_for_status()
    return response.json()

def find_envelope_by_signing_url(signing_url):
    token_data = get_salesforce_token()
    sf = Salesforce(instance_url=token_data["instance_url"], session_id=token_data["access_token"])
    
    query = f"SELECT Id, Name, Signing_Url__c FROM Envelope_Document__c WHERE Signing_Url__c = '{signing_url}'"
    result = sf.query(query)
    
    records = result.get("records", [])
    if not records:
        print("No Envelope Document found for signing URL:", signing_url)
    else:
        for r in records:
            print("Found Envelope Document:")
            print(f"  Id: {r['Id']}")
            print(f"  Name: {r.get('Name')}")
            print(f"  Signing URL: {r['Signing_Url__c']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find Envelope Document by Signing URL")
    parser.add_argument("--signing_url", type=str, required=True, help="Signing URL to query")
    args = parser.parse_args()
    find_envelope_by_signing_url(args.signing_url)