

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
import logging
from shared.log_utils.logging_config import configure_logging

logger = configure_logging(name="apps.esign.pdf_loader", logfile="esign.log", level=None)

TEMPLATE_MAP = {
    # Primary identifiers
    "cea": "tests/sample_data/cea.pdf",
    "cea_rra": "tests/sample_data/cea_rra.pdf",

    # Legacy or alias identifiers
    "case_eval": "tests/sample_data/cea.pdf",
    "case_eval_plus_records": "tests/sample_data/cea_rra.pdf"
}

def get_template_path(template_type: str) -> str:
    """
    Returns the file path of the PDF template corresponding to the given template_type.
    Raises ValueError if the type is not recognized or the file is missing.
    """
    if template_type not in TEMPLATE_MAP:
        logger.error(f"Invalid template_type requested: {template_type}")
        raise ValueError(f"Unknown template type: {template_type}")

    path = os.path.abspath(TEMPLATE_MAP[template_type])
    if not os.path.isfile(path):
        logger.error(f"Template file does not exist: {path}")
        raise FileNotFoundError(f"Template PDF not found at: {path}")

    logger.info(f"Resolved template path for type '{template_type}': {path}")
    return path
def smoke_test() -> None:
    logger.info("Starting pdf_loader smoke test...")
    for key, _ in TEMPLATE_MAP.items():
        try:
            path = get_template_path(key)
            logger.info(f"✔ Template for '{key}' resolved at: {path}")
        except Exception as e:
            logger.error(f"❌ Smoke test failed for template '{key}': {e}")

if __name__ == "__main__":
    smoke_test()