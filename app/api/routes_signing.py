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

from utils.dropbox_api.factory import get_authenticated_client

from app.api.update_envelope_document import update_envelope_document, find_envelope_id_by_token

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

    # If status is Sent, update to Delivered
    if signature_request.status == SignatureStatus.Sent:
        signature_request.status = SignatureStatus.Delivered
        session.commit()

    # Allow both Sent and Delivered for backward compatibility
    if signature_request.status not in [SignatureStatus.Sent, SignatureStatus.Delivered]:
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
    # dbx = get_authenticated_client()  # TODO: Re-enable when Dropbox is properly configured
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()
    if not signature_request:
        return jsonify({"error": "Signature request not found."}), 404

    # Allow both Sent and Delivered for backward compatibility
    if signature_request.status not in [SignatureStatus.Sent, SignatureStatus.Delivered]:
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

        signature_request.status = SignatureStatus.Completed
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

        import time

        dropbox_folder = os.environ.get("DROPBOX_ESIGN_FOLDER", "/esign")
        dropbox_path = f"{dropbox_folder}/{os.path.basename(signed_pdf_path)}"

        # Prepare Salesforce update payload and try to find envelope_document_id if missing
        from app.api.update_envelope_document import update_envelope_document, find_envelope_id_by_token

        sf_update_payload = {
            "dropbox_file_path__c": signed_pdf_path,
            "Envelope_Status__c": "Completed",
            "Sign_Date__c": signature_request.signed_at.isoformat(),
            "Expiration_Date__c": signature_request.expires_at.date().isoformat() if signature_request.expires_at else None
        }

        envelope_document_id = signature_request.envelope_document_id

        # Only use token-based lookup for Salesforce
        if not envelope_document_id and hasattr(signature_request, 'token') and signature_request.token:
            try:
                envelope_document_id = find_envelope_id_by_token(signature_request.token)
                if envelope_document_id:
                    signature_request.envelope_document_id = envelope_document_id
                    session.commit()
                    logger.info(f"Retrieved envelope_document_id via token: {envelope_document_id}")
                else:
                    logger.warning("Could not resolve envelope_document_id via token lookup")
            except Exception as e:
                logger.exception(f"Error fetching envelope_document_id: {e}")

        if not envelope_document_id:
            logger.warning("No envelope_document_id found - skipping Salesforce update")

        max_sf_attempts = 3
        base_sf_delay = 2  # seconds
        webhook_url = os.environ.get("RC_WEBHOOK_URL")
        send_webhook = should_send_webhook()

        # Only attempt Salesforce update if we have an envelope document ID
        if envelope_document_id:
            for attempt in range(1, max_sf_attempts + 1):
                try:
                    update_envelope_document(sf_update_payload, envelope_document_id)
                    logger.info(f"Salesforce Envelope Document {envelope_document_id} updated. (attempt {attempt})")
                    if send_webhook and webhook_url and isinstance(signature_request.audit_log, list):
                        signature_request.audit_log.append({
                            "event": "salesforce_update_success",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        session.commit()
                        try:
                            payload = {
                                "text": (
                                    f"Salesforce update succeeded for Envelope Document {envelope_document_id} "
                                    f"on attempt {attempt}."
                                )
                            }
                            response = requests.post(webhook_url, json=payload)
                            logger.info(f"Webhook response: {response.status_code} {response.text}")
                        except Exception:
                            logger.exception("Failed to post Salesforce update success webhook")
                    break
                except Exception as e:
                    logger.warning(f"Attempt {attempt} to update Salesforce failed: {e}")
                    if send_webhook and webhook_url and isinstance(signature_request.audit_log, list):
                        signature_request.audit_log.append({
                            "event": "salesforce_update_retry",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "attempt": attempt,
                            "error": str(e)
                        })
                        session.commit()
                        try:
                            payload = {
                                "text": (
                                    f"Salesforce update retry {attempt} failed for Envelope Document {envelope_document_id}: {e}"
                                )
                            }
                            response = requests.post(webhook_url, json=payload)
                            logger.info(f"Webhook response: {response.status_code} {response.text}")
                        except Exception:
                            logger.exception("Failed to post Salesforce update retry webhook")
                    if attempt < max_sf_attempts:
                        sf_sleep_time = base_sf_delay * (2 ** (attempt - 1))
                        logger.info(f"Retrying Salesforce update in {sf_sleep_time} seconds...")
                        time.sleep(sf_sleep_time)
                    else:
                        logger.error(f"All attempts to update Salesforce failed for Envelope Document {envelope_document_id}")
                        if send_webhook and webhook_url and isinstance(signature_request.audit_log, list):
                            signature_request.audit_log.append({
                                "event": "salesforce_update_failed",
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                            session.commit()
                            try:
                                payload = {
                                    "text": (
                                        f"Salesforce update failed for Envelope Document {envelope_document_id} after {max_sf_attempts} attempts."
                                    )
                                }
                                response = requests.post(webhook_url, json=payload)
                                logger.info(f"Webhook response: {response.status_code} {response.text}")
                            except Exception:
                                logger.exception("Failed to post Salesforce update failure webhook")
        else:
            logger.info("Skipping Salesforce update - no envelope document ID available")

        # TODO: Re-enable Dropbox upload when properly configured with refresh tokens
        # dropbox_upload_success = False
        # max_attempts = 3
        # base_delay = 2  # seconds

        # for attempt in range(1, max_attempts + 1):
        #     try:
        #         dbx.upload_file(dropbox_path, signed_pdf_path)
        #         logger.info(f"Uploaded signed file to Dropbox: {dropbox_path} (attempt {attempt})")
        #         dropbox_upload_success = True
        #         break
        #     except Exception as e:
        #         logger.warning(f"Attempt {attempt} failed to upload to Dropbox: {e}")
        #         if attempt < max_attempts:
        #             sleep_time = base_delay * (2 ** (attempt - 1))
        #             logger.info(f"Retrying in {sleep_time} seconds...")
        #             time.sleep(sleep_time)

        response_data = {"redirect_url": f"/v1/sign/final/{token}"}
        # if not dropbox_upload_success:
        #     response_data["warning"] = "Document saved locally but Dropbox upload failed."
        logger.info("Dropbox upload temporarily disabled - document saved locally only")
        return jsonify(response_data)
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
                    expires_date = signature_request.expires_at.date().isoformat() if signature_request.expires_at else ""
                    payload = {
                        "text": (
                            f"Signature completed!\n"
                            f"URL: {signature_request.signing_url}\n"
                            f"Name: {signature_request.client_name}\n"
                            f"Email: {signature_request.client_email}\n"
                            f"Template: {signature_request.template_type}\n"
                            f"Salesforce Case ID: {signature_request.salesforce_case_id}\n"
                            f"Envelope Document ID: {signature_request.envelope_document_id}\n"
                            f"Status: {signature_request.status.value.title()}\n"
                            f"Expires: {expires_date}\n"
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

    if not signature_request or signature_request.status != SignatureStatus.Completed:
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