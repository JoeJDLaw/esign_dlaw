import requests
from app.integrations.salesforce.token import get_salesforce_access_token

def update_envelope_record(record_id, updates):
    """
    Updates a custom Envelope__c record in Salesforce using the REST API.

    :param record_id: str, Salesforce ID of the Envelope__c record (e.g., "a01HS0000001abc")
    :param updates: dict, field names and new values to update
    :return: True if successful, raises Exception on failure
    """
    access_token, instance_url = get_salesforce_access_token()

    url = f"{instance_url}/services/data/v59.0/sobjects/Envelope__c/{record_id}"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = requests.patch(url, json=updates, headers=headers)

    if response.status_code == 204:
        print(f"✅ Envelope {record_id} updated successfully.")
        return True
    else:
        raise Exception(f"Failed to update envelope {record_id}: {response.status_code} {response.text}")