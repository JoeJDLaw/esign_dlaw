# File: /srv/apps/esign/tests/generate_hmac_headers.py

from dotenv import load_dotenv
load_dotenv("/srv/shared/.env")

import argparse
import hmac
import hashlib
import time
import os
from datetime import date

try:
    from faker import Faker
except ImportError:
    raise ImportError("The 'faker' library is required for this script. Please install it via 'pip install faker'.")

faker = Faker()

parser = argparse.ArgumentParser(description="Generate HMAC headers for eSign API")
parser.add_argument("--template", type=str, required=True, help="Template type (e.g., cea, rra, or cea_rra)")
parser.add_argument("--client_name", type=str, default=faker.name(), help="Client name")
parser.add_argument("--client_email", type=str, default=faker.email(), help="Client email")
parser.add_argument("--salesforce_case_id", type=str, default=faker.bothify(text='a0B7V00000????????EAA'), help="Salesforce case ID (18 characters)")
parser.add_argument("--envelope_document_id", type=str, default="a44Hs000005lVCOIA2", help="Salesforce Envelope Document ID")

args = parser.parse_args()

SF_SECRET_KEY = os.environ["SF_SECRET_KEY"].encode()

timestamp = str(int(time.time()))
body = f'{{"template_type":"{args.template}","client_name":"{args.client_name}","client_email":"{args.client_email}","salesforce_case_id":"{args.salesforce_case_id}","envelope_document_id":"{args.envelope_document_id}"}}'

message = f"{timestamp}{body}".encode()
signature = hmac.new(SF_SECRET_KEY, message, hashlib.sha256).hexdigest()

print("curl -X POST https://esign.dlaw.app/api/v1/initiate \\")
print(f"  -H \"Content-Type: application/json\" \\")
print(f"  -H \"X-Timestamp: {timestamp}\" \\")
print(f"  -H \"X-Signature: {signature}\" \\")
print(f"  -d '{body}'")