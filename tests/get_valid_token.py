

# ------------------------------------------------------------------------
# File: get_valid_token.py
# Location: /srv/apps/esign/tests/get_valid_token.py
# Description:
#     Script to generate and insert a valid SignatureRequest into the
#     database for manual testing. Outputs a usable token for signing.
# ------------------------------------------------------------------------

import uuid
import hashlib
from datetime import datetime, timedelta

from app.db.models import SignatureRequest, SignatureStatus
from app.db.session import get_session

# Configuration
client_name = "Test Client"
client_email = "test@example.com"
template_type = "case_eval"
salesforce_case_id = "TEST123"
expiration_minutes = 60 * 48  # 48 hours

# Generate token and hash
token = str(uuid.uuid4())
token_hash = hashlib.sha256(token.encode()).hexdigest()

# Prepare DB row
request = SignatureRequest(
    client_name=client_name,
    client_email=client_email,
    template_type=template_type,
    token_hash=token_hash,
    salesforce_case_id=salesforce_case_id,
    status=SignatureStatus.pending,
    expires_at=datetime.utcnow() + timedelta(minutes=expiration_minutes),
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow()
)

# Insert into DB
session = get_session()
session.add(request)
session.commit()

print(f"\n✅ SignatureRequest created.\nUse this token in your browser:\n\n{token}\n")