"""REST API routes for the Document Management System."""

from __future__ import annotations

import io
import json

from bson import ObjectId
from flask import Blueprint, current_app, g, jsonify, request, send_file

from app.config import Config
from app.ocr import extract_text
from app.utils import (
    admin_required,
    create_token,
    login_required,
    optional_auth,
    parse_json_field,
    user_can_download_document,
    user_can_upload_to_division,
)

api = Blueprint("api", __name__, url_prefix="/api")


def db():
    return current_app.extensions["db"]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@api.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    division = (data.get("division") or "").strip()

    if not username or not password or not division:
        return jsonify({"error": "username, password, and division are required"}), 400
    if division not in Config.DEFAULT_DIVISIONS:
        # Still allow custom divisions that may have been added via metadata options
        field = db().find_metadata_field_by_name("Division")
        allowed = (field or {}).get("options") or Config.DEFAULT_DIVISIONS
        if division not in allowed:
            return jsonify({"error": f"Invalid division. Allowed: {allowed}"}), 400

    if db().find_user_by_username(username):
        return jsonify({"error": "Username already exists"}), 409

    user = db().create_user(username, password, division)
    token = create_token(user)
    return jsonify({"message": "Registered successfully", "token": token, "user": user}), 201


@api.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user_doc = db().find_user_by_username(username)
    if not user_doc or not db().verify_password(user_doc, password):
        return jsonify({"error": "Invalid credentials"}), 401

    user = db().serialize_user(user_doc)
    token = create_token(user)
    return jsonify({"message": "Login successful", "token": token, "user": user}), 200


@api.get("/auth/me")
@login_required
def me():
    user_doc = db().find_user_by_id(g.user["sub"])
    if not user_doc:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"user": db().serialize_user(user_doc)}), 200


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
@api.post("/documents/upload")
@optional_auth
def upload_document():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "empty file"}), 400

    try:
        metadata = parse_json_field(request.form.get("metadata"))
    except (json.JSONDecodeError, ValueError) as exc:
        return jsonify({"error": f"Invalid metadata JSON: {exc}"}), 400

    if not isinstance(metadata, dict):
        return jsonify({"error": "metadata must be a JSON object"}), 400

    requested = metadata.get("Division") or metadata.get("division")
    metadata.pop("division", None)

    if g.user:
        # RBAC: users upload only to their own division (admins may choose one)
        division = requested or g.user["division"]
        if not user_can_upload_to_division(g.user, division):
            return jsonify({"error": "You can only upload documents to your own division"}), 403
        uploaded_by = g.user["sub"]
    else:
        # Anonymous upload exists only for the starter test script; it can be
        # switched off with ALLOW_ANONYMOUS_UPLOAD=false.
        if not getattr(Config, "ALLOW_ANONYMOUS_UPLOAD", True):
            return jsonify({"error": "Authentication required"}), 401
        division = requested
        if not division:
            return jsonify({"error": "Division is required in metadata when unauthenticated"}), 400
        uploaded_by = None
    metadata["Division"] = division

    file_bytes = file.read()
    if not file_bytes:
        return jsonify({"error": "empty file"}), 400
    if len(file_bytes) > Config.UPLOAD_MAX_BYTES:
        return jsonify({"error": "File too large"}), 413

    content_type = file.mimetype or "application/octet-stream"
    ocr_text = extract_text(file_bytes, filename=file.filename, content_type=content_type)

    gridfs_id = db().store_file(io.BytesIO(file_bytes), file.filename, content_type)
    document = db().create_document(
        filename=file.filename,
        content_type=content_type,
        gridfs_id=gridfs_id,
        metadata=metadata,
        division=division,
        uploaded_by=uploaded_by,
        ocr_text=ocr_text,
    )
    return jsonify({"message": "Document uploaded", "document": document}), 201


@api.get("/documents")
@login_required
def list_documents():
    # Build filters from query params (supports ?Report Type=Financial and ?division=...)
    filters = {}
    for key, value in request.args.items():
        if key in ("page", "limit"):
            continue
        filters[key] = value

    # Default scope: own division + approved docs. ?Division=X browses another
    # division (metadata only) so users can find documents to request.
    docs = db().list_documents(filters, g.user)

    enriched = []
    for doc in docs:
        raw = db().find_document(doc["id"])
        can_download = user_can_download_document(g.user, raw, db())
        same_division = g.user.get("division") == doc.get("division")
        has_pending = False
        if not can_download:
            pending = db().db.access_requests.find_one(
                {
                    "doc_id": doc["id"],
                    "requester_id": g.user["sub"],
                    "status": "pending",
                }
            )
            has_pending = pending is not None
        enriched.append(
            {
                **doc,
                "can_download": can_download,
                "same_division": same_division,
                "access_pending": has_pending,
            }
        )
    return jsonify({"documents": enriched, "count": len(enriched)}), 200


@api.get("/documents/<doc_id>")
@login_required
def get_document(doc_id: str):
    raw = db().find_document(doc_id)
    if not raw:
        return jsonify({"error": "Document not found"}), 404

    can_download = user_can_download_document(g.user, raw, db())
    same_division = g.user.get("division") == raw.get("division")
    pending = db().db.access_requests.find_one(
        {"doc_id": doc_id, "requester_id": g.user["sub"], "status": "pending"}
    )
    payload = db().serialize_document(raw, include_ocr=can_download)
    payload.update(
        {
            "can_download": can_download,
            "same_division": same_division,
            "access_pending": pending is not None,
        }
    )
    return jsonify({"document": payload}), 200


@api.get("/documents/<doc_id>/download")
@login_required
def download_document(doc_id: str):
    raw = db().find_document(doc_id)
    if not raw:
        return jsonify({"error": "Document not found"}), 404

    if not user_can_download_document(g.user, raw, db()):
        return jsonify({"error": "Access denied. Request access from the document's division."}), 403

    try:
        grid_file = db().get_file(ObjectId(raw["gridfs_id"]) if not isinstance(raw["gridfs_id"], ObjectId) else raw["gridfs_id"])
    except Exception:  # noqa: BLE001
        return jsonify({"error": "File missing from storage"}), 404

    return send_file(
        io.BytesIO(grid_file.read()),
        mimetype=raw.get("content_type") or "application/octet-stream",
        as_attachment=True,
        download_name=raw.get("filename") or "document",
    )


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------
@api.post("/access/request")
@login_required
def request_access():
    data = request.get_json(silent=True) or {}
    doc_id = data.get("doc_id")
    if not doc_id:
        return jsonify({"error": "doc_id is required"}), 400

    raw = db().find_document(doc_id)
    if not raw:
        return jsonify({"error": "Document not found"}), 404

    if g.user.get("division") == raw.get("division"):
        return jsonify({"error": "You already have access to documents in your division"}), 400

    if db().has_approved_access(doc_id, g.user["sub"]):
        return jsonify({"error": "Access already approved"}), 400

    access_req = db().create_access_request(doc_id, g.user["sub"], g.user["division"])
    return jsonify({"message": "Access request submitted", "request": access_req}), 201


@api.post("/access/approve")
@login_required
def approve_access():
    data = request.get_json(silent=True) or {}
    request_id = data.get("request_id")
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400

    access_req = db().find_access_request(request_id)
    if not access_req:
        return jsonify({"error": "Access request not found"}), 404
    if access_req.get("status") != "pending":
        return jsonify({"error": f"Request is already {access_req.get('status')}"}), 400

    document = db().find_document(access_req["doc_id"])
    if not document:
        return jsonify({"error": "Document no longer exists"}), 404

    if g.user.get("division") != document.get("division") and g.user.get("role") != "admin":
        return jsonify({"error": "Only users in the document's division can approve"}), 403

    updated = db().update_access_request(request_id, "approved", g.user["sub"])
    return jsonify({"message": "Access approved", "request": updated}), 200


@api.post("/access/reject")
@login_required
def reject_access():
    data = request.get_json(silent=True) or {}
    request_id = data.get("request_id")
    if not request_id:
        return jsonify({"error": "request_id is required"}), 400

    access_req = db().find_access_request(request_id)
    if not access_req:
        return jsonify({"error": "Access request not found"}), 404
    if access_req.get("status") != "pending":
        return jsonify({"error": f"Request is already {access_req.get('status')}"}), 400

    document = db().find_document(access_req["doc_id"])
    if not document:
        return jsonify({"error": "Document no longer exists"}), 404

    if g.user.get("division") != document.get("division") and g.user.get("role") != "admin":
        return jsonify({"error": "Only users in the document's division can reject"}), 403

    updated = db().update_access_request(request_id, "rejected", g.user["sub"])
    return jsonify({"message": "Access rejected", "request": updated}), 200


@api.get("/access/requests")
@login_required
def list_access_requests():
    incoming = db().list_access_requests_for_division(g.user["division"])
    outgoing = db().list_access_requests_by_user(g.user["sub"])
    return jsonify({"incoming": incoming, "outgoing": outgoing}), 200


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
@api.get("/search")
@login_required
def search():
    q = request.args.get("q", "")
    results = db().search_documents(q, g.user)
    enriched = []
    for doc in results:
        raw = db().find_document(doc["id"])
        enriched.append(
            {
                **doc,
                "can_download": user_can_download_document(g.user, raw, db()),
                "same_division": g.user.get("division") == doc.get("division"),
            }
        )
    return jsonify({"query": q, "results": enriched, "count": len(enriched)}), 200


# ---------------------------------------------------------------------------
# Metadata / Admin settings
# ---------------------------------------------------------------------------
@api.get("/metadata/fields")
@login_required
def list_metadata_fields():
    return jsonify({"fields": db().list_metadata_fields()}), 200


@api.post("/metadata/fields")
@admin_required
def create_metadata_field():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    options = data.get("options") or []
    if not name:
        return jsonify({"error": "name is required"}), 400
    if db().find_metadata_field_by_name(name):
        return jsonify({"error": "Field already exists"}), 409
    field = db().create_metadata_field(name, options)
    return jsonify({"message": "Field created", "field": field}), 201


@api.put("/metadata/fields/<field_id>")
@admin_required
def update_metadata_field(field_id: str):
    data = request.get_json(silent=True) or {}
    updated = db().update_metadata_field(field_id, data.get("name"), data.get("options"))
    if not updated:
        return jsonify({"error": "Field not found"}), 404
    return jsonify({"message": "Field updated", "field": updated}), 200


@api.delete("/metadata/fields/<field_id>")
@admin_required
def delete_metadata_field(field_id: str):
    # Protect core Division field from accidental deletion
    fields = {f["id"]: f for f in db().list_metadata_fields()}
    target = fields.get(field_id)
    if target and target["name"] == "Division":
        return jsonify({"error": "Cannot delete the Division field"}), 400
    if not db().delete_metadata_field(field_id):
        return jsonify({"error": "Field not found"}), 404
    return jsonify({"message": "Field deleted"}), 200


@api.get("/divisions")
def list_divisions():
    field = db().find_metadata_field_by_name("Division")
    options = (field or {}).get("options") or Config.DEFAULT_DIVISIONS
    return jsonify({"divisions": options}), 200


@api.get("/health")
def health():
    try:
        db().client.admin.command("ping")
        mongo_ok = True
    except Exception:  # noqa: BLE001
        mongo_ok = False
    return jsonify({"status": "ok" if mongo_ok else "degraded", "mongo": mongo_ok}), 200 if mongo_ok else 503
