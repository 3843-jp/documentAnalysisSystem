import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "triad-ai-dms-dev-secret-change-me")
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/dms")
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    UPLOAD_MAX_BYTES = int(os.environ.get("UPLOAD_MAX_BYTES", str(25 * 1024 * 1024)))
    DEFAULT_DIVISIONS = ["Division A", "Division B", "Division C"]
    DEFAULT_METADATA_FIELDS = [
        {"name": "Division", "options": ["Division A", "Division B", "Division C"]},
        {"name": "Report Type", "options": ["Financial", "Technical", "HR", "Operations"]},
    ]
