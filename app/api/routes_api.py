import os
import uuid
import hmac
import hashlib
import traceback
from time import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from flask import Blueprint, request, jsonify, render_template

from log_utils.logging_config import configure_logging
from app.db.models import SignatureRequest, SignatureStatus
from app.db.session import get_session
from app.core.signer import embed_signature_on_pdf
from app.core.pdf_loader import get_template_path

logger = configure_logging("apps.esign.routes_api", "esign.log")

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


def should_send_webhook() -> bool:
    return os.environ.get("DISABLE_WEBHOOKS", "").lower() != "true"


@api_bp.route("/initiate", methods=["POST"])
def initiate_signature():
    try:
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
                request_data={field: data.get(field) for field in required_fields}
            )
        ]

        full_url = f"https://esign.dlaw.app/v1/sign/{token}"

        signature_request = SignatureRequest(
            client_name=data.get("client_name"),
            client_email=data.get("client_email"),
            template_type=data.get("template_type"),
            salesforce_case_id=data.get("salesforce_case_id"),
            envelope_document_id=data.get("envelope_document_id"),  # Optional - can be updated later
            token=token,
            token_hash=token_hash,
            audit_log=audit_log,
            status=SignatureStatus.Sent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            signing_url=full_url
        )

        session.add(signature_request)
        session.commit()
        logger.info(f"Successfully created signature request for client: {data.get('client_name')}")

        if should_send_webhook():
            try:
                rc_webhook_url = os.environ.get("RC_WEBHOOK_URL")
                if rc_webhook_url:
                    expires_date = signature_request.expires_at.date().isoformat() if signature_request.expires_at else ""
                    rc_payload = {
                        "text": (
                            f"New document ready for signing:\n"
                            f"URL: {full_url}\n"
                            f"Name: {data.get('client_name', '')}\n"
                            f"Email: {data.get('client_email', '')}\n"
                            f"Template: {data.get('template_type', '')}\n"
                            f"Salesforce Case ID: {data.get('salesforce_case_id', '')}\n"
                            f"Envelope Document ID: {data.get('envelope_document_id', 'Not yet assigned')}\n"
                            f"Status: {signature_request.status.value.title()}\n"
                            f"Expires: {expires_date}"
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
    except Exception:
        logger.exception("Unhandled error occurred")
        return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500


@api_bp.route("/update-envelope", methods=["POST"])
def update_envelope_id():
    """Update an existing signature request with the envelope document ID."""
    if not is_valid_hmac_request(request):
        return jsonify({"error": "Unauthorized"}), 401

    logger.info("Processing envelope ID update request")
    data = request.get_json()

    required_fields = ["token", "envelope_document_id"]
    if not all(field in data for field in required_fields):
        logger.warning(f"Missing required fields in envelope update. Provided fields: {list(data.keys())}")
        return jsonify({"error": "Missing required fields"}), 400

    session = get_session()
    token = data.get("token")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()
    if not signature_request:
        logger.warning(f"Signature request not found for token: {token[:8]}...")
        return jsonify({"error": "Signature request not found"}), 404

    # Update the envelope document ID
    signature_request.envelope_document_id = data.get("envelope_document_id")
    
    # Add audit log entry
    if isinstance(signature_request.audit_log, list):
        signature_request.audit_log.append({
            "event": "envelope_id_updated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "envelope_document_id": data.get("envelope_document_id")
        })
    
    session.commit()
    logger.info(f"Updated envelope document ID for signature request: {data.get('envelope_document_id')}")

    return jsonify({
        "message": "Envelope document ID updated successfully",
        "envelope_document_id": signature_request.envelope_document_id
    }), 200


@api_bp.route("/sign/<token>", methods=["POST"])
def sign_document(token):
    try:
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

        if signature_request.status != SignatureStatus.Sent:
            logger.warning(f"Document not available for signing. Token: {token[:8]}..., Status: {signature_request.status}")
            return jsonify({"error": "Document already signed or not available"}), 403

        if signature_request.expires_at < datetime.now(timezone.utc):
            logger.warning(f"Signature link expired. Token: {token[:8]}..., Expires: {signature_request.expires_at}")
            return jsonify({"error": "This link has expired"}), 403

        signature_request.status = SignatureStatus.Completed
        signature_request.signed_at = datetime.now(timezone.utc)
        if request.remote_addr:
            signature_request.signed_ip = request.remote_addr
        signature_request.user_agent = request.headers.get("User-Agent", "Unknown")

        # Create signed/YYYYMMDD subdirectory and pass it to embed_signature_on_pdf
        signed_root = Path("signed").resolve()
        today_folder = datetime.now().strftime("%Y%m%d")
        dated_dir = signed_root / today_folder
        dated_dir.mkdir(parents=True, exist_ok=True)

        base_name = f"{token_hash[:8]}_signed.pdf"
        output_path = dated_dir / base_name

        final_output_path = embed_signature_on_pdf(
            template_key=signature_request.template_type,
            output_path=str(output_path),
            signature_b64=data.get("signature"),
            client_name=signature_request.client_name,
            sign_date=datetime.utcnow().strftime("%Y-%m-%d"),
        )
        signature_request.pdf_path = final_output_path

        log_entry = create_audit_log_event(
            "signed",
            ip=signature_request.signed_ip,
            user_agent=signature_request.user_agent
        )
        if isinstance(signature_request.audit_log, list):
            signature_request.audit_log.append(log_entry)
        else:
            signature_request.audit_log = [log_entry]

        session.commit()
        logger.info(f"Successfully processed signature for client: {signature_request.client_name}")
        return render_template("thank-you.html", client_name=signature_request.client_name)
    except Exception:
        logger.exception("Unhandled error during sign_document")
        return jsonify({"error": "An unexpected error occurred while signing the document. Please try again later."}), 500