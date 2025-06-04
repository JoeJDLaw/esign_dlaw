# ------------------------------------------------------------------------
# File: pdf_loader.py
# Location: /srv/apps/esign/app/core/pdf_loader.py
# Description:
#     This module handles loading of PDF templates for e-signature flows.
#     It selects the appropriate document based on the template_type
#     provided in the signature request payload. This module may be
#     extended to inject prefilled data or manage page-specific logic.
# ------------------------------------------------------------------------

import os
import json
import logging
from log_utils.logging_config import configure_logging

logger = configure_logging(name="apps.esign.pdf_loader", logfile="esign.log", level=None)

# Load the centralized template registry
REGISTRY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "config", "template_registry.json"))

try:
    with open(REGISTRY_PATH, "r") as f:
        TEMPLATE_REGISTRY = json.load(f)
    logger.info(f"Loaded template registry with {len(TEMPLATE_REGISTRY)} entries")
except Exception as e:
    logger.exception(f"Failed to load template registry: {e}")
    TEMPLATE_REGISTRY = {}

# Define the app root so we can resolve paths relative to /srv/apps/esign
APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def get_template_path(template_type: str) -> str:
    """
    Returns the file path of the PDF template corresponding to the given template_type.
    Raises ValueError if the type is not recognized or the file is missing.
    """
    if template_type not in TEMPLATE_REGISTRY:
        logger.error(f"Invalid template_type requested: {template_type}")
        raise ValueError(f"Unknown template type: {template_type}")

    relative_path = TEMPLATE_REGISTRY[template_type]["path"]
    path = os.path.join(APP_ROOT, relative_path)
    if not os.path.isfile(path):
        logger.error(f"Template file does not exist: {path}")
        raise FileNotFoundError(f"Template PDF not found at: {path}")

    logger.info(f"Resolved template path for type '{template_type}': {path}")
    return path

def smoke_test() -> None:
    logger.info("Starting pdf_loader smoke test...")
    for key in TEMPLATE_REGISTRY:
        try:
            path = get_template_path(key)
            logger.info(f"✔ Template for '{key}' resolved at: {path}")
        except Exception as e:
            logger.error(f"❌ Smoke test failed for template '{key}': {e}")

if __name__ == "__main__":
    smoke_test()
    print("Smoke test completed. Check logs.")