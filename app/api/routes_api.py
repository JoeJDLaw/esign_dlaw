import sys
sys.path.insert(0, "/srv/shared")
from shared.log_utils.logging_config import configure_logging
logger = configure_logging("apps.esign.routes_api", "esign.log")

from flask import Blueprint, request, jsonify
from app.db.models import SignatureRequest, SignatureStatus
from app.db.session import get_session
from datetime import datetime, timedelta, timezone
import hashlib
import uuid
import hmac
import os
import hashlib

api_bp = Blueprint("esign_api", __name__, url_prefix="/api/v1")

def is_valid_hmac_request(request):
    shared_secret = os.environ.get("SALESFORCE_SHARED_SECRET", "").encode()
    timestamp = request.headers.get("X-Timestamp", "")
    signature = request.headers.get("X-Signature", "")

    if not shared_secret or not timestamp or not signature:
        logger.warning("Missing HMAC headers or shared secret")
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        logger.warning("Invalid X-Timestamp format")
        return False

    # Prevent replay attacks: allow max 5 min drift
    from time import time
    if abs(time() - timestamp_int) > 300:
        logger.warning("Request timestamp is outside the allowable window")
        return False

    body = request.get_data(as_text=True)
    data_to_sign = f"{timestamp}{body}".encode()
    expected_sig = hmac.new(shared_secret, data_to_sign, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        logger.warning("HMAC signature mismatch")
        return False

    return True

def create_audit_log_event(event: str, **details):
    return {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **details
    }

@api_bp.route("/initiate", methods=["POST"])
def initiate_signature():
    # HMAC validation temporarily disabled for testing
    # if not is_valid_hmac_request(request):
    #     return jsonify({"error": "Unauthorized"}), 401

    logger.info("Processing new signature request initiation")
    data = request.get_json()

    required_fields = ["client_name", "client_email", "template_type", "salesforce_case_id"]
    if not all(field in data for field in required_fields):
        logger.warning(f"Missing required fields in signature request. Provided fields: {list(data.keys())}")
        return jsonify({"error": "Missing required fields"}), 400

    session = get_session()

    token = str(uuid.uuid4())
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    logger.debug(f"Generated new token hash for request: {token_hash[:8]}...")

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
    logger.info(f"Successfully created signature request for client: {data['client_name']}")

    return jsonify({
        "message": "Signature request created",
        "token": token,
        "expires_at": signature_request.expires_at.isoformat()
    }), 201

@api_bp.route("/sign/<token>", methods=["POST"])
def sign_document(token):
    logger.info(f"Processing document signing request for token: {token[:8]}...")
    data = request.get_json()
    if not data or not data.get("consent") or not data.get("signature"):
        logger.warning(f"Missing consent or signature in request for token: {token[:8]}...")
        return jsonify({"error": "Consent and signature are required"}), 400

    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request:
        logger.warning(f"Invalid token hash: {token_hash[:8]}...")
        return jsonify({"error": "Invalid or expired token"}), 404

    if signature_request.status != SignatureStatus.pending:
        logger.warning(f"Document not available for signing. Token: {token[:8]}..., Status: {signature_request.status}")
        return jsonify({"error": "Document already signed or not available"}), 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        logger.warning(f"Signature link expired. Token: {token[:8]}..., Expires: {signature_request.expires_at}")
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
    logger.info(f"Successfully processed signature for client: {signature_request.client_name}")
    return jsonify({"message": "Document signed successfully"}), 200