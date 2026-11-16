import os

DEV_SECRET_KEY = "triad-ai-dms-dev-secret-change-me"


def _env_flag(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


class Config:
    # Falls back to a dev-only key; create_app() warns when it is in use.
    SECRET_KEY = os.environ.get("SECRET_KEY") or DEV_SECRET_KEY
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/dms")
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    UPLOAD_MAX_BYTES = int(os.environ.get("UPLOAD_MAX_BYTES", str(25 * 1024 * 1024)))

    # Only for running the original starter test_api.py, which uploads without a token.
    ALLOW_ANONYMOUS_UPLOAD = _env_flag("ALLOW_ANONYMOUS_UPLOAD")

    # Optional admin account created (or promoted) on startup.
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "").strip()
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
    ADMIN_DIVISION = os.environ.get("ADMIN_DIVISION", "Division A").strip()

    DEFAULT_DIVISIONS = ["Division A", "Division B", "Division C"]
    DEFAULT_METADATA_FIELDS = [
        {"name": "Division", "options": ["Division A", "Division B", "Division C"]},
        {"name": "Report Type", "options": ["Financial", "Technical", "HR", "Operations"]},
    ]
