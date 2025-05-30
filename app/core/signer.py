# ------------------------------------------------------------------------
# File: signer.py
# Location: /srv/apps/esign/app/core/signer.py
# Description:
#     This module handles the embedding of a base64-encoded signature image
#     onto a PDF template and saves the final signed document. It uses
#     reportlab to generate a transparent overlay and PyPDF2 to merge
#     the overlay with the original PDF. This function is called after a client
#     submits their electronic signature through the signing interface.
# ------------------------------------------------------------------------

import base64
import io
import logging
import os
import re
import json

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from shared.log_utils.logging_config import configure_logging
from PIL import Image
from datetime import datetime

with open("/srv/apps/esign/config/template_registry.json", "r") as f:
    TEMPLATE_REGISTRY = json.load(f)

logger = configure_logging(name="apps.esign.signer", logfile="esign.log", level=None)

def embed_signature_on_pdf(
    template_key: str,
    output_path: str,
    signature_b64: str,
    client_name: str,
    sign_date: str,
    test_mode: bool = False,
    smoke_test: bool = False,
    is_preview: bool = False
) -> str:
    try:
        logger.info("Starting signature embedding process.")
        if test_mode:
            logger.info("Test mode enabled. Output PDF will not be written.")
        if smoke_test:
            logger.info("Smoke test mode enabled. Will run decoding and PDF pipeline only.")

        # Validate sign_date is ISO format
        try:
            datetime.fromisoformat(sign_date)
        except ValueError:
            logger.error(f"Invalid sign_date format: {sign_date}")
            raise ValueError("sign_date must be an ISO-formatted string (YYYY-MM-DD)")

        template_info = TEMPLATE_REGISTRY.get(template_key)
        if not template_info:
            raise ValueError(f"Template key '{template_key}' not found in registry.")
        template_path = template_info["path"]
        signature_fields = template_info["signature_fields"]
        if not os.path.isfile(template_path):
            logger.error(f"Template file does not exist: {template_path}")
            raise FileNotFoundError(f"Template PDF not found: {template_path}")
        logger.info(f"Template PDF found: {template_path}")

        # --- Signature image handling ---
        if is_preview:
            # Use the generic signature image for preview
            generic_sig_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "assets", "signature_here.png"))
            if not os.path.isfile(generic_sig_path):
                logger.error(f"Generic signature image not found: {generic_sig_path}")
                raise FileNotFoundError(f"Generic signature image not found: {generic_sig_path}")
            signature_img = Image.open(generic_sig_path).convert("RGBA")
            logger.info("Using generic signature image for preview PDF.")
        else:
            # Normalize and extract Base64 data
            logger.debug(f"Raw signature input: {signature_b64[:30]!r}...")
            b64_data = signature_b64.strip()
            # If it's a Data‑URI, extract the part after "base64,"
            match = re.match(r"^data:.*?;base64,(.+)$", b64_data, re.IGNORECASE)
            if match:
                b64_data = match.group(1).strip()

            # Remove any whitespace or non-base64 characters
            b64_clean = re.sub(r'[^A-Za-z0-9+/=]', '', b64_data)

            # Add padding if necessary
            missing_padding = len(b64_clean) % 4
            if missing_padding:
                b64_clean += '=' * (4 - missing_padding)

            # Decode with validation
            try:
                signature_bytes = base64.b64decode(b64_clean, validate=True)
            except Exception as decode_err:
                logger.error(f"Failed to decode base64 signature: {decode_err}")
                raise ValueError("Unable to decode signature image") from decode_err

            try:
                signature_img = Image.open(io.BytesIO(signature_bytes)).convert("RGBA")
                signature_img.verify()  # validate image file format
                signature_img = Image.open(io.BytesIO(signature_bytes)).convert("RGBA")
            except Exception as decode_err:
                logger.error("Failed to decode and parse signature image.")
                raise ValueError("Invalid signature image format or corrupt data.") from decode_err
            logger.info("Signature image successfully decoded and verified.")

        overlay_buffers = {}
        for field in signature_fields:
            page = field["page"]
            if page not in overlay_buffers:
                overlay_buffers[page] = {
                    "buffer": io.BytesIO(),
                    "canvas": None
                }
                overlay_buffers[page]["canvas"] = canvas.Canvas(overlay_buffers[page]["buffer"], pagesize=letter)

        for field in signature_fields:
            c = overlay_buffers[field["page"]]["canvas"]
            x, y = field["x"], field["y"]
            label = field["label"].lower()
            if "signature" in label:
                c.drawImage(ImageReader(signature_img), x, y, width=field["width"], height=field["height"], mask='auto')
            elif "name" in label:
                c.setFont("Helvetica", 10)
                c.drawString(x, y, client_name)
            elif "date" in label:
                c.setFont("Helvetica", 10)
                c.drawString(x, y, sign_date)

        for key in overlay_buffers:
            overlay_buffers[key]["canvas"].save()
            overlay_buffers[key]["buffer"].seek(0)

        template_pdf = PdfReader(template_path)
        writer = PdfWriter()
        for i, page in enumerate(template_pdf.pages):
            page_number = i + 1
            if page_number in overlay_buffers:
                overlay_pdf = PdfReader(overlay_buffers[page_number]["buffer"])
                page.merge_page(overlay_pdf.pages[0])
            writer.add_page(page)

        if smoke_test:
            logger.info("Smoke test complete. PDF pipeline executed successfully.")
            return output_path

        if not test_mode:
            # Prepend last name and add timestamp to output filename
            last_name = client_name.strip().split()[-1].lower()
            output_dir = os.path.dirname(output_path)
            base_output_name = os.path.basename(output_path)
            timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
            name_part, ext_part = os.path.splitext(base_output_name)
            final_output_name = f"{last_name}_{template_key}_{name_part}_{timestamp_suffix}{ext_part}"
            output_path = os.path.join(output_dir, final_output_name)
            # Write the signed output PDF to the given path
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            logger.info(f"Signed PDF written to: {output_path}")
            return output_path
        # If test_mode, just return the intended output_path
        return output_path
    except Exception as e:
        logger.exception("Error embedding signature on PDF.")
        raise

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manual test runner for embed_signature_on_pdf")
    parser.add_argument("--template", required=True, help="Template key name from the registry")
    parser.add_argument("--output", required=True, help="Path to save the signed PDF")
    parser.add_argument("--signature", required=True, help="Path to a base64-encoded signature file (PNG)")
    parser.add_argument("--name", default="Test User", help="Client name")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Signing date (YYYY-MM-DD)")
    parser.add_argument("--test", action="store_true", help="Enable test mode (no write)")
    parser.add_argument("--smoke", action="store_true", help="Enable smoke test mode (no write)")

    args = parser.parse_args()

    with open(args.signature, "r") as sig_file:
        signature_data = sig_file.read().strip()

    # Add timestamp to output filename
    from datetime import datetime
    import os

    timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_output, ext = os.path.splitext(args.output)
    output_with_timestamp = f"{base_output}_{args.template}_{timestamp_suffix}{ext}"

    output = embed_signature_on_pdf(
        template_key=args.template,
        output_path=output_with_timestamp,
        signature_b64=signature_data,
        client_name=args.name,
        sign_date=args.date,
        test_mode=args.test,
        smoke_test=args.smoke
    )

    # Example test logic with updated variable usage
    # (Assuming this block is for manual testing and demonstration)
    if not args.test and not args.smoke:
        assert os.path.exists(output)
        assert os.path.getsize(output) > 1000
        # Cleanup after test
        if os.path.exists(output):
            os.remove(output)