
"""MongoDB data access helpers for users, documents, access requests, and metadata fields."""

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from gridfs import GridFS
from pymongo import ASCENDING, MongoClient, ReturnDocument
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import Config


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Database:
    def __init__(self, uri: str):
        self.client = MongoClient(uri)
        self.db = self.client.get_default_database()
        self.fs = GridFS(self.db)
        self._ensure_indexes()
        self._seed_defaults()

    def _ensure_indexes(self) -> None:
        # Enforce unique usernames only when username is a string.
        # Existing documents with missing/null usernames won't block index creation.
        self.db.users.create_index(
            [("username", ASCENDING)],
            unique=True,
            partialFilterExpression={
                "username": {"$type": "string"}
            },
        )

        self.db.documents.create_index(
            [("division", ASCENDING), ("created_at", ASCENDING)]
        )
        self.db.documents.create_index("ocr_text")

        self.db.access_requests.create_index(
            [("doc_id", ASCENDING), ("requester_id", ASCENDING)]
        )

        self.db.metadata_fields.create_index("name", unique=True)

    def _seed_defaults(self) -> None:
        for field in Config.DEFAULT_METADATA_FIELDS:
            self.db.metadata_fields.update_one(
                {"name": field["name"]},
                {
                    "$setOnInsert": {
                        "name": field["name"],
                        "options": field["options"],
                        "created_at": utcnow(),
                    }
                },
                upsert=True,
            )

    # ---------- Users ----------

    def create_user(
        self,
        username: str,
        password: str,
        division: str,
        role: str = "user",
    ) -> dict:
        username = username.strip()

        if not username:
            raise ValueError("Username cannot be empty")

        doc = {
            "username": username,
            "password_hash": generate_password_hash(password),
            "division": division,
            "role": role,
            "created_at": utcnow(),
        }

        result = self.db.users.insert_one(doc)
        doc["_id"] = result.inserted_id

        return self.serialize_user(doc)

    def find_user_by_username(self, username: str) -> Optional[dict]:
        return self.db.users.find_one({"username": username.strip()})

    def find_user_by_id(self, user_id: str | ObjectId) -> Optional[dict]:
        if not ObjectId.is_valid(user_id):
            return None

        return self.db.users.find_one({"_id": ObjectId(user_id)})

    def verify_password(self, user: dict, password: str) -> bool:
        return check_password_hash(user["password_hash"], password)

    @staticmethod
    def serialize_user(user: dict) -> dict:
        return {
            "id": str(user["_id"]),
            "username": user["username"],
            "division": user["division"],
            "role": user.get("role", "user"),
            "created_at": (
                user.get("created_at").isoformat()
                if user.get("created_at")
                else None
            ),
        }

    # ---------- Documents ----------

    def store_file(self, file_storage, filename: str, content_type: str) -> ObjectId:
        return self.fs.put(
            file_storage,
            filename=filename,
            content_type=content_type or "application/octet-stream",
        )

    def get_file(self, file_id: ObjectId):
        return self.fs.get(file_id)

    def create_document(
        self,
        *,
        filename: str,
        content_type: str,
        gridfs_id: ObjectId,
        metadata: dict,
        division: str,
        uploaded_by: Optional[str],
        ocr_text: str,
    ) -> dict:
        doc = {
            "filename": filename,
            "content_type": content_type,
            "gridfs_id": gridfs_id,
            "metadata": metadata or {},
            "division": division,
            "uploaded_by": uploaded_by,
            "ocr_text": ocr_text or "",
            "created_at": utcnow(),
        }

        result = self.db.documents.insert_one(doc)
        doc["_id"] = result.inserted_id

        return self.serialize_document(doc)

    def find_document(self, doc_id: str) -> Optional[dict]:
        if not ObjectId.is_valid(doc_id):
            return None

        return self.db.documents.find_one({"_id": ObjectId(doc_id)})

    def list_documents(self, filters: Optional[dict] = None) -> list[dict]:
        query: dict[str, Any] = {}
        filters = filters or {}

        for key, value in filters.items():
            if value is None or value == "":
                continue

            if key == "division":
                query["division"] = value
            else:
                query[f"metadata.{key}"] = value

        cursor = self.db.documents.find(query).sort("created_at", -1)

        return [self.serialize_document(doc) for doc in cursor]

    def search_documents(self, query: str) -> list[dict]:
        if not query or not query.strip():
            return []

        search_term = query.strip()
        regex = {"$regex": search_term, "$options": "i"}

        cursor = self.db.documents.find(
            {
                "$or": [
                    {"filename": regex},
                    {"ocr_text": regex},
                    {"division": regex},
                    {"metadata.Division": regex},
                    {"metadata.Report Type": regex},
                    {
                        "$expr": {
                            "$gt": [
                                {
                                    "$size": {
                                        "$filter": {
                                            "input": {
                                                "$objectToArray": {
                                                    "$ifNull": ["$metadata", {}]
                                                }
                                            },
                                            "as": "kv",
                                            "cond": {
                                                "$regexMatch": {
                                                    "input": {"$toString": "$$kv.v"},
                                                    "regex": search_term,
                                                    "options": "i",
                                                }
                                            },
                                        }
                                    }
                                },
                                0,
                            ]
                        }
                    },
                ]
            }
        ).sort("created_at", -1)

        return [self.serialize_document(doc) for doc in cursor]

    @staticmethod
    def serialize_document(doc: dict, include_ocr: bool = False) -> dict:
        payload = {
            "id": str(doc["_id"]),
            "filename": doc.get("filename"),
            "content_type": doc.get("content_type"),
            "metadata": doc.get("metadata") or {},
            "division": doc.get("division"),
            "uploaded_by": doc.get("uploaded_by"),
            "created_at": (
                doc.get("created_at").isoformat()
                if doc.get("created_at")
                else None
            ),
            "has_ocr": bool(doc.get("ocr_text")),
        }

        if include_ocr:
            payload["ocr_text"] = doc.get("ocr_text", "")

        return payload

    # ---------- Access requests ----------

    def create_access_request(
        self,
        doc_id: str,
        requester_id: str,
        requester_division: str,
    ) -> dict:
        existing = self.db.access_requests.find_one(
            {
                "doc_id": doc_id,
                "requester_id": requester_id,
                "status": {"$in": ["pending", "approved"]},
            }
        )

        if existing:
            return self.serialize_access_request(existing)

        doc = {
            "doc_id": doc_id,
            "requester_id": requester_id,
            "requester_division": requester_division,
            "status": "pending",
            "created_at": utcnow(),
            "resolved_at": None,
            "resolved_by": None,
        }

        result = self.db.access_requests.insert_one(doc)
        doc["_id"] = result.inserted_id

        return self.serialize_access_request(doc)

    def find_access_request(self, request_id: str) -> Optional[dict]:
        if not ObjectId.is_valid(request_id):
            return None

        return self.db.access_requests.find_one({"_id": ObjectId(request_id)})

    def list_access_requests_for_division(self, division: str) -> list[dict]:
        docs = list(
            self.db.documents.find({"division": division}, {"_id": 1})
        )
        doc_ids = [str(doc["_id"]) for doc in docs]

        if not doc_ids:
            return []

        cursor = self.db.access_requests.find(
            {"doc_id": {"$in": doc_ids}}
        ).sort("created_at", -1)

        return [self.serialize_access_request(req) for req in cursor]

    def list_access_requests_by_user(self, user_id: str) -> list[dict]:
        cursor = self.db.access_requests.find(
            {"requester_id": user_id}
        ).sort("created_at", -1)

        return [self.serialize_access_request(req) for req in cursor]

    def update_access_request(
        self,
        request_id: str,
        status: str,
        resolved_by: str,
    ) -> Optional[dict]:
        if not ObjectId.is_valid(request_id):
            return None

        updated = self.db.access_requests.find_one_and_update(
            {"_id": ObjectId(request_id), "status": "pending"},
            {
                "$set": {
                    "status": status,
                    "resolved_at": utcnow(),
                    "resolved_by": resolved_by,
                }
            },
            return_document=ReturnDocument.AFTER,
        )

        return self.serialize_access_request(updated) if updated else None

    def has_approved_access(self, doc_id: str, user_id: str) -> bool:
        found = self.db.access_requests.find_one(
            {
                "doc_id": doc_id,
                "requester_id": user_id,
                "status": "approved",
            }
        )

        return found is not None

    def serialize_access_request(self, req: dict) -> dict:
        doc = (
            self.find_document(req["doc_id"])
            if req.get("doc_id")
            else None
        )

        requester = (
            self.find_user_by_id(req["requester_id"])
            if req.get("requester_id")
            else None
        )

        return {
            "id": str(req["_id"]),
            "request_id": str(req["_id"]),
            "doc_id": req.get("doc_id"),
            "document": self.serialize_document(doc) if doc else None,
            "requester_id": req.get("requester_id"),
            "requester": self.serialize_user(requester) if requester else None,
            "requester_division": req.get("requester_division"),
            "status": req.get("status"),
            "created_at": (
                req.get("created_at").isoformat()
                if req.get("created_at")
                else None
            ),
            "resolved_at": (
                req.get("resolved_at").isoformat()
                if req.get("resolved_at")
                else None
            ),
            "resolved_by": req.get("resolved_by"),
        }

    # ---------- Metadata fields ----------

    def list_metadata_fields(self) -> list[dict]:
        cursor = self.db.metadata_fields.find().sort("name", 1)

        return [self.serialize_metadata_field(field) for field in cursor]

    def create_metadata_field(self, name: str, options: list[str]) -> dict:
        doc = {
            "name": name.strip(),
            "options": [
                option.strip()
                for option in options
                if str(option).strip()
            ],
            "created_at": utcnow(),
        }

        result = self.db.metadata_fields.insert_one(doc)
        doc["_id"] = result.inserted_id

        return self.serialize_metadata_field(doc)

    def update_metadata_field(
        self,
        field_id: str,
        name: Optional[str],
        options: Optional[list],
    ) -> Optional[dict]:
        if not ObjectId.is_valid(field_id):
            return None

        updates: dict[str, Any] = {"updated_at": utcnow()}

        if name is not None:
            updates["name"] = name.strip()

        if options is not None:
            updates["options"] = [
                option.strip()
                for option in options
                if str(option).strip()
            ]

        updated = self.db.metadata_fields.find_one_and_update(
            {"_id": ObjectId(field_id)},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
        )

        return self.serialize_metadata_field(updated) if updated else None

    def delete_metadata_field(self, field_id: str) -> bool:
        if not ObjectId.is_valid(field_id):
            return False

        result = self.db.metadata_fields.delete_one(
            {"_id": ObjectId(field_id)}
        )

        return result.deleted_count > 0

    def find_metadata_field_by_name(self, name: str) -> Optional[dict]:
        return self.db.metadata_fields.find_one({"name": name})

