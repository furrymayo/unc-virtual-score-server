import base64

from flask import Flask

from .config import CONFIG


def create_app():
    app = Flask(__name__, template_folder="Templates", static_folder="static")
    app.config["SECRET_KEY"] = CONFIG.flask_secret_key

    from .views import views
    from .sports import sports
    from .api import api

    app.register_blueprint(views, url_prefix="/")
    app.register_blueprint(sports, url_prefix="/")
    app.register_blueprint(api, url_prefix="/")

    # Make API auth token available to all templates for JS config fetches
    _token = base64.b64encode(
        f"{CONFIG.admin_user}:{CONFIG.admin_pass}".encode()
    ).decode()

    @app.context_processor
    def inject_api_auth():
        return {"api_auth_token": _token}

    return app
