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
export MONGO_URI=mongodb://localhost:27017/dms
export SECRET_KEY=dev-secret
python run.py
```

App: http://localhost:5000

## Core API (matches assignment)

| Method | Endpoint | Notes |
|--------|----------|--------|
| POST | `/api/auth/register` | `{username, password, division}` |
| POST | `/api/auth/login` | returns `{token, user}` |
| POST | `/api/documents/upload` | multipart: `file` + `metadata` JSON |
| GET | `/api/documents` | filter via query params e.g. `?Report Type=Financial` |
| GET | `/api/documents/<id>/download` | RBAC enforced |
| POST | `/api/access/request` | `{doc_id}` |
| POST | `/api/access/approve` | `{request_id}` |
| GET | `/api/search?q=` | title, metadata, OCR text |

Auth header for protected routes: `Authorization: Bearer <token>`

> The starter `test_api.py` posts to `/documents/upload` **without** a token. The API accepts that path for the automated suite; the UI always sends a JWT and forces the uploader’s division.

## Run the automated tests

With the server running on port 5000:

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
| `SECRET_KEY` | dev fallback (change in production) |
| `PORT` | `5000` |
| `JWT_EXPIRY_HOURS` | `24` |
