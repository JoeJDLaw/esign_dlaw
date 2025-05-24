

from flask import Flask
from app.api.routes_api import api_bp
from app.api.routes_signing import signing_bp

def create_app():
    app = Flask(__name__)
    app.register_blueprint(api_bp)
    app.register_blueprint(signing_bp)
    return app