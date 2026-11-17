# Triad AI — Document Management System

A full-stack Document Management System built using **Python Flask, MongoDB Atlas, GridFS and OCR**. The application provides secure document storage, role-based access control (RBAC), division-based access management, cross-division document requests, and OCR-powered document search.

Developed as part of an internship take-home assignment.

## Key Features

- **Document Management:** Upload, store, retrieve and manage documents.
- **MongoDB GridFS:** Store uploaded files directly in MongoDB GridFS.
- **Role-Based Access Control (RBAC):** Restrict document operations based on user roles and permissions.
- **Division-Based Access:** Users can upload documents to their assigned divisions.
- **Cross-Division Access Requests:** Users can request access to documents belonging to other divisions. Authorized users can approve or reject requests.
- **Dynamic Metadata:** Configure metadata fields such as Division and Report Type through Admin / Settings.
- **OCR and Text Extraction:** Extract text from PDFs using PyMuPDF and perform OCR on scanned PDFs and images using Tesseract.
- **Document Search:** Search documents using filenames, metadata and extracted OCR text.
- **JWT Authentication:** Secure API endpoints using JSON Web Tokens.
- **Browser-Based Interface:** Access application features through a frontend dashboard.

## Technology Stack

| Category | Technologies |
|---|---|
| Backend | Python, Flask, REST API |
| Database | MongoDB Atlas |
| File Storage | MongoDB GridFS |
| Authentication | JWT, PyJWT |
| Security | RBAC, Werkzeug password hashing |
| OCR | Tesseract OCR, PyTesseract |
| PDF Processing | PyMuPDF |
| Image Processing | Pillow |
| Frontend | HTML, CSS, JavaScript |
| Version Control | Git, GitHub |

## Project Structure

```text
documentAnalysisSystem/
│
├── app/
│   ├── __init__.py       # Flask application factory
│   ├── routes.py         # REST API endpoints
│   ├── models.py         # MongoDB operations and GridFS
│   ├── ocr.py            # OCR and text extraction
│   ├── utils.py          # JWT and RBAC helpers
│   └── config.py         # Application configuration
│
├── frontend/             # Browser-based frontend
│
├── .env                  # Local environment variables (not committed)
├── .gitignore
├── requirements.txt
├── run.py                # Application entry point
├── test_api.py           # API testing script
├── test_report.txt
├── test_sample.pdf
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Installation and Setup

### Prerequisites

Install the following:

- Python 3.12
- MongoDB Atlas account
- Git
- Tesseract OCR

### 1. Clone the Repository

```bash
git clone https://github.com/3843-jp/documentAnalysisSystem.git
cd documentAnalysisSystem
```

### 2. Create a Python Virtual Environment

For Windows PowerShell:

```powershell
py -3.12 -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Verify Python:

```powershell
python --version
```

### 3. Install Dependencies

```powershell
python -m pip install -r requirements.txt
```

Note: Use `python -m pip` to install packages through the active Python environment.

### 4. Configure MongoDB Atlas

1. Create a MongoDB Atlas account.
2. Create a database cluster.
3. Create a database user with the required permissions.
4. Configure Network Access to allow your development machine's public IP.
5. Open Connect → Drivers and copy the Python connection string.
6. Include your database name in the connection string.

Example format:

```text
mongodb+srv://<username>:<password>@cluster0.example.mongodb.net/triad_dms?retryWrites=true&w=majority
```

Replace the placeholders with your actual MongoDB credentials.

### 5. Configure Environment Variables

Create a `.env` file in the project root directory.

```env
MONGO_URI=mongodb+srv://<username>:<password>@cluster0.example.mongodb.net/triad_dms?retryWrites=true&w=majority

SECRET_KEY=replace-with-a-secure-random-secret

TOKEN_TTL_HOURS=24

MAX_CONTENT_LENGTH=26214400

PORT=5000
```

**Important:**
- Never upload `.env` to GitHub.
- Use a strong secret key.
- URL-encode special characters in MongoDB passwords.
- Ensure the MongoDB URI contains the intended database name.

### 6. Install Tesseract OCR

Install Tesseract OCR for Windows.

Verify the installation:

```powershell
tesseract --version
```

If Windows cannot find the executable, add the Tesseract installation directory to your system PATH.

### 7. Run the Application

Start Flask:

```powershell
python run.py
```

The application will be available at:

```text
http://127.0.0.1:5000
```

Open the URL in your browser to access the frontend.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `MONGO_URI` | MongoDB connection string | Local MongoDB URI |
| `SECRET_KEY` | Flask application secret | Development fallback |
| `TOKEN_TTL_HOURS` | JWT token expiry in hours | 24 |
| `MAX_CONTENT_LENGTH` | Maximum upload size in bytes | 25 MB |
| `PORT` | Flask server port | 5000 |
| `JWT_EXPIRY_HOURS` | Alternative JWT expiry setting | 24 |
| `UPLOAD_MAX_BYTES` | Alternative upload size setting | 25 MB |

The application loads environment variables from `.env` using `python-dotenv`.

## Core API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register a new user |
| POST | `/api/auth/login` | Authenticate and receive JWT |
| POST | `/api/documents/upload` | Upload a document |
| GET | `/api/documents` | Retrieve documents |
| GET | `/api/documents/<id>/download` | Download a document |
| POST | `/api/access/request` | Request access to a document |
| POST | `/api/access/approve` | Approve an access request |
| GET | `/api/search?q=` | Search documents |

### Authentication

Protected API requests use JWT authentication.

Include the following HTTP header:

```http
Authorization: Bearer <your_jwt_token>
```

### Document Upload

The upload endpoint accepts multipart form data containing:

- `file` — document to upload.
- `metadata` — document metadata in JSON format.

## Application Workflow

1. A user registers with a username, password and division.
2. The user logs in and receives a JWT token.
3. The authenticated user uploads a document.
4. The uploaded file is stored in MongoDB GridFS.
5. Document metadata and extracted OCR text are stored in MongoDB.
6. Users can search documents using filenames, metadata and extracted text.
7. Users from other divisions can request document access.
8. Authorized users can approve or reject access requests.
9. Approved users can download the requested documents.

## Running API Tests

With the virtual environment activated and application dependencies installed:

```powershell
python test_api.py
```

Check the generated test report:

```powershell
Get-Content .\test_report.txt
```

## GitHub

Repository: https://github.com/3843-jp/documentAnalysisSystem

## Future Improvements

- Advanced document search and filtering.
- Improved document preview functionality.
- Audit logs for document activities.
- Enhanced admin dashboard.
- Automated testing and deployment.
- Improved document security and validation.

---

