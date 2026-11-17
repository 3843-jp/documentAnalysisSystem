
import os
from dotenv import load_dotenv

# Load environment variables from the project's .env file
load_dotenv()


class Config:
    # Security
    SECRET_KEY = os.environ.get("SECRET_KEY", "triad-ai-dms-dev-secret-change-me")

    # MongoDB Atlas connection
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/dms")

    # JWT token expiry (in hours)
    JWT_EXPIRY_HOURS = int(
        os.environ.get(
            "TOKEN_TTL_HOURS",
            os.environ.get("JWT_EXPIRY_HOURS", "24")
        )
    )

    # Maximum file upload size (default: 25 MB)
    UPLOAD_MAX_BYTES = int(
        os.environ.get(
            "MAX_CONTENT_LENGTH",
            os.environ.get("UPLOAD_MAX_BYTES", str(25 * 1024 * 1024))
        )
    )

    # Default divisions
    DEFAULT_DIVISIONS = [
        "Division A",
        "Division B",
        "Division C"
    ]

    # Default metadata fields
    DEFAULT_METADATA_FIELDS = [
        {
            "name": "Division",
            "options": ["Division A", "Division B", "Division C"]
        },
        {
            "name": "Report Type",
            "options": ["Financial", "Technical", "HR", "Operations"]
        },
    ]
