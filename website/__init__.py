import os
import secrets

from flask import Flask


def create_app():
    app = Flask(__name__, template_folder="Templates", static_folder="static")
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

    from .views import views
    from .sports import sports
    from .api import api

    app.register_blueprint(views, url_prefix="/")
    app.register_blueprint(sports, url_prefix="/")
    app.register_blueprint(api, url_prefix="/")

    return app
