# File: /srv/apps/esign/app/api/routes_signing.py

import sys
sys.path.insert(0, "/srv/shared")
from shared.log_utils.logging_config import configure_logging
logger = configure_logging("apps.esign.routes_signing", "esign.log")

from flask import Blueprint, render_template, abort, request
from app.db.session import get_session
from app.db.models import SignatureRequest, SignatureStatus
from datetime import datetime, timezone
import hashlib
from app.core.pdf_loader import get_template_path

# Imports for POST route
from app.core.signer import embed_signature_on_pdf
import os

signing_bp = Blueprint("esign_signing", __name__, url_prefix="/v1/sign")

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

    try:
        template_path = get_template_path(signature_request.template_type)
        logger.info(f"Template path resolved for signing: {template_path}")
    except Exception as e:
        logger.error(f"Failed to resolve template for type '{signature_request.template_type}': {e}")
        return "An error occurred while preparing the document.", 500

    # This is where the signature embedding would occur:
    # signer.embed_signature_on_pdf(template_path, ...)

    logger.info(f"Rendering signature page for client: {signature_request.client_name}")
    return render_template("sign.html", client_name=signature_request.client_name, token=token)


# POST route for submitting the signature
@signing_bp.route("/<token>", methods=["POST"])
def submit_signature(token):
    logger.info(f"Processing submitted signature for token: {token[:8]}...")
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request:
        logger.warning(f"Signature request not found for token: {token[:8]}...")
        abort(404)

    if signature_request.status != SignatureStatus.pending:
        logger.warning(f"Document already signed or invalid. Token: {token[:8]}..., Status: {signature_request.status}")
        return "This document is no longer available for signing.", 403

    if signature_request.expires_at < datetime.now(timezone.utc):
        logger.warning(f"Signature link expired. Token: {token[:8]}..., Expires: {signature_request.expires_at}")
        return "This link has expired.", 403

    signature_b64 = request.form.get("signature")
    if not signature_b64:
        logger.warning(f"Signature missing in form submission. Token: {token[:8]}...")
        return "Missing signature data.", 400

    try:
        template_path = get_template_path(signature_request.template_type)
        output_dir = os.path.abspath("signed")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{token_hash[:8]}_signed.pdf")

        embed_signature_on_pdf(
            template_path=template_path,
            output_path=output_path,
            signature_b64=signature_b64,
            client_name=signature_request.client_name,
            sign_date=datetime.utcnow().strftime("%Y-%m-%d"),
        )

        signature_request.status = SignatureStatus.signed
        signature_request.signed_at = datetime.utcnow()
        signature_request.pdf_path = output_path
        signature_request.signed_ip = request.remote_addr
        signature_request.user_agent = request.headers.get("User-Agent", "")
        session.commit()

        logger.info(f"Signature successfully processed. File saved: {output_path}")
        return render_template("thank-you.html", client_name=signature_request.client_name)

    except Exception as e:
        logger.exception(f"Error while processing signature for token: {token[:8]}...")
        return "An error occurred while saving the signed document.", 500