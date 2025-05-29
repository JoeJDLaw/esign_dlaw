from shared.log_utils.logging_config import configure_logging
logger = configure_logging("apps.esign.routes_api", "esign.log")

from flask import Blueprint, request, jsonify, render_template
from app.db.models import SignatureRequest, SignatureStatus
from app.db.session import get_session
from datetime import datetime, timedelta, timezone
import hashlib
import requests  # ensure this is at the top of the file if not already
import uuid
import hmac
import os
import hashlib
from app.core.signer import embed_signature_on_pdf
from app.core.pdf_loader import get_template_path

api_bp = Blueprint("esign_api", __name__, url_prefix="/api/v1")

def is_valid_hmac_request(request):
    shared_secret = os.environ.get("SF_SECRET_KEY", "").encode()
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
    if not is_valid_hmac_request(request):
        return jsonify({"error": "Unauthorized"}), 401

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

    full_url = f"https://esign.dlaw.app/v1/sign/{token}"

    signature_request = SignatureRequest(
        client_name=data["client_name"],
        client_email=data["client_email"],
        template_type=data["template_type"],
        salesforce_case_id=data["salesforce_case_id"],
        token_hash=token_hash,
        audit_log=audit_log,
        status=SignatureStatus.pending,
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        signing_url=full_url
    )

    session.add(signature_request)
    session.commit()
    logger.info(f"Successfully created signature request for client: {data['client_name']}")

    # Send URL to RingCentral webhook for testing
    try:
        rc_webhook_url = "https://hooks.ringcentral.com/webhook/v2/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJvdCI6ImMiLCJvaSI6IjMxNDY0MDc5MzciLCJpZCI6IjMwNzYyMTA3MTUifQ.L--SpnXvDawVy69XJykgCdIpHNmpADqsdV-DyZOXAhk"
        rc_payload = {
            "text": (
                f"New document ready for signing:\n"
                f"URL: {full_url}\n"
                f"Name: {data.get('client_name', '')}\n"
                f"Email: {data.get('client_email', '')}\n"
                f"Template: {data.get('template_type', '')}\n"
                f"Salesforce Case ID: {data.get('salesforce_case_id', '')}\n"
                f"Expires: {signature_request.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"
            )
        }
        rc_response = requests.post(rc_webhook_url, json=rc_payload)
        logger.info(f"Posted signing URL to RingCentral webhook: {rc_response.status_code} {rc_response.text}")
    except Exception as e:
        logger.error(f"Error posting to RingCentral webhook: {e}")
    return jsonify({
        "message": "Signature request created",
        "token": token,
        "signing_url": full_url,
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

    # Generate and save the signed PDF
    template_path = get_template_path(signature_request.template_type)
    output_dir = os.path.abspath("signed")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{token_hash[:8]}_signed.pdf")

    embed_signature_on_pdf(
        template_path=template_path,
        output_path=output_path,
        signature_b64=data.get("signature"),
        client_name=signature_request.client_name,
        sign_date=datetime.utcnow().strftime("%Y-%m-%d"),
    )
    signature_request.pdf_path = output_path

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
    return render_template("thank-you.html", client_name=signature_request.client_name)