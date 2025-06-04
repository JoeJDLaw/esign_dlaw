# File: /srv/apps/esign/app/api/routes_signing.py

from log_utils.logging_config import configure_logging
logger = configure_logging("apps.esign.routes_signing", "esign.log")

from flask import Blueprint, render_template, abort, request, send_file, jsonify
from app.db.session import get_session
from app.db.models import SignatureRequest, SignatureStatus
from datetime import datetime, timezone, timedelta
import hashlib
from app.core.pdf_loader import get_template_path
import os
import glob
import requests
from app.core.signer import embed_signature_on_pdf

signing_bp = Blueprint("esign_signing", __name__, url_prefix="/v1/sign")


def should_send_webhook() -> bool:
    return os.environ.get("DISABLE_WEBHOOKS", "").lower() != "true"


def cleanup_prefilled_pdfs(max_age_hours: int = 24) -> tuple[int, int]:
    try:
        preview_dir = os.path.abspath("preview")
        if not os.path.exists(preview_dir):
            logger.warning("Preview directory does not exist")
            return 0, 0

        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        deleted, skipped = 0, 0

        for root, _, files in os.walk(preview_dir):
            for file in files:
                if file.endswith("_sample.pdf"):
                    pdf_path = os.path.join(root, file)
                    try:
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
    try:
        preview_dir = os.path.abspath("preview")
        os.makedirs(preview_dir, exist_ok=True)
        output_path = os.path.join(preview_dir, f"{token_hash[:8]}_sample.pdf")

        return embed_signature_on_pdf(
            template_key=os.path.splitext(os.path.basename(template_path))[0],
            output_path=output_path,
            signature_b64="",
            client_name=client_name,
            sign_date=datetime.utcnow().strftime("%Y-%m-%d"),
            test_mode=False,
            is_preview=True
        )
    except Exception as e:
        logger.exception("Error generating sample PDF")
        raise


@signing_bp.route("/<token>", methods=["GET"])
def sign_document(token):
    logger.info(f"Processing signature request for token: {token[:8]}...")
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request:
        logger.warning("Signature request not found")
        abort(404)

    if signature_request.status != SignatureStatus.pending:
        return "This document is no longer available for signing.", 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        return "This link has expired.", 403

    try:
        template_path = get_template_path(signature_request.template_type)
        prefill_path = generate_prefilled_pdf(template_path, token_hash, signature_request.client_name)
        signature_request.preview_path = prefill_path
        session.commit()

        return render_template(
            "sign.html",
            client_name=signature_request.client_name,
            token=token,
            prefill_filename=os.path.basename(prefill_path)
        )
    except Exception as e:
        logger.exception("Failed to prepare document")
        return "An error occurred while preparing the document.", 500


@signing_bp.route("/<token>", methods=["POST"])
def submit_signature(token):
    logger.info(f"Submitting signature for token: {token[:8]}...")
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()
    if not signature_request:
        return jsonify({"error": "Signature request not found."}), 404

    if signature_request.status != SignatureStatus.pending:
        return jsonify({"error": "Document already signed."}), 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        return jsonify({"error": "Link expired."}), 403

    signature_b64 = (request.get_json(silent=True) or {}).get("signature") if request.is_json else request.form.get("signature")
    if not signature_b64:
        return jsonify({"error": "Missing signature data."}), 400

    try:
        signed_dir = os.path.abspath("signed")
        os.makedirs(signed_dir, exist_ok=True)
        output_path = os.path.join(signed_dir, f"{token_hash[:8]}_signed.pdf")

        signed_pdf_path = embed_signature_on_pdf(
            template_key=signature_request.template_type,
            output_path=output_path,
            signature_b64=signature_b64,
            client_name=signature_request.client_name,
            sign_date=datetime.utcnow().strftime("%Y-%m-%d")
        )

        signature_request.status = SignatureStatus.signed
        signature_request.signed_at = datetime.utcnow()
        signature_request.pdf_path = signed_pdf_path
        signature_request.signed_ip = request.headers.get("X-Forwarded-For", request.remote_addr).split(",")[0].strip()
        signature_request.user_agent = request.headers.get("User-Agent", "")
        if isinstance(signature_request.audit_log, list):
            signature_request.audit_log.append({
                "event": "signed",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        session.commit()

        return jsonify({"redirect_url": f"/v1/sign/final/{token}"})
    except Exception:
        logger.exception("Error processing signature")
        return jsonify({"error": "Error saving signed document."}), 500


@signing_bp.route("/thank-you", methods=["GET"])
def thank_you():
    token = request.args.get("token")
    if token and should_send_webhook():
        session = get_session()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()
        if signature_request:
            webhook_url = os.environ.get("RC_WEBHOOK_URL")
            if webhook_url:
                try:
                    payload = {
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
                    response = requests.post(webhook_url, json=payload)
                    logger.info(f"Webhook response: {response.status_code} {response.text}")
                except Exception:
                    logger.exception("Failed to post RingCentral webhook")
    return render_template("thank-you.html")


@signing_bp.route("/preview/<filename>", methods=["GET"])
def serve_prefilled_pdf(filename):
    preview_root = os.path.abspath("preview")
    for dated_folder in sorted(os.listdir(preview_root), reverse=True):
        candidate_path = os.path.join(preview_root, dated_folder, filename)
        if os.path.exists(candidate_path):
            try:
                return send_file(candidate_path, mimetype='application/pdf', as_attachment=False, download_name=filename)
            except Exception:
                logger.exception("Error serving sample PDF")
                abort(500)
    logger.error(f"Preview file not found: {filename}")
    abort(404)


@signing_bp.route("/signed/<filename>", methods=["GET"])
def serve_signed_pdf(filename):
    signed_root = os.path.abspath("signed")
    for dated_folder in sorted(os.listdir(signed_root), reverse=True):
        candidate_path = os.path.join(signed_root, dated_folder, filename)
        if os.path.exists(candidate_path):
            try:
                return send_file(candidate_path, mimetype='application/pdf', as_attachment=False, download_name=filename)
            except Exception:
                logger.exception("Error serving signed PDF")
                abort(500)
    logger.error(f"Signed file not found: {filename}")
    abort(404)


@signing_bp.route("/final/<token>", methods=["GET"])
def final_review(token):
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request or signature_request.status != SignatureStatus.signed:
        abort(403)

    if isinstance(signature_request.audit_log, list):
        signature_request.audit_log.append({
            "event": "final_review_viewed",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        session.commit()

    return render_template(
        "final_review.html",
        client_name=signature_request.client_name,
        signed_filename=os.path.basename(signature_request.pdf_path),
        token=token
    )