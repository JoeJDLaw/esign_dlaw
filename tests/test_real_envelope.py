# File: tests/test_real_envelope.py
# Test script for the specific Envelope Document record a44Hs000005lVCOIA2

from dotenv import load_dotenv
load_dotenv()

import hmac
import hashlib
import time
import os

# Real data from the Envelope Document record a44Hs000005lVCOIA2
REAL_DATA = {
    "template_type": "cea_rra",
    "client_name": "J Test",
    "client_email": "sam.s@d.law", 
    "salesforce_case_id": "00002673",  # From the Objective field
    "envelope_document_id": "a44Hs000005lVCOIA2"
}

SF_SECRET_KEY = os.environ["SF_SECRET_KEY"].encode()

timestamp = str(int(time.time()))
body = f'{{"template_type":"{REAL_DATA["template_type"]}","client_name":"{REAL_DATA["client_name"]}","client_email":"{REAL_DATA["client_email"]}","salesforce_case_id":"{REAL_DATA["salesforce_case_id"]}","envelope_document_id":"{REAL_DATA["envelope_document_id"]}"}}'

message = f"{timestamp}{body}".encode()
signature = hmac.new(SF_SECRET_KEY, message, hashlib.sha256).hexdigest()

print("=== Testing Real Envelope Document ===")
print(f"Envelope ID: {REAL_DATA['envelope_document_id']}")
print(f"Client: {REAL_DATA['client_name']} ({REAL_DATA['client_email']})")
print(f"Salesforce Case: {REAL_DATA['salesforce_case_id']}")
print()
print("curl -X POST https://esign.dlaw.app/api/v1/initiate \\")
print(f"  -H \"Content-Type: application/json\" \\")
print(f"  -H \"X-Timestamp: {timestamp}\" \\")
print(f"  -H \"X-Signature: {signature}\" \\")
print(f"  -d '{body}'") 