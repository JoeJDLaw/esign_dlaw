# File: /srv/apps/esign/app/api/routes_signing.py


from flask import Blueprint, render_template, abort
from app.db.session import get_session
from app.db.models import SignatureRequest, SignatureStatus
from datetime import datetime
import hashlib

signing_bp = Blueprint("esign_signing", __name__, url_prefix="/esign/sign")

@signing_bp.route("/<token>", methods=["GET"])
def sign_document(token):
    session = get_session()
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    signature_request = session.query(SignatureRequest).filter_by(token_hash=token_hash).first()

    if not signature_request:
        abort(404)

    if signature_request.status != SignatureStatus.pending:
        return "This document is no longer available for signing.", 403

    if signature_request.expires_at < datetime.utcnow():
        return "This link has expired.", 403

    return render_template("sign.html", client_name=signature_request.client_name, token=token)