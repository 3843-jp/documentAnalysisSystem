# Triad AI — Document Management System

Full-stack internship take-home: Flask REST API + MongoDB/GridFS + OCR search + RBAC with cross-division access requests, plus a browser UI for all required views.

## Features

- **Dynamic metadata** — configurable fields (Division, Report Type, …) editable from Admin / Settings
- **RBAC & division isolation** — users upload only to their division; same-division users can download
- **Cross-division access requests** — request → approve/reject workflow
- **OCR / text search** — PDF text via PyMuPDF; image/scanned OCR via Tesseract when available
- **GridFS** — all uploaded files stored in MongoDB GridFS

## Project structure

```
├── app/
│   ├── __init__.py      # Flask app factory
│   ├── routes.py        # REST API
│   ├── models.py        # MongoDB + GridFS
│   ├── ocr.py           # OCR / text extraction
│   ├── utils.py         # JWT + RBAC helpers
│   └── config.py
├── frontend/            # SPA (login, dashboard, detail, search, inbox, settings)
├── test_api.py          # Triad automated starter tests
├── run.py
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## Quick start (Docker — recommended)

```bash
cp .env.example .env   # then set SECRET_KEY (and ADMIN_PASSWORD if you want an admin)
docker compose up --build
```

Open http://localhost:5000

## Local development

### 1. MongoDB

```bash
# if you use Docker only for Mongo:
docker run -d --name dms-mongo -p 27017:27017 mongo:7
```

### 2. Python env

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional OCR binary (images / scanned PDFs):

```bash
# Debian/Ubuntu
sudo apt-get install -y tesseract-ocr
```

### 3. Run API + UI

```bash
cp .env.example .env   # run.py loads it; or export the variables yourself
python run.py
```

App: http://localhost:5000

## Core API (matches assignment)

| Method | Endpoint | Notes |
|--------|----------|--------|
| POST | `/api/auth/register` | `{username, password, division}` |
| POST | `/api/auth/login` | returns `{token, user}` |
| POST | `/api/documents/upload` | multipart: `file` + `metadata` JSON; token required |
| GET | `/api/documents` | filter via query params e.g. `?Report Type=Financial` |
| GET | `/api/documents/<id>/download` | RBAC enforced |
| POST | `/api/access/request` | `{doc_id}` |
| POST | `/api/access/approve` | `{request_id}` |
| GET | `/api/search?q=` | title, metadata, OCR text (OCR text only for documents you can open) |
| POST/PUT/DELETE | `/api/metadata/fields` | admin only |

Auth header for protected routes: `Authorization: Bearer <token>`

Uploads always go into the uploader's division. The original starter `test_api.py` uploaded **without** a token; that is rejected by default. Set `ALLOW_ANONYMOUS_UPLOAD=1` only if you need to run that original script unchanged.

### Admin

Metadata fields (Admin / Settings) can only be changed by an admin. Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` and the account is created on startup (an existing user with that name is promoted).

## Run the automated tests

`test_api.py` covers auth, upload, division isolation, the access request flow, search and admin-only settings. With the server running on port 5000:

```bash
pip install requests
python test_api.py
cat test_report.txt
```

## Manual test walkthrough

1. Register **alice** in Division A and **bob** in Division B  
2. Alice uploads a PDF with Report Type = Financial  
3. Bob sees the doc but must **Request Access** to download  
4. Alice opens **Access Inbox** → Approve  
5. Bob can download; search finds OCR/extracted text  

## Environment

| Variable | Default |
|----------|---------|
| `MONGO_URI` | `mongodb://localhost:27017/dms` |
| `SECRET_KEY` | insecure dev fallback with a warning; **required** by docker compose |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | unset (no admin) |
| `ADMIN_DIVISION` | `Division A` |
| `ALLOW_ANONYMOUS_UPLOAD` | `0` |
| `PORT` | `5000` |
| `JWT_EXPIRY_HOURS` | `24` |
