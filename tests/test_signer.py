

# ------------------------------------------------------------------------
# File: test_signer.py
# Location: /srv/apps/esign/tests/test_signer.py
# Description:
#     Unit tests for signer.py, verifying PDF signature embedding behavior,
#     base64 decoding, and merge logic. Uses test_mode to skip file I/O.
# ------------------------------------------------------------------------

import base64
import os
import pytest
from datetime import datetime
from app.core.signer import embed_signature_on_pdf

from shared.log_utils.logging_config import configure_logging

# Configure logger for test output
logger = configure_logging(name="apps.esign.tests.signer", logfile="esign.log", level=None)

# Sample setup for test paths
TEMPLATE_PATH = "/srv/apps/esign/tests/sample_data/cea.pdf"
SIGNATURE_PATH = "/srv/apps/esign/tests/sample_data/signature.txt"
OUTPUT_PATH = "/tmp/test_signed_output.pdf"

# Smoke test to validate PDF signature embedding logic
@pytest.mark.skipif(not os.path.isfile(TEMPLATE_PATH), reason="Template PDF is missing")
@pytest.mark.skipif(not os.path.isfile(SIGNATURE_PATH), reason="Signature file is missing")
def test_embed_signature_smoke():
    """Smoke test for signature embedding logic using test_mode=True"""
    # Read base64 signature from file
    with open(SIGNATURE_PATH, "r") as f:
        signature_b64 = f.read().strip()

    try:
        # Call the embed_signature_on_pdf function with test_mode to avoid file I/O
        embed_signature_on_pdf(
            template_path=TEMPLATE_PATH,
            output_path=OUTPUT_PATH,
            signature_b64=signature_b64,
            client_name="Test User",
            sign_date=datetime.now().strftime("%Y-%m-%d"),
            test_mode=True
        )
        logger.info("Smoke test passed without exception.")
    except Exception as e:
        logger.exception("Smoke test failed with exception.")
        pytest.fail(f"embed_signature_on_pdf raised an exception: {e}")
@pytest.mark.skipif(not os.path.isfile(TEMPLATE_PATH), reason="Template PDF is missing")
@pytest.mark.skipif(not os.path.isfile(SIGNATURE_PATH), reason="Signature file is missing")
def test_embed_signature_writes_file():
    """Functional test to ensure the signed PDF file is written and non-empty"""
    with open(SIGNATURE_PATH, "r") as f:
        signature_b64 = f.read().strip()

    try:
        embed_signature_on_pdf(
            template_path=TEMPLATE_PATH,
            output_path=OUTPUT_PATH,
            signature_b64=signature_b64,
            client_name="Test User",
            sign_date=datetime.now().strftime("%Y-%m-%d"),
            test_mode=False
        )
        assert os.path.exists(OUTPUT_PATH), "Signed PDF file was not created"
        assert os.path.getsize(OUTPUT_PATH) > 1000, "Signed PDF file is too small or empty"
        logger.info("File output test passed and output file verified.")
    except Exception as e:
        logger.exception("File output test failed.")
        pytest.fail(f"embed_signature_on_pdf raised an exception: {e}")
    finally:
        if os.path.exists(OUTPUT_PATH):
            os.remove(OUTPUT_PATH)
            logger.info("Cleaned up test output file.")