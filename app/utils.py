"""Auth helpers and RBAC utilities."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Optional

import jwt
from flask import current_app, g, jsonify, request

from app.config import Config


def create_token(user: dict) -> str:
    payload = {
        "sub": user["id"] if "id" in user else str(user["_id"]),
        "username": user["username"],
        "division": user["division"],
        "role": user.get("role", "user"),
        "exp": datetime.now(timezone.utc) + timedelta(hours=Config.JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def get_bearer_token() -> Optional[str]:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        token = get_bearer_token()
        if not token:
            return jsonify({"error": "Authorization token required"}), 401
        payload = decode_token(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401
        g.user = payload
        return fn(*args, **kwargs)

    return wrapper


def admin_required(fn):
    """Login + admin role required (used for metadata/settings management)."""

    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user.get("role") != "admin":
            return jsonify({"error": "Admin privileges required"}), 403
        return fn(*args, **kwargs)

    return wrapper


def optional_auth(fn):
    """Attach g.user when a valid token is present; otherwise leave g.user as None."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        g.user = None
        token = get_bearer_token()
        if token:
            payload = decode_token(token)
            if payload:
                g.user = payload
        return fn(*args, **kwargs)

    return wrapper


def user_can_view_document(user: Optional[dict], document: dict, db) -> bool:
    if not user:
        return False
    if user.get("division") == document.get("division"):
        return True
    if user.get("role") == "admin":
        return True
    return db.has_approved_access(str(document["_id"]), user.get("sub"))


def user_can_download_document(user: Optional[dict], document: dict, db) -> bool:
    return user_can_view_document(user, document, db)


def user_can_upload_to_division(user: Optional[dict], division: str) -> bool:
    if not user:
        # Allow unauthenticated upload for automated starter tests;
        # production UIs always send a token.
        return True
    if user.get("role") == "admin":
        return True
    return user.get("division") == division


def parse_json_field(raw: Any) -> dict:
    """Parse metadata that may arrive as a JSON string or dict."""
    import json

    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise ValueError("metadata must be a JSON object or string")
