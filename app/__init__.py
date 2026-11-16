"""Flask application factory for Triad AI Document Management System."""

from flask import Flask, send_from_directory
from flask_cors import CORS

from app.config import DEV_SECRET_KEY, Config
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

    if app.config["SECRET_KEY"] == DEV_SECRET_KEY:
        app.logger.warning("SECRET_KEY is not set; using the insecure development key.")

    database = Database(app.config["MONGO_URI"])
    app.extensions["db"] = database

    if app.config["ADMIN_USERNAME"]:
        if app.config["ADMIN_PASSWORD"]:
            database.ensure_admin(
                app.config["ADMIN_USERNAME"],
                app.config["ADMIN_PASSWORD"],
                app.config["ADMIN_DIVISION"],
            )
        else:
            app.logger.warning("ADMIN_USERNAME is set without ADMIN_PASSWORD; no admin created.")

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
