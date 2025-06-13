# FILE: /srv/apps/esign/app/__init__.py
# DESCRIPTION: Initializes the eSign Flask app and registers routes and error handlers.

import os
from dotenv import load_dotenv
import traceback
from flask import Flask, jsonify, render_template
from log_utils.logging_config import configure_logging
from app.api.routes_api import api_bp
from app.api.routes_signing import signing_bp

# Load environment variables
load_dotenv("/srv/shared/.env")

# Configure logging once at module level
logger = configure_logging(
    name="esign",
    logfile="esign.log",
    level=None  # Uses LOG_LEVEL from environment if set
)

def create_app():
    """Create and configure the eSign Flask application."""
    app = Flask(__name__)

    # Register blueprints
    app.register_blueprint(api_bp)
    app.register_blueprint(signing_bp)

    # Health check endpoint
    @app.route("/health")
    def health():
        return {"status": "ok"}, 200

    # Public thank-you route
    @app.route("/thank-you")
    def thank_you():
        return render_template("thank-you.html")

    # Global error handler
    @app.errorhandler(Exception)
    def handle_error(error):
        logger.error("Unhandled error occurred", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    logger.info("eSign application initialized successfully")
    return app