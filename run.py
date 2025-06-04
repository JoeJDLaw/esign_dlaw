# FILE: /srv/apps/esign/run.py
# DESCRIPTION: Run the eSign application (production entrypoint for Gunicorn).

"""
Entrypoint for the eSign application.
Used by Gunicorn to start the app server.
"""

import os
from app import create_app
from log_utils.logging_config import configure_logging

# Configure logging first
logger = configure_logging(
    name="esign",
    logfile="esign.log",
    level=None  # Will use LOG_LEVEL from .env if present
)

# Create the Flask application
app = create_app()