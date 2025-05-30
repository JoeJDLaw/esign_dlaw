# File: /srv/apps/esign/app/api/routes_signing.py

from shared.log_utils.logging_config import configure_logging
logger = configure_logging("apps.esign.routes_signing", "esign.log")

from flask import Blueprint, render_template, abort, request, send_file, jsonify
from app.db.session import get_session
from app.db.models import SignatureRequest, SignatureStatus
from datetime import datetime, timezone, timedelta
import hashlib
from app.core.pdf_loader import get_template_path
import os
import glob

# Imports for POST route
from app.core.signer import embed_signature_on_pdf

signing_bp = Blueprint("esign_signing", __name__, url_prefix="/v1/sign")

def should_send_webhook() -> bool:
    """
    Check if webhooks should be sent based on environment configuration.
    Returns True if webhooks are enabled, False if disabled.
    """
    return os.environ.get("DISABLE_WEBHOOKS", "").lower() != "true"

def cleanup_prefilled_pdfs(max_age_hours: int = 24) -> tuple[int, int]:
    """
    Clean up old sample PDFs from the preview directory.
    
    Args:
        max_age_hours: Maximum age of files in hours before deletion (default: 24)
    
    Returns:
        tuple: (number of files deleted, number of files skipped)
    """
    try:
        preview_dir = os.path.abspath("preview")
        if not os.path.exists(preview_dir):
            logger.warning("Preview directory does not exist")
            return 0, 0

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        deleted = 0
        skipped = 0

        # Get all sample PDF files in the preview directory
        pdf_files = glob.glob(os.path.join(preview_dir, "*_sample.pdf"))
        
        for pdf_path in pdf_files:
            try:
                # Get file's last modification time
                mtime = datetime.fromtimestamp(os.path.getmtime(pdf_path))
                
                if mtime < cutoff_time:
                    os.remove(pdf_path)
                    deleted += 1
                    logger.info(f"Deleted old sample PDF: {pdf_path}")
                else:
                    skipped += 1
            except Exception as e:
                logger.error(f"Error processing file {pdf_path}: {e}")
                skipped += 1

        logger.info(f"Cleanup complete. Deleted: {deleted}, Skipped: {skipped}")
        return deleted, skipped

    except Exception as e:
        logger.exception("Error during sample cleanup")
        raise

def generate_prefilled_pdf(template_path: str, token_hash: str, client_name: str) -> str:
    """
    Generate a sample PDF with client name and date (but no signature).
    Returns the path to the generated PDF.
    """
    try:
        preview_dir = os.path.abspath("preview")
        os.makedirs(preview_dir, exist_ok=True)
        output_path = os.path.join(preview_dir, f"{token_hash[:8]}_sample.pdf")

        # Use embed_signature_on_pdf with preview flag, and get the actual output path
        actual_output_path = embed_signature_on_pdf(
            template_key=os.path.splitext(os.path.basename(template_path))[0],
            output_path=output_path,
            signature_b64="",  # Not used for preview
            client_name=client_name,
            sign_date=datetime.utcnow().strftime("%Y-%m-%d"),
            test_mode=False,
            is_preview=True
        )

        logger.info(f"Generated sample PDF at: {actual_output_path}")
        return actual_output_path
    except Exception as e:
        logger.exception(f"Error generating sample PDF: {e}")
        raise

@signing_bp.route("/<token>", methods=["GET"])
def sign_document(token):
    logger.info(f"Processing signature request for token: {token[:8]}...")
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request:
        logger.warning(f"Signature request not found for token: {token[:8]}...")
        abort(404)

    if signature_request.status != SignatureStatus.pending:
        logger.warning(f"Document no longer available for signing. Token: {token[:8]}..., Status: {signature_request.status}")
        return "This document is no longer available for signing.", 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        logger.warning(f"Signature link expired. Token: {token[:8]}..., Expires: {signature_request.expires_at}")
        return "This link has expired.", 403

    logger.debug(f"template_type from DB: '{signature_request.template_type}'")
    try:
        template_path = get_template_path(signature_request.template_type)
        logger.info(f"Template path resolved for signing: {template_path}")
        
        # Generate prefilled PDF and get the actual filename
        prefill_path = generate_prefilled_pdf(
            template_path=template_path,
            token_hash=token_hash,
            client_name=signature_request.client_name
        )
        prefill_filename = os.path.basename(prefill_path)
        # Save preview_path to the database
        signature_request.preview_path = prefill_path
        session.commit()
        
        logger.info(f"Rendering signature page for client: {signature_request.client_name}")
        return render_template(
            "sign.html",
            client_name=signature_request.client_name,
            token=token,
            prefill_filename=prefill_filename
        )
    except Exception as e:
        logger.error(f"Failed to prepare document: {e}")
        return "An error occurred while preparing the document.", 500


# POST route for submitting the signature
@signing_bp.route("/<token>", methods=["POST"])
def submit_signature(token):
    logger.info(f"Processing submitted signature for token: {token[:8]}...")
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Debug log for IP headers
    logger.info(f"X-Forwarded-For: {request.headers.get('X-Forwarded-For')}, remote_addr: {request.remote_addr}")

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request:
        logger.warning(f"Signature request not found for token: {token[:8]}...")
        return jsonify({"error": "Signature request not found."}), 404

    if signature_request.status != SignatureStatus.pending:
        logger.warning(f"Document already signed or invalid. Token: {token[:8]}..., Status: {signature_request.status}")
        return jsonify({"error": "This document is no longer available for signing."}), 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        logger.warning(f"Signature link expired. Token: {token[:8]}..., Expires: {signature_request.expires_at}")
        return jsonify({"error": "This link has expired."}), 403

    # Accept signature from either JSON payload or form data
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        signature_b64 = payload.get("signature")
    else:
        signature_b64 = request.form.get("signature")

    if not signature_b64:
        logger.warning(f"Signature missing in submission. Token: {token[:8]}...")
        return jsonify({"error": "Missing signature data."}), 400

    try:
        output_dir = os.path.abspath("signed")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{token_hash[:8]}_signed.pdf")

        signed_pdf_path = embed_signature_on_pdf(
            template_key=signature_request.template_type,
            output_path=output_path,
            signature_b64=signature_b64,
            client_name=signature_request.client_name,
            sign_date=datetime.utcnow().strftime("%Y-%m-%d"),
        )

        signature_request.status = SignatureStatus.signed
        signature_request.signed_at = datetime.utcnow()
        signature_request.pdf_path = signed_pdf_path
        # Capture real client IP behind proxy
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            signature_request.signed_ip = xff.split(",")[0].strip()
        else:
            signature_request.signed_ip = request.remote_addr
        signature_request.user_agent = request.headers.get("User-Agent", "")
        # Log audit event
        if isinstance(signature_request.audit_log, list):
            signature_request.audit_log.append({
                "event": "signed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        session.commit()

        redirect_url = f"/v1/sign/final/{token}"
        logger.info(f"Signature successfully processed. File saved: {signed_pdf_path}. Redirecting to {redirect_url}")
        return jsonify({"redirect_url": redirect_url})

    except Exception as e:
        logger.exception(f"Error while processing signature for token: {token[:8]}...")
        return jsonify({"error": "An error occurred while saving the signed document."}), 500

@signing_bp.route("/thank-you", methods=["GET"])
def thank_you():
    # Try to get token from query string for context (optional, if you want to pass it)
    token = request.args.get('token')
    if token:
        session = get_session()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()
        if signature_request and should_send_webhook():
            # Send webhook to RingCentral for signature completion
            try:
                rc_webhook_url = "https://hooks.ringcentral.com/webhook/v2/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJvdCI6ImMiLCJvaSI6IjMxNDY0MDc5MzciLCJpZCI6IjMwNzYyMTA3MTUifQ.L--SpnXvDawVy69XJykgCdIpHNmpADqsdV-DyZOXAhk"
                rc_payload = {
                    "text": (
                        f"Signature completed!\n"
                        f"URL: {signature_request.signing_url}\n"
                        f"Name: {signature_request.client_name}\n"
                        f"Email: {signature_request.client_email}\n"
                        f"Template: {signature_request.template_type}\n"
                        f"Salesforce Case ID: {signature_request.salesforce_case_id}\n"
                        f"Expires: {signature_request.expires_at.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                        f"Signed at: {signature_request.signed_at.strftime('%Y-%m-%d %H:%M:%S UTC') if signature_request.signed_at else ''}"
                    )
                }
                import requests
                rc_response = requests.post(rc_webhook_url, json=rc_payload)
                logger.info(f"Posted signature complete to RingCentral webhook: {rc_response.status_code} {rc_response.text}")
            except Exception as e:
                logger.error(f"Error posting signature complete to RingCentral webhook: {e}")
    return render_template("thank-you.html")

@signing_bp.route("/preview/<filename>", methods=["GET"])
def serve_prefilled_pdf(filename):
    """
    Securely serve a sample PDF document by filename.
    """
    logger.info(f"Serving sample PDF: {filename}")
    preview_dir = os.path.abspath("preview")
    preview_path = os.path.join(preview_dir, filename)
    if not os.path.exists(preview_path):
        logger.error(f"Sample PDF not found at: {preview_path}")
        abort(404)
    try:
        return send_file(
            preview_path,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        logger.exception(f"Error serving sample PDF: {e}")
        abort(500)

@signing_bp.route("/signed/<filename>", methods=["GET"])
def serve_signed_pdf(filename):
    """
    Securely serve a signed PDF document by filename.
    """
    logger.info(f"Serving signed PDF: {filename}")
    signed_dir = os.path.abspath("signed")
    signed_path = os.path.join(signed_dir, filename)
    if not os.path.exists(signed_path):
        logger.error(f"Signed PDF not found at: {signed_path}")
        abort(404)
    try:
        return send_file(
            signed_path,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=filename
        )
    except Exception as e:
        logger.exception(f"Error serving signed PDF: {e}")
        abort(500)

@signing_bp.route("/final/<token>", methods=["GET"])
def final_review(token):
    logger.info(f"Rendering final review for token: {token[:8]}...")
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request or signature_request.status != SignatureStatus.signed:
        logger.warning(f"Final review not available for token: {token[:8]}...")
        abort(403)

    # Optionally log the final review event
    if isinstance(signature_request.audit_log, list):
        signature_request.audit_log.append({
            "event": "final_review_viewed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        session.commit()

    signed_filename = os.path.basename(signature_request.pdf_path)
    return render_template("final_review.html", client_name=signature_request.client_name, signed_filename=signed_filename, token=token)