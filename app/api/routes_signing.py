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
import requests
from app.core.signer import embed_signature_on_pdf
from utils.dropbox_api.upload_file import upload_file_to_team_folder
from app.api.update_envelope_document import update_envelope_document, find_envelope_id_by_token, send_webhook_if_enabled

signing_bp = Blueprint("esign_signing", __name__, url_prefix="/v1/sign")


def should_send_webhook() -> bool:
    return os.environ.get("DISABLE_WEBHOOKS", "").lower() != "true"


@signing_bp.route("/<token>", methods=["GET"])
def sign_document(token):
    logger.info(f"Processing signature request for token: {token[:8]}...")
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()
    if not signature_request:
        abort(404)

    if signature_request.status == SignatureStatus.Sent:
        signature_request.status = SignatureStatus.Delivered
        session.commit()

    if signature_request.status not in [SignatureStatus.Sent, SignatureStatus.Delivered]:
        return "This document is no longer available for signing.", 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        return "This link has expired.", 403

    try:
        template_path = get_template_path(signature_request.template_type)
        preview_dir = os.path.abspath("preview")
        os.makedirs(preview_dir, exist_ok=True)
        prefill_path = os.path.join(preview_dir, f"{token_hash[:8]}_sample.pdf")

        actual_preview_path = embed_signature_on_pdf(
            template_key=os.path.splitext(os.path.basename(template_path))[0],
            output_path=prefill_path,
            signature_b64="",
            client_name=signature_request.client_name,
            sign_date=datetime.utcnow().strftime("%Y-%m-%d"),
            test_mode=False,
            is_preview=True
        )

        signature_request.preview_path = actual_preview_path
        session.commit()

        return render_template(
            "sign.html",
            client_name=signature_request.client_name,
            token=token,
            prefill_filename=os.path.basename(actual_preview_path)
        )
    except Exception:
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

        # Upload to Dropbox team folder using proven approach
        upload_success, dropbox_path = upload_file_to_team_folder(
            local_path=signed_pdf_path,
            filename=os.path.basename(signed_pdf_path)
        )
        
        if upload_success:
            logger.info(f"Successfully uploaded to Dropbox: {dropbox_path}")
            send_webhook_if_enabled(
                f"✅ Document signed and uploaded to Dropbox:\n"
                f"Client: {signature_request.client_name}\n"
                f"Email: {signature_request.client_email}\n"
                f"Template: {signature_request.template_type}\n"
                f"Local Path: {signed_pdf_path}\n"
                f"Dropbox Path: {dropbox_path}\n"
                f"File Size: {os.path.getsize(signed_pdf_path)} bytes\n"
                f"Signed At: {signature_request.signed_at.isoformat()}\n"
                f"Salesforce Case: {signature_request.salesforce_case_id}\n"
                f"Envelope ID: {signature_request.envelope_document_id or 'TBD'}"
            )
        else:
            logger.error(f"Failed to upload {signed_pdf_path} to Dropbox team folder")
            # Continue with Salesforce update even if Dropbox upload fails
            dropbox_path = f"UPLOAD_FAILED: {signed_pdf_path}"
            send_webhook_if_enabled(
                f"❌ Document signed but Dropbox upload failed:\n"
                f"Client: {signature_request.client_name}\n"
                f"Email: {signature_request.client_email}\n"
                f"Template: {signature_request.template_type}\n"
                f"Local Path: {signed_pdf_path}\n"
                f"Error: Dropbox upload failed\n"
                f"Signed At: {signature_request.signed_at.isoformat()}\n"
                f"Salesforce Case: {signature_request.salesforce_case_id}\n"
                f"Envelope ID: {signature_request.envelope_document_id or 'TBD'}"
            )

        # Salesforce update with Dropbox path (migration-safe)
        try:
            envelope_document_id = signature_request.envelope_document_id
            if not envelope_document_id:
                try:
                    envelope_document_id = find_envelope_id_by_token(signature_request.token)
                except Exception as e:
                    logger.warning(f"Could not find envelope by token (expected during migration): {e}")
                    envelope_document_id = None
            
            if envelope_document_id:
                signature_request.envelope_document_id = envelope_document_id
                session.commit()
                
                try:
                    update_envelope_document({
                        "dropbox_file_path__c": dropbox_path,  # Use Dropbox path instead of local path
                        "Envelope_Status__c": "Completed",
                        "Sign_Date__c": signature_request.signed_at.isoformat(),
                        "Expiration_Date__c": signature_request.expires_at.date().isoformat()
                    }, envelope_document_id)
                    logger.info(f"Salesforce updated for envelope {envelope_document_id} with Dropbox path: {dropbox_path}")
                    send_webhook_if_enabled(
                        f"✅ Salesforce updated successfully:\n"
                        f"Client: {signature_request.client_name}\n"
                        f"Envelope ID: {envelope_document_id}\n"
                        f"Dropbox Path: {dropbox_path}\n"
                        f"Status: Completed\n"
                        f"Sign Date: {signature_request.signed_at.isoformat()}\n"
                        f"Salesforce Case: {signature_request.salesforce_case_id}"
                    )
                except Exception as e:
                    logger.error(f"Failed to update Salesforce envelope {envelope_document_id}: {e}")
                    logger.info("Continuing with signing process despite Salesforce update failure")
            else:
                logger.warning("No envelope_document_id available for Salesforce update (expected during migration)")
                logger.info(f"Dropbox path would be: {dropbox_path}")
        except Exception as e:
            logger.error(f"Salesforce integration error: {e}")
            logger.info("Continuing with signing process despite Salesforce error")

        return jsonify({"redirect_url": f"/v1/sign/final/{token}"})
    except Exception:
        logger.exception("Error processing signature")
        return jsonify({"error": "Error saving signed document."}), 500


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


@signing_bp.route("/preview/<filename>", methods=["GET"])
def serve_prefilled_pdf(filename):
    """Serve preview PDF files for document preview."""
    try:
        preview_dir = os.path.abspath("preview")
        
        # First try direct path
        file_path = os.path.join(preview_dir, filename)
        
        # If not found, search in dated subdirectories
        if not os.path.exists(file_path):
            # Look for the file in dated subdirectories (YYYYMMDD format)
            for subdir in os.listdir(preview_dir):
                subdir_path = os.path.join(preview_dir, subdir)
                if os.path.isdir(subdir_path) and subdir.isdigit() and len(subdir) == 8:
                    potential_file = os.path.join(subdir_path, filename)
                    if os.path.exists(potential_file):
                        file_path = potential_file
                        break
        
        # Security check: ensure file is within preview directory tree
        if not os.path.commonpath([preview_dir, file_path]) == preview_dir:
            abort(403)
        
        if not os.path.exists(file_path):
            abort(404)
            
        return send_file(file_path, mimetype='application/pdf')
    except Exception:
        logger.exception(f"Error serving preview PDF: {filename}")
        abort(500)


@signing_bp.route("/signed/<filename>", methods=["GET"])
def serve_signed_pdf(filename):
    """Serve signed PDF files."""
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


@signing_bp.route("/download/<filename>", methods=["GET"])
def download_signed_pdf(filename):
    """Download signed PDF files as attachment."""
    signed_root = os.path.abspath("signed")
    for dated_folder in sorted(os.listdir(signed_root), reverse=True):
        candidate_path = os.path.join(signed_root, dated_folder, filename)
        if os.path.exists(candidate_path):
            try:
                return send_file(candidate_path, mimetype='application/pdf', as_attachment=True, download_name=filename)
            except Exception:
                logger.exception("Error downloading signed PDF")
                abort(500)
    logger.error(f"Signed file not found for download: {filename}")
    abort(404)


@signing_bp.route("/thank-you", methods=["GET"])
def thank_you():
    """Thank you page after signing completion."""
    token = request.args.get('token', '')
    client_name = "Client"  # Default fallback
    
    if token:
        try:
            session = get_session()
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()
            if signature_request:
                client_name = signature_request.client_name
        except Exception:
            logger.exception("Error retrieving client name for thank you page")
    
    return render_template("thank-you.html", client_name=client_name)