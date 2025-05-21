# File: /srv/apps/esign/run.py
import logging
import sys
import traceback
from flask import Flask, jsonify
from app.api.routes_api import api_bp

# Configure logging to stderr with more detail
logging.basicConfig(
    stream=sys.stderr,
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s: %(message)s\n%(pathname)s:%(lineno)d'
)

app = Flask(__name__)
app.register_blueprint(api_bp)

@app.errorhandler(Exception)
def handle_error(error):
    # Log the full traceback
    app.logger.error("Unhandled error:", exc_info=True)
    app.logger.error(f"Error type: {type(error).__name__}")
    app.logger.error(f"Error message: {str(error)}")
    app.logger.error(f"Traceback: {traceback.format_exc()}")
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(debug=True)