"""Flask application factory for Triad AI Document Management System."""

from flask import Flask, send_from_directory
from flask_cors import CORS

from app.config import Config
from app.models import Database
from app.routes import api


def create_app(config_class=Config) -> Flask:
    app = Flask(
        __name__,
        static_folder="../frontend",
        static_url_path="",
    )
    app.config.from_object(config_class)
    app.config["MAX_CONTENT_LENGTH"] = config_class.UPLOAD_MAX_BYTES

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    database = Database(app.config["MONGO_URI"])
    app.extensions["db"] = database

    app.register_blueprint(api)

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.errorhandler(404)
    def not_found(err):  # noqa: ARG001
        # SPA fallback for non-API routes
        from flask import request

        if request.path.startswith("/api/"):
            return {"error": "Not found"}, 404
        return send_from_directory(app.static_folder, "index.html")

    return app
