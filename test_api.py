import json
import os
import uuid

import requests

BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000/api")
REPORT_FILE = "test_report.txt"

results = {"total": 0, "passed": 0, "failed": 0, "errors": []}

# Unique per run so the suite can be re-run against the same database.
RUN = uuid.uuid4().hex[:8]
SECRET_WORD = f"zebrafinance{RUN}"
ctx = {}


def log_result(test_name, success, error_msg=""):
    results["total"] += 1
    if success:
        results["passed"] += 1
    else:
        results["failed"] += 1
        results["errors"].append(f"[{test_name}] FAILED: {error_msg}")


def check(test_name, response, expected):
    expected = expected if isinstance(expected, (list, tuple)) else [expected]
    ok = response.status_code in expected
    log_result(
        test_name,
        ok,
        "" if ok else f"Expected {expected}, got {response.status_code}. Response: {response.text[:300]}",
    )
    return ok


def auth(user):
    return {"Authorization": f"Bearer {ctx[user]['token']}"}


def sample_pdf(text):
    """Minimal one-page PDF containing ``text`` as real (extractable) text."""
    stream = f"BT /F1 18 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


def upload(token_user=None, division="Division A"):
    files = {"file": (f"report_{RUN}.pdf", sample_pdf(f"Quarterly {SECRET_WORD} summary"), "application/pdf")}
    data = {"metadata": json.dumps({"Division": division, "Report Type": "Financial"})}
    headers = auth(token_user) if token_user else {}
    return requests.post(f"{BASE_URL}/documents/upload", files=files, data=data, headers=headers)


def search_ids(user, q):
    res = requests.get(f"{BASE_URL}/search", params={"q": q}, headers=auth(user))
    return res, [d["id"] for d in res.json().get("results", [])] if res.ok else []


def test_authentication():
    for name, division in (("alice", "Division A"), ("bob", "Division B")):
        username = f"{name}_{RUN}"
        res = requests.post(
            f"{BASE_URL}/auth/register",
            json={"username": username, "password": "pw-" + RUN, "division": division},
        )
        check(f"POST /api/auth/register ({name})", res, 201)
        res = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": "pw-" + RUN})
        if check(f"POST /api/auth/login ({name})", res, 200):
            ctx[name] = res.json()

    res = requests.post(f"{BASE_URL}/auth/login", json={"username": f"alice_{RUN}", "password": "wrong"})
    check("POST /api/auth/login rejects bad password", res, 401)
    res = requests.get(f"{BASE_URL}/documents")
    check("GET /api/documents requires token", res, 401)


def test_document_upload():
    res = upload("alice")
    if check("POST /api/documents/upload", res, [200, 201]):
        doc = res.json()["document"]
        ctx["doc_id"] = doc["id"]
        log_result(
            "Upload is forced into uploader's division",
            doc["division"] == "Division A",
            f"division was {doc['division']}",
        )
    check("POST /api/documents/upload without token is rejected", upload(None), 401)


def test_rbac_isolation():
    doc_id = ctx["doc_id"]
    check("Same division can download", requests.get(f"{BASE_URL}/documents/{doc_id}/download", headers=auth("alice")), 200)
    check("Other division cannot download", requests.get(f"{BASE_URL}/documents/{doc_id}/download", headers=auth("bob")), 403)

    res = requests.post(f"{BASE_URL}/access/request", json={"doc_id": doc_id}, headers=auth("bob"))
    if not check("POST /api/access/request", res, 201):
        return
    request_id = res.json()["request"]["request_id"]
    check(
        "Requester cannot approve own request",
        requests.post(f"{BASE_URL}/access/approve", json={"request_id": request_id}, headers=auth("bob")),
        403,
    )
    ctx["request_id"] = request_id


def test_search():
    res, ids = search_ids("alice", SECRET_WORD)
    if check("GET /api/search", res, 200):
        log_result("Search finds extracted PDF text", ctx["doc_id"] in ids, f"results: {ids}")

    _, ids = search_ids("bob", SECRET_WORD)
    log_result("Search does not reveal text of inaccessible documents", ctx["doc_id"] not in ids, f"results: {ids}")

    res, _ = search_ids("alice", "(")
    check("Search treats regex characters literally", res, 200)


def test_access_approval():
    res = requests.post(f"{BASE_URL}/access/approve", json={"request_id": ctx["request_id"]}, headers=auth("alice"))
    check("POST /api/access/approve", res, 200)
    check(
        "Approved user can download",
        requests.get(f"{BASE_URL}/documents/{ctx['doc_id']}/download", headers=auth("bob")),
        200,
    )
    _, ids = search_ids("bob", SECRET_WORD)
    log_result("Search includes text after access is approved", ctx["doc_id"] in ids, f"results: {ids}")


def test_metadata_admin_only():
    res = requests.post(f"{BASE_URL}/metadata/fields", json={"name": f"Field {RUN}", "options": []}, headers=auth("alice"))
    check("Non-admin cannot create metadata fields", res, 403)
    res = requests.get(f"{BASE_URL}/metadata/fields", headers=auth("alice"))
    check("GET /api/metadata/fields", res, 200)


def generate_report():
    with open(REPORT_FILE, "w") as f:
        f.write("=== BACKEND API TEST REPORT ===\n")
        f.write(f"Total Endpoints Tested: {results['total']}\n")
        f.write(f"Passed: {results['passed']}\n")
        f.write(f"Failed: {results['failed']}\n\n")

        if results["failed"] > 0:
            f.write("=== FAILURE DETAILS ===\n")
            for error in results["errors"]:
                f.write(f"{error}\n")


if __name__ == "__main__":
    print(f"Running automated API tests against {BASE_URL}...")

    steps = [
        test_authentication,
        test_document_upload,
        test_rbac_isolation,
        test_search,
        test_access_approval,
        test_metadata_admin_only,
    ]
    for step in steps:
        try:
            step()
        except requests.exceptions.ConnectionError:
            log_result(step.__name__, False, "Connection Refused. Is the Flask server running on port 5000?")
            break
        except Exception as e:  # noqa: BLE001
            log_result(step.__name__, False, f"{type(e).__name__}: {e}")

    generate_report()
    print(f"Testing complete. {results['passed']}/{results['total']} passed. Summary written to {REPORT_FILE}.")
