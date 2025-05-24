"""
Entrypoint for the eSign application.
"""

import os
import sys
import traceback
from flask import jsonify
from app import create_app
from shared.log_utils.logging_config import configure_logging

# Configure logging first
logger = configure_logging(
    name="esign",
    logfile="esign.log",
    level=None  # Will use environment-based level
)

# Create the Flask application
app = create_app()

@app.errorhandler(Exception)
def handle_error(error):
    """Global error handler with standardized logging."""
    logger.error("Unhandled error:", exc_info=True)
    logger.error("Error type: %s", type(error).__name__)
    logger.error("Error message: %s", str(error))
    logger.error("Traceback: %s", traceback.format_exc())
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    port = int(os.getenv("FLASK_PORT", 5000))
    
    logger.info("Starting eSign application on port %d (debug: %s)", port, debug)
    app.run(debug=debug, port=port)