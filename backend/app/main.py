from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse, PlainTextResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, database
from .modules import username_check, email_check, domain_ip_recon, file_metadata, phone_intel, dork_builder
from . import report_export

app = FastAPI(title="RAWS - Read-only OSINT Workstation", version="1.0")

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.on_event("startup")
def _startup():
    database.init_db()


# --------------------------------------------------------------------------
# Case management
# --------------------------------------------------------------------------

class CaseCreate(BaseModel):
    name: str
    description: str = ""
    investigator: str = ""


class NoteCreate(BaseModel):
    note: str


class StatusUpdate(BaseModel):
    status: str


@app.post("/api/cases")
def create_case(payload: CaseCreate):
    if not payload.name.strip():
        raise HTTPException(400, "Case name is required")
    return database.create_case(payload.name.strip(), payload.description.strip(), payload.investigator.strip())


@app.get("/api/cases")
def list_cases():
    return database.list_cases()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = database.get_case(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    case["findings"] = database.list_findings(case_id)
    case["notes"] = database.list_notes(case_id)
    return case


@app.patch("/api/cases/{case_id}/status")
def set_case_status(case_id: str, payload: StatusUpdate):
    if not database.get_case(case_id):
        raise HTTPException(404, "Case not found")
    if payload.status not in ("open", "closed"):
        raise HTTPException(400, "status must be 'open' or 'closed'")
    database.update_case_status(case_id, payload.status)
    return database.get_case(case_id)


@app.delete("/api/cases/{case_id}")
def remove_case(case_id: str):
    if not database.get_case(case_id):
        raise HTTPException(404, "Case not found")
    database.delete_case(case_id)
    return {"deleted": True}


@app.post("/api/cases/{case_id}/notes")
def add_note(case_id: str, payload: NoteCreate):
    if not database.get_case(case_id):
        raise HTTPException(404, "Case not found")
    return database.add_note(case_id, payload.note.strip())


@app.delete("/api/findings/{finding_id}")
def remove_finding(finding_id: str):
    database.delete_finding(finding_id)
    return {"deleted": True}


# --------------------------------------------------------------------------
# Helper to log a tool result to a case
# --------------------------------------------------------------------------

def _log(case_id: str, tool: str, subject: str, subject_type: str, data: dict, summary: str = "", status: str = "ok"):
    if not database.get_case(case_id):
        raise HTTPException(404, "Case not found")
    return database.log_finding(case_id, tool, subject, subject_type, status, summary or data.get("summary", ""), data)


# --------------------------------------------------------------------------
# Tool: Username check
# --------------------------------------------------------------------------

class UsernamePayload(BaseModel):
    case_id: str
    username: str = Field(..., min_length=1)


@app.post("/api/tools/username")
async def run_username_check(payload: UsernamePayload):
    data = await username_check.check_username_async(payload.username.strip())
    status = "error" if data.get("error") else "ok"
    return _log(payload.case_id, "Username Check", payload.username.strip(), "username", data, status=status)


# --------------------------------------------------------------------------
# Tool: Email check
# --------------------------------------------------------------------------

class EmailPayload(BaseModel):
    case_id: str
    email: str = Field(..., min_length=3)


@app.post("/api/tools/email")
async def run_email_check(payload: EmailPayload):
    data = await email_check.check_email_async(payload.email.strip())
    status = "ok" if data.get("valid_syntax") else "error"
    return _log(payload.case_id, "Email Check", payload.email.strip(), "email", data, status=status)


# --------------------------------------------------------------------------
# Tool: Domain / IP recon
# --------------------------------------------------------------------------

class DomainIpPayload(BaseModel):
    case_id: str
    subject: str = Field(..., min_length=1)


@app.post("/api/tools/domain-ip")
async def run_domain_ip_recon(payload: DomainIpPayload):
    subject = payload.subject.strip()
    data = await domain_ip_recon.recon_async(subject)
    return _log(payload.case_id, "Domain/IP Recon", subject, data["type"], data)


# --------------------------------------------------------------------------
# Tool: Phone intel (offline)
# --------------------------------------------------------------------------

class PhonePayload(BaseModel):
    case_id: str
    phone: str = Field(..., min_length=1)
    region: Optional[str] = None


@app.post("/api/tools/phone")
def run_phone_intel(payload: PhonePayload):
    data = phone_intel.analyze_phone(payload.phone.strip(), payload.region)
    status = "ok" if data.get("valid") else "error"
    return _log(payload.case_id, "Phone Intel", payload.phone.strip(), "phone", data, status=status)


# --------------------------------------------------------------------------
# Tool: Dork builder
# --------------------------------------------------------------------------

class DorkPayload(BaseModel):
    case_id: str
    subject: str = Field(..., min_length=1)
    subject_type: str = Field(..., pattern="^(name|username|email|domain|phone)$")


@app.post("/api/tools/dorks")
def run_dork_builder(payload: DorkPayload):
    data = dork_builder.build_dorks(payload.subject.strip(), payload.subject_type)
    return _log(payload.case_id, "Dork Builder", payload.subject.strip(), payload.subject_type, data,
                summary=f"{sum(len(g['links']) for g in data['groups'])} dork link groups generated")


class ReverseImagePayload(BaseModel):
    case_id: str
    image_url: str = Field(..., min_length=5)


@app.post("/api/tools/reverse-image")
def run_reverse_image(payload: ReverseImagePayload):
    data = dork_builder.build_reverse_image_links(payload.image_url.strip())
    return _log(payload.case_id, "Reverse Image Search", payload.image_url.strip(), "image_url", data,
                summary=f"{len(data['links'])} reverse image search links generated")


# --------------------------------------------------------------------------
# Tool: File metadata upload
# --------------------------------------------------------------------------

@app.post("/api/tools/file")
async def run_file_metadata(case_id: str = Form(...), file: UploadFile = File(...)):
    if not database.get_case(case_id):
        raise HTTPException(404, "Case not found")
    contents = await file.read()
    if len(contents) > config.UPLOAD_MAX_BYTES:
        raise HTTPException(413, "File too large")
    with tempfile.NamedTemporaryFile(delete=True, suffix=Path(file.filename).suffix) as tmp:
        tmp.write(contents)
        tmp.flush()
        data = file_metadata.extract_metadata(tmp.name, file.filename)
    summary = f"{file.filename} ({data.get('size_bytes', 0)} bytes) - sha256 {data['hashes']['sha256'][:16]}..."
    return _log(case_id, "File Metadata", file.filename, "file", data, summary=summary)


# --------------------------------------------------------------------------
# Batch mode - run one tool across up to 25 subjects
# --------------------------------------------------------------------------

class BatchPayload(BaseModel):
    case_id: str
    tool: str = Field(..., pattern="^(username|email|domain-ip|phone)$")
    subjects: list[str]
    region: Optional[str] = None


@app.post("/api/tools/batch")
async def run_batch(payload: BatchPayload):
    if not database.get_case(payload.case_id):
        raise HTTPException(404, "Case not found")
    subjects = [s.strip() for s in payload.subjects if s.strip()]
    if not subjects:
        raise HTTPException(400, "No subjects provided")
    if len(subjects) > config.BATCH_MAX_SUBJECTS:
        raise HTTPException(400, f"Batch mode supports at most {config.BATCH_MAX_SUBJECTS} subjects")

    results = []
    for subject in subjects:
        try:
            if payload.tool == "username":
                data = await username_check.check_username_async(subject)
                finding = _log(payload.case_id, "Username Check", subject, "username", data,
                                status="error" if data.get("error") else "ok")
            elif payload.tool == "email":
                data = await email_check.check_email_async(subject)
                finding = _log(payload.case_id, "Email Check", subject, "email", data,
                                status="ok" if data.get("valid_syntax") else "error")
            elif payload.tool == "domain-ip":
                data = await domain_ip_recon.recon_async(subject)
                finding = _log(payload.case_id, "Domain/IP Recon", subject, data["type"], data)
            elif payload.tool == "phone":
                data = phone_intel.analyze_phone(subject, payload.region)
                finding = _log(payload.case_id, "Phone Intel", subject, "phone", data,
                                status="ok" if data.get("valid") else "error")
            else:
                continue
            results.append(finding)
        except Exception as e:  # noqa: BLE001
            results.append({"subject": subject, "status": "error", "summary": str(e)})
    return {"tool": payload.tool, "count": len(results), "results": results}


# --------------------------------------------------------------------------
# Report export
# --------------------------------------------------------------------------

@app.get("/api/cases/{case_id}/report.md")
def export_markdown(case_id: str):
    if not database.get_case(case_id):
        raise HTTPException(404, "Case not found")
    md = report_export.build_markdown_report(case_id)
    return PlainTextResponse(md, media_type="text/markdown",
                              headers={"Content-Disposition": f'attachment; filename="case_{case_id}.md"'})


@app.get("/api/cases/{case_id}/report.pdf")
def export_pdf(case_id: str):
    if not database.get_case(case_id):
        raise HTTPException(404, "Case not found")
    try:
        pdf_bytes = report_export.build_pdf_report(case_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"PDF generation failed: {e}")
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f'attachment; filename="case_{case_id}.pdf"'})


# --------------------------------------------------------------------------
# Frontend static files (served last so /api routes take precedence)
# --------------------------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    import warnings
    warnings.warn(
        f"Frontend directory not found at {FRONTEND_DIR} - the web UI will "
        "not be served (API routes under /api still work). Check that the "
        "'frontend' folder sits alongside 'backend' in the RAWS project root."
    )
