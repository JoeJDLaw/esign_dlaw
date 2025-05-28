# File: /srv/apps/esign/app/__init__.py


import traceback
from flask import jsonify
from shared.log_utils.logging_config import configure_logging

from flask import Flask
from app.api.routes_api import api_bp
from app.api.routes_signing import signing_bp

logger = configure_logging(name="esign", logfile="esign.log", level=None)

def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.register_blueprint(signing_bp)

    @app.route("/thank-you")
    def thank_you():
        from flask import render_template
        return render_template("thank-you.html")

    @app.errorhandler(Exception)
    def handle_error(error):
        """Global error handler with standardized logging."""
        logger.error("Unhandled error:", exc_info=True)
        logger.error("Error type: %s", type(error).__name__)
        logger.error("Error message: %s", str(error))
        logger.error("Traceback: %s", traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500
    return app