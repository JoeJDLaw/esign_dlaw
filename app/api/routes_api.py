# File: /srv/apps/esign/app/api/routes_api.py

from flask import Blueprint, request, jsonify
from app.db.models import SignatureRequest, SignatureStatus
from app.db.session import get_session
from datetime import datetime, timedelta, timezone
import hashlib
import uuid

api_bp = Blueprint("esign_api", __name__, url_prefix="/api/esign")

def create_audit_log_event(event: str, **details):
    return {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **details
    }

@api_bp.route("/initiate", methods=["POST"])
def initiate_signature():
    data = request.get_json()

    required_fields = ["client_name", "client_email", "template_type", "salesforce_case_id"]
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    session = get_session()

    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    audit_log = [
        create_audit_log_event(
            "initiated",
            source="Salesforce",
            request_data={field: data[field] for field in required_fields}
        )
    ]

    signature_request = SignatureRequest(
        client_name=data["client_name"],
        client_email=data["client_email"],
        template_type=data["template_type"],
        salesforce_case_id=data["salesforce_case_id"],
        token_hash=token_hash,
        audit_log=audit_log,
        status=SignatureStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2)
    )

    session.add(signature_request)
    session.commit()

    return jsonify({
        "message": "Signature request created",
        "token": token,
        "expires_at": signature_request.expires_at.isoformat()
    }), 201

@api_bp.route("/sign/<token>", methods=["POST"])
def sign_document(token):
    data = request.get_json()
    if not data or not data.get("consent") or not data.get("signature"):
        return jsonify({"error": "Consent and signature are required"}), 400

    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request:
        return jsonify({"error": "Invalid or expired token"}), 404

    if signature_request.status != SignatureStatus.pending:
        return jsonify({"error": "Document already signed or not available"}), 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        return jsonify({"error": "This link has expired"}), 403

    # Update fields
    signature_request.status = SignatureStatus.signed
    signature_request.signed_at = datetime.now(timezone.utc)
    # Only set signed_ip if we have a valid IP address
    if request.remote_addr and request.remote_addr != '':
        signature_request.signed_ip = request.remote_addr
    signature_request.user_agent = request.headers.get("User-Agent", "Unknown")

    # Append to audit log
    log_entry = create_audit_log_event(
        "signed",
        ip=signature_request.signed_ip if hasattr(signature_request, 'signed_ip') else None,
        user_agent=signature_request.user_agent
    )
    if isinstance(signature_request.audit_log, list):
        signature_request.audit_log.append(log_entry)
    else:
        signature_request.audit_log = [log_entry]

    session.commit()
    return jsonify({"message": "Document signed successfully"}), 200