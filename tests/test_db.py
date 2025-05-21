# File: /srv/apps/esign/tests/test_db.py

from app.db.models import SignatureRequest, SignatureStatus
from app.db.session import get_session
from datetime import datetime, timedelta
import hashlib
import uuid

def run_test_insert_and_query():
    session = get_session()

    test_token = str(uuid.uuid4())
    hashed_token = hashlib.sha256(test_token.encode()).hexdigest()

    req = SignatureRequest(
        client_name="Jane Test",
        client_email="jane@example.com",
        template_type="case_eval",
        pdf_path=None,
        signed_at=None,
        signed_ip=None,
        user_agent="TestAgent/1.0",
        audit_log={"event": "created_in_test_script"},
        salesforce_case_id="CASE-REPL-001",
        status=SignatureStatus.pending,
        token_hash=hashed_token,
        expires_at=datetime.utcnow() + timedelta(days=2),
    )

    session.add(req)
    session.commit()

    result = session.query(SignatureRequest).filter_by(client_email="jane@example.com").first()
    print(f"Fetched: {result.id} | {result.client_name} | {result.status}")

if __name__ == "__main__":
    run_test_insert_and_query()