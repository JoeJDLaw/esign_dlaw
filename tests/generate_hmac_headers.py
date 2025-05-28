# File: tests/generate_hmac_headers.py
from dotenv import load_dotenv
load_dotenv()

import hmac
import hashlib
import time
import os

SF_SECRET_KEY = os.environ["SF_SECRET_KEY"].encode()

timestamp = str(int(time.time()))
body = '{"template_type":"cea","client_name":"Jane Doe","client_email":"jane@example.com","date":"2025-05-28","salesforce_case_id":"a0B7V00000abc123EAA"}'

message = f"{timestamp}{body}".encode()
signature = hmac.new(SF_SECRET_KEY, message, hashlib.sha256).hexdigest()

print("curl -X POST https://esign.dlaw.app/api/v1/initiate \\")
print(f"  -H \"Content-Type: application/json\" \\")
print(f"  -H \"X-Timestamp: {timestamp}\" \\")
print(f"  -H \"X-Signature: {signature}\" \\")
print(f"  -d '{body}'")