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

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from shared.log_utils.logging_config import configure_logging
from PIL import Image
from datetime import datetime

logger = configure_logging(name="apps.esign.signer", logfile="esign.log", level=None)

def embed_signature_on_pdf(
    template_path: str,
    output_path: str,
    signature_b64: str,
    client_name: str,
    sign_date: str,
    signature_coords: tuple[int, int] = (100, 100),
    name_coords: tuple[int, int] = (100, 150),
    test_mode: bool = False,
    smoke_test: bool = False
) -> None:
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

        # Validate that the template PDF exists
        if not os.path.isfile(template_path):
            logger.error(f"Template file does not exist: {template_path}")
            raise FileNotFoundError(f"Template PDF not found: {template_path}")
        logger.info(f"Template PDF found: {template_path}")

        # Decode the base64 signature string
        try:
            signature_bytes = base64.b64decode(signature_b64.split(",")[-1])
            signature_img = Image.open(io.BytesIO(signature_bytes))
            signature_img.verify()  # validate image file format
            signature_img = Image.open(io.BytesIO(signature_bytes))  # re-open after verify
        except Exception as decode_err:
            logger.error("Failed to decode and parse signature image.")
            raise ValueError("Invalid signature image format or corrupt base64 string.") from decode_err
        logger.info("Signature image successfully decoded and verified.")

        # Create a PDF overlay in memory with the signature and client name/date
        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=letter)

        # Draw the signature image at the given coordinates
        c.drawImage(ImageReader(signature_img), *signature_coords, width=200, height=50)

        # Draw the client name and signing date
        c.setFont("Helvetica", 10)
        c.drawString(*name_coords, f"{client_name} - {sign_date}")
        c.save()
        logger.info("Overlay PDF with signature and name created.")

        # Read both the original template and the overlay PDF
        overlay_buffer.seek(0)
        overlay_pdf = PdfReader(overlay_buffer)
        template_pdf = PdfReader(template_path)
        writer = PdfWriter()

        # Merge the overlay page onto the template's first page
        base_page = template_pdf.pages[0]
        base_page.merge_page(overlay_pdf.pages[0])
        writer.add_page(base_page)

        if smoke_test:
            logger.info("Smoke test complete. PDF pipeline executed successfully.")
            return

        if not test_mode:
            # Write the signed output PDF to the given path
            with open(output_path, "wb") as f_out:
                writer.write(f_out)
            logger.info(f"Signed PDF written to: {output_path}")
    except Exception as e:
        logger.exception("Error embedding signature on PDF.")
        raise

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manual test runner for embed_signature_on_pdf")
    parser.add_argument("--template", required=True, help="Path to the template PDF file")
    parser.add_argument("--output", required=True, help="Path to save the signed PDF")
    parser.add_argument("--signature", required=True, help="Path to a base64-encoded signature file (PNG)")
    parser.add_argument("--name", default="Test User", help="Client name")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="Signing date (YYYY-MM-DD)")
    parser.add_argument("--test", action="store_true", help="Enable test mode (no write)")
    parser.add_argument("--smoke", action="store_true", help="Enable smoke test mode (no write)")

    args = parser.parse_args()

    with open(args.signature, "r") as sig_file:
        signature_data = sig_file.read().strip()

    embed_signature_on_pdf(
        template_path=args.template,
        output_path=args.output,
        signature_b64=signature_data,
        client_name=args.name,
        sign_date=args.date,
        test_mode=args.test,
        smoke_test=args.smoke
    )