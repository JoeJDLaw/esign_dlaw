# FILE: /srv/apps/esign/run.py
# DESCRIPTION: Run the eSign application.
import sys
sys.path.insert(0, "/srv/shared")

"""
Entrypoint for the eSign application.
"""

import os
import traceback
from flask import jsonify
from app import create_app
from log_utils.logging_config import configure_logging

# Configure logging first
logger = configure_logging(
    name="esign",
    logfile="esign.log",
    level=None  # Will use environment-based level
)

# Create the Flask application
app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("FLASK_PORT", 5000))
    
    logger.info("Starting eSign application on port %d (debug: %s)", port, debug)
    app.run(debug=debug, port=port)