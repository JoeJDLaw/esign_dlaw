# File: apps/esign/app/api/update_envelope_document.py
import os
import jwt
import time
import requests
from simple_salesforce import Salesforce
from dotenv import load_dotenv
import logging

load_dotenv("/srv/shared/.env")

logger = logging.getLogger(__name__)

def get_salesforce_token():
    try:
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
            data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to obtain Salesforce token: {e}")

def should_send_webhook() -> bool:
    """Check if webhooks should be sent (respects DISABLE_WEBHOOKS setting)."""
    return os.environ.get("DISABLE_WEBHOOKS", "").lower() != "true"

def send_webhook_if_enabled(message: str):
    """Send webhook notification if webhooks are enabled."""
    if not should_send_webhook():
        logger.info(f"Webhook disabled - would have sent: {message}")
        return
        
    try:
        webhook_url = os.environ.get("RC_WEBHOOK_URL")
        if webhook_url:
            import requests
            response = requests.post(webhook_url, json={"text": message}, timeout=5)
            logger.info(f"Webhook sent: {response.status_code}")
    except Exception as e:
        logger.error(f"Failed to send webhook: {e}")

def update_envelope_document(updates: dict, record_id: str, max_attempts: int = 3):
    if not record_id:
        raise RuntimeError("No Envelope Document ID provided for update.")

    token_data = get_salesforce_token()
    sf = Salesforce(instance_url=token_data["instance_url"], session_id=token_data["access_token"])

    for attempt in range(1, max_attempts + 1):
        try:
            sf.Envelope_Document__c.update(record_id, updates)
            return
        except Exception as e:
            error_msg = f"Salesforce update retry {attempt} failed for Envelope Document {record_id}: {e}"
            logger.warning(error_msg)
            send_webhook_if_enabled(error_msg)
            
            if attempt == max_attempts:
                final_error_msg = f"Salesforce update failed for Envelope Document {record_id} after {max_attempts} attempts."
                logger.error(final_error_msg)
                send_webhook_if_enabled(final_error_msg)
                raise RuntimeError(f"Failed to update Salesforce Envelope Document {record_id}: {e}")
            time.sleep(2 ** (attempt - 1))

def find_envelope_id_by_token(token: str) -> str | None:
    try:
        token_data = get_salesforce_token()
        sf = Salesforce(instance_url=token_data["instance_url"], session_id=token_data["access_token"])

        logger.info(f"Searching for Envelope Document with token: {token}")

        query = f"SELECT Id FROM Envelope_Document__c WHERE Signing_Token__c = '{token}' LIMIT 1"
        logger.info(f"Executing Salesforce query: {query}")
        result = sf.query(query)

        if result.get("records"):
            record_id = result["records"][0]["Id"]
            logger.info(f"Found Envelope Document with ID: {record_id}")
            return record_id

        logger.warning(f"No Envelope Document found for token: {token}")
        return None
    except Exception as e:
        logger.error(f"Failed to query Salesforce for token '{token}': {e}")
        raise RuntimeError(f"Failed to query Salesforce for token '{token}': {e}")