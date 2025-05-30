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
import json

REGISTRY_PATH = "/srv/apps/esign/config/template_registry.json"
SAMPLE_DATA_DIR = "/srv/apps/esign/tests/sample_data"

with open(REGISTRY_PATH, "r") as f:
    registry = json.load(f)

TEMPLATES_TO_TEST = [
    key for key, entry in registry.items()
    if os.path.isfile(os.path.join(SAMPLE_DATA_DIR, os.path.basename(entry["path"])))
]

from shared.log_utils.logging_config import configure_logging

# Configure logger for test output
logger = configure_logging(name="apps.esign.tests.signer", logfile="esign.log", level=None)

# Whether to keep generated PDF files after test (set True to inspect outputs)
KEEP_FILES = True  # Set to True to keep generated PDF files for inspection

# Sample setup for test paths (template-agnostic)
SIGNATURE_PATH = "/srv/apps/esign/tests/sample_data/signature.txt"
OUTPUT_PATH = "/srv/apps/esign/tests/sample_exports/test_signed_output.pdf"


@pytest.mark.parametrize("template_key", TEMPLATES_TO_TEST)
@pytest.mark.skipif(not os.path.isfile(SIGNATURE_PATH), reason="Signature file is missing")
def test_embed_signature_smoke(template_key):
    """Smoke test for signature embedding logic using test_mode=True"""
    with open(SIGNATURE_PATH, "r") as f:
        signature_b64 = f.read().strip()

    try:
        embed_signature_on_pdf(
            template_key=template_key,
            output_path=OUTPUT_PATH,
            signature_b64=signature_b64,
            client_name="Test User",
            sign_date=datetime.now().strftime("%Y-%m-%d"),
            test_mode=True
        )
        logger.info(f"Smoke test passed for {template_key}.")
    except Exception as e:
        logger.exception(f"Smoke test failed for {template_key}.")
        pytest.fail(f"{template_key}: embed_signature_on_pdf raised an exception: {e}")

@pytest.mark.parametrize("template_key", TEMPLATES_TO_TEST)
@pytest.mark.skipif(not os.path.isfile(SIGNATURE_PATH), reason="Signature file is missing")
def test_embed_signature_writes_file(template_key):
    """Functional test to ensure the signed PDF file is written and non-empty"""
    with open(SIGNATURE_PATH, "r") as f:
        signature_b64 = f.read().strip()

    try:
        actual_output_path = embed_signature_on_pdf(
            template_key=template_key,
            output_path=OUTPUT_PATH,
            signature_b64=signature_b64,
            client_name="Test User",
            sign_date=datetime.now().strftime("%Y-%m-%d"),
            test_mode=False
        )
        assert os.path.exists(actual_output_path), f"{template_key}: Signed PDF file was not created"
        assert os.path.getsize(actual_output_path) > 1000, f"{template_key}: Output file too small"
        logger.info(f"File output test passed for {template_key}.")
    except Exception as e:
        logger.exception(f"File output test failed for {template_key}.")
        pytest.fail(f"{template_key}: embed_signature_on_pdf raised an exception: {e}")
    finally:
        if not KEEP_FILES and os.path.exists(actual_output_path):
            os.remove(actual_output_path)
            logger.info("Cleaned up test output file.")