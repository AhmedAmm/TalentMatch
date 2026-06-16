"""
main.py
===========
SmartStaff FastAPI backend.

All database access goes through db/operations.py (Beanie async ODM).
Matching uses matching_pipeline_v2 exclusively.

Run:
    python start.py
    # or directly:
    uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import sys
import tempfile
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

# ── sys-path bootstrap ────────────────────────────────────────────────────────
_ROOT  = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.join(_ROOT, "tools")
_POP   = os.path.join(_ROOT, "po_parser")

for _p in [_ROOT, _TOOLS, _POP]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── FastAPI ───────────────────────────────────────────────────────────────────
from fastapi import (
    Depends, FastAPI, File, Form, Header, HTTPException,
    Request, UploadFile, BackgroundTasks,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

# ── Local ─────────────────────────────────────────────────────────────────────
from security import (
    check_nosql_injection,
    sanitize_string,
    validate_email_field,
    validate_pdf_upload,
    verify_turnstile,
)
import security.auth as _auth
import db.operations as _db

# ── matching_pipeline_v2 ──────────────────────────────────────────────────────
from matching_pipeline_v2.search_service import (
    search_employees_for_job as _search_employees,
    find_best_replacement    as _find_best_replacement,
    build_explanation_text   as _explain_text,
)
from matching_pipeline_v2.knowledge_graph import (
    get_kg              as _get_kg,
    invalidate_kg_cache as _invalidate_kg_cache,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nw_main2")

# In-process cache: pdf_sha256 → parsed project data dict.
# parse-pdf stores here; ingest-pdf reuses it to avoid double Docling + LLM.
_parse_cache: dict[str, dict] = {}

# ─────────────────────────────────────────────────────────────────────────────
#  APP
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title       = "SmartStaff API",
    version     = "2.0.0",
    description = "AI-powered employee matching & CV generation platform.",
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins     = _ALLOWED_ORIGINS,
    allow_credentials = True,
    allow_methods     = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers     = ["Authorization", "Content-Type", "CF-Turnstile-Token"],
)


# ─────────────────────────────────────────────────────────────────────────────
#  Auth dependencies
# ─────────────────────────────────────────────────────────────────────────────
def _get_current_user(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    try:
        return _auth.verify_token(authorization[len("Bearer "):])
    except _auth.AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


def _require_admin(current_user: dict = Depends(_get_current_user)) -> dict:
    if not current_user.get("is_sys_admin") and current_user.get("role") not in ("ADMIN", "RH"):
        raise HTTPException(status_code=403, detail="Admin or RH role required.")
    return current_user


def _require_po_or_admin(current_user: dict = Depends(_get_current_user)) -> dict:
    if current_user.get("role") not in ("ADMIN", "PO", "RH") and not current_user.get("is_sys_admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions.")
    return current_user


# ─────────────────────────────────────────────────────────────────────────────
#  Pydantic request models
# ─────────────────────────────────────────────────────────────────────────────
class LoginRequest(BaseModel):
    email:    str
    password: str

    @field_validator("email")
    @classmethod
    def _clean_email(cls, v: str) -> str:
        return sanitize_string(v, 254)

    @field_validator("password")
    @classmethod
    def _clean_password(cls, v: str) -> str:
        if not v or len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class RegisterRequest(BaseModel):
    email:    str
    name:     str
    password: str
    role:     str = "PO"

    @field_validator("email")
    @classmethod
    def _clean_email(cls, v: str) -> str:
        return sanitize_string(v, 254)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        return sanitize_string(v, 120)

    @field_validator("role")
    @classmethod
    def _clean_role(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("PO", "RH", "ADMIN"):
            raise ValueError("role must be PO, RH, or ADMIN.")
        return v


class CreateUserRequest(BaseModel):
    name:     str
    email:    str
    role:     str
    password: str = Field(default="ChangeMe123!")

    @field_validator("email")
    @classmethod
    def _clean_email(cls, v: str) -> str:
        return sanitize_string(v, 254)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        return sanitize_string(v, 120)


class ProjectJobIn(BaseModel):
    title:     str
    headcount: int = 1

    @field_validator("title")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_string(v, 200)

    @field_validator("headcount")
    @classmethod
    def _valid_headcount(cls, v: int) -> int:
        if v < 1:
            raise ValueError("headcount must be >= 1")
        return min(v, 50)


class CreateProjectRequest(BaseModel):
    name:   str
    client: str
    status: str = "IN_PROGRESS"
    poId:   str
    jobs:   list[ProjectJobIn] = []

    @field_validator("name", "client", "status", "poId")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_string(v, 300)


class UpdatePORequest(BaseModel):
    po_id: str

    @field_validator("po_id")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_string(v, 254)


class UpdateStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_string(v, 50)


class UpdateMatchStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _valid(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in ("PENDING", "ACCEPTED", "REJECTED"):
            raise ValueError("status must be PENDING, ACCEPTED, or REJECTED.")
        return v


class SwapRequest(BaseModel):
    new_employee_id: str
    old_match_id:    Optional[str] = None

    @field_validator("new_employee_id")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_string(v, 254)


class ManualSwapRequest(BaseModel):
    project_id:      str
    job_id:          str
    new_employee_id: str
    old_match_id:    Optional[str] = None

    @field_validator("project_id", "job_id", "new_employee_id")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_string(v, 254)


class GenerateCVRequest(BaseModel):
    employee_id: str
    project_id:  Optional[str] = None
    job_id:      Optional[str] = None
    language:    str = "en"

    @field_validator("employee_id")
    @classmethod
    def _clean_emp(cls, v: str) -> str:
        return sanitize_string(v, 254)

    @field_validator("language")
    @classmethod
    def _clean_lang(cls, v: str) -> str:
        return sanitize_string(v, 5)


class ManualAssignRequest(BaseModel):
    employee_id:      str
    replace_match_id: Optional[str] = None

    @field_validator("employee_id")
    @classmethod
    def _clean(cls, v: str) -> str:
        return sanitize_string(v, 254)


# ─────────────────────────────────────────────────────────────────────────────
#  Serialisation helpers
# ─────────────────────────────────────────────────────────────────────────────
def _serialize(doc: Any) -> Any:
    if doc is None:
        return None
    if isinstance(doc, dict):
        return {k: _serialize(v) for k, v in doc.items() if k != "password_hash"}
    if isinstance(doc, list):
        return [_serialize(i) for i in doc]
    try:
        from bson import ObjectId
        if isinstance(doc, ObjectId):
            return str(doc)
    except ImportError:
        pass
    return doc


def _not_found(resource: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{resource} not found.")


def _serialize_employee(doc: dict) -> dict:
    if not doc:
        return {}
    doc = _serialize(doc)
    experiences = []
    for i, p in enumerate(doc.get("projects", [])):
        sd     = p.get("start_date") or ""
        ed     = p.get("end_date") or "Present"
        period = f"{sd} - {ed}" if sd else ed
        experiences.append({
            "id":          p.get("project_id", f"exp_{i}"),
            "title":       p.get("role", ""),
            "company":     p.get("client", ""),
            "period":      period,
            "description": ", ".join(p.get("technologies", [])),
        })
    stored_stats = doc.get("stats", {})
    return {
        "id":          doc.get("_id") or doc.get("email", ""),
        "name":        doc.get("name", ""),
        "email":       doc.get("email", ""),
        "about":       doc.get("current_role", ""),
        "skills":      doc.get("skills", []),
        "isAvailable": doc.get("available", True),
        "avatarUrl":   doc.get("avatar_url"),
        "experiences": experiences,
        "stats": {
            "technical":      stored_stats.get("technical", 50),
            "communication":  stored_stats.get("communication", 50),
            "leadership":     stored_stats.get("leadership", 50),
            "problemSolving": stored_stats.get("problemSolving", 50),
            "teamwork":       stored_stats.get("teamwork", 50),
        },
    }


def _assignment_to_match(doc: dict) -> dict:
    if not doc:
        return {}
    raw_score = doc.get("adequacy_score") or doc.get("score") or 0
    return {
        "id":              str(doc.get("_id", "")),
        "projectId":       doc.get("project_id", ""),
        "jobId":           doc.get("job_id", ""),
        "employeeId":      doc.get("employee_id", ""),
        "status":          (doc.get("status", "pending")).upper(),
        "matchReason":     doc.get("notes", ""),
        "matchScore":      raw_score,
        "scorePercentage": round(raw_score * 100),
        "explanation":     doc.get("explanation", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  A2A agent servers
# ─────────────────────────────────────────────────────────────────────────────
_servers_started = False


def _ensure_a2a_servers() -> None:
    """Start all four A2A agent servers if they are not already running."""
    global _servers_started
    if _servers_started:
        return
    from matching_pipeline_v2.run import start_all_servers
    start_all_servers()
    _servers_started = True


async def _run_matching_pipeline(project_id: str) -> None:
    """
    Background task: run the full matching_pipeline_v2 for a project and
    persist the resulting assignments via the ORM.
    """
    try:
        logger.info("[Pipeline] Starting pipeline for project '%s'", project_id)

        raw_employees = await _db.list_employees(available=True)
        raw_jobs      = await _db.get_open_jobs(project_id)

        if not raw_employees or not raw_jobs:
            logger.warning(
                "[Pipeline] No employees (%d) or jobs (%d) — aborting.",
                len(raw_employees), len(raw_jobs),
            )
            return

        jobs_for_pipeline = [
            {
                "job_id":          j["_id"],
                "title":           j.get("title", ""),
                # remaining open positions — Hungarian expands by this count
                "headcount":       max(int(j.get("remaining", j.get("headcount", 1))), 1),
                "required_skills": [
                    (s["skill"] if isinstance(s, dict) else s).strip()
                    for s in j.get("required_stack", [])
                    if s
                ],
            }
            for j in raw_jobs
        ]

        employees_for_pipeline = []
        for emp in raw_employees:
            personal_kg: dict[str, list[str]] = {}
            for proj in emp.get("projects", []):
                techs = [t.strip().lower() for t in proj.get("technologies", []) if t]
                for tech in techs:
                    for related in techs:
                        if related != tech:
                            personal_kg.setdefault(tech, [])
                            if related not in personal_kg[tech]:
                                personal_kg[tech].append(related)
            employees_for_pipeline.append({
                "email":           emp["email"],
                "name":            emp.get("name", ""),
                "skills":          emp.get("skills", []),
                "knowledge_graph": personal_kg,
            })

        kg = _get_kg()
        _ensure_a2a_servers()

        from matching_pipeline_v2.orchestrator import run_pipeline
        loop = asyncio.get_event_loop()
        summary_text, assignments = await loop.run_in_executor(
            None, run_pipeline, employees_for_pipeline, jobs_for_pipeline, kg
        )
        logger.info("[Pipeline] Pipeline complete for '%s': %s", project_id, summary_text[:120])

        for asgn in assignments:
            try:
                new_asgn = await _db.create_assignment(
                    employee_id = asgn["employee_email"],
                    project_id  = project_id,
                    job_id      = asgn["job_id"],
                    assigned_by = "matching_pipeline_v2",
                    notes       = "",
                )
                explanation = asgn.get("explanation") or _explain_text(
                    asgn["job_id"],
                    asgn["employee_email"],
                    asgn.get("score", 0.0),
                    asgn.get("matched_skills", []),
                    asgn.get("missing_skills", []),
                )
                await _db.update_assignment_fields(
                    str(new_asgn["_id"]),
                    adequacy_score = asgn.get("score", 0.0),
                    explanation    = explanation,
                )
            except (ValueError, Exception) as exc:
                logger.warning(
                    "[Pipeline] Could not persist assignment %s → %s: %s",
                    asgn.get("employee_email"), asgn.get("job_id"), exc,
                )

    except Exception as exc:
        logger.error("[Pipeline] Pipeline failed for '%s': %s", project_id, exc, exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Composite helpers
# ─────────────────────────────────────────────────────────────────────────────
async def _build_project_details(project_id: str) -> Optional[dict]:
    proj = await _db.get_project(project_id)
    if not proj:
        return None

    result = _serialize(proj)
    jobs   = await _db.get_jobs_by_project(project_id)
    result["jobs"] = _serialize(jobs)

    assignment_docs = await _db.list_assignments(
        project_id = project_id,
        statuses   = ["pending", "accepted"],
    )

    emp_ids  = list({a["employee_id"] for a in assignment_docs})
    emp_map: dict[str, dict] = {}
    if emp_ids:
        for emp in await _db.list_employees():
            if emp["email"] in emp_ids:
                emp_map[emp["email"]] = emp

    matches = []
    for a in assignment_docs:
        m = _assignment_to_match(a)
        emp = emp_map.get(a["employee_id"])
        if emp:
            stored_stats = emp.get("stats", {})
            m["employee"] = {
                "id":        emp.get("email", ""),
                "name":      emp.get("name", ""),
                "email":     emp.get("email", ""),
                "about":     emp.get("current_role", ""),
                "skills":    emp.get("skills", []),
                "avatarUrl": emp.get("avatar_url"),
                "stats": {
                    "technical":      stored_stats.get("technical", 50),
                    "communication":  stored_stats.get("communication", 50),
                    "leadership":     stored_stats.get("leadership", 50),
                    "problemSolving": stored_stats.get("problemSolving", 50),
                    "teamwork":       stored_stats.get("teamwork", 50),
                },
            }
        else:
            m["employee"] = None
        matches.append(m)

    matches.sort(key=lambda x: x.get("matchScore", 0), reverse=True)
    result["matches"] = matches
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  HEALTH
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "SmartStaff API", "version": "2.0.0"}


# ─────────────────────────────────────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/v1/auth/login", tags=["Auth"])
async def login(body: LoginRequest, request: Request):
    email = validate_email_field(body.email)
    check_nosql_injection({"email": email, "password": ""})
    try:
        result  = await _auth.login(email, body.password)
        user_id = result.get("user", {}).get("id") or email
        user    = await _db.get_user(user_id)
        if user:
            result["user"] = {
                "id":     user.get("_id") or user.get("email"),
                "name":   user.get("name"),
                "email":  user.get("email"),
                "role":   user.get("role"),
                "active": user.get("active", True),
            }
        return result
    except _auth.AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@app.post("/api/v1/auth/logout", tags=["Auth"])
async def logout(current_user: dict = Depends(_get_current_user)):
    return {"message": "Logged out successfully."}


@app.get("/api/v1/auth/me", tags=["Auth"])
async def get_me(current_user: dict = Depends(_get_current_user)):
    user = await _db.get_user(current_user.get("sub"))
    if not user:
        raise _not_found("User")
    return _serialize(user)


@app.post("/api/v1/auth/register", tags=["Auth"], status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    cf_turnstile_token: str = Header(default="", alias="CF-Turnstile-Token"),
):
    client_ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else None)
    await verify_turnstile(cf_turnstile_token, client_ip)
    email = validate_email_field(body.email)
    check_nosql_injection({"email": email, "name": body.name})
    try:
        # FIX: was missing await — coroutine was never executed
        return await _auth.create_user(email=email, name=body.name, password=body.password, role=body.role)
    except (ValueError, _auth.AuthError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
#  USERS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/users", tags=["Users"])
async def list_users(current_user: dict = Depends(_require_admin)):
    return _serialize(await _db.list_users())


@app.post("/api/v1/users", tags=["Users"], status_code=201)
async def create_user(body: CreateUserRequest, current_user: dict = Depends(_require_admin)):
    check_nosql_injection(body.model_dump())
    email = validate_email_field(body.email)
    try:
        # FIX: was missing await — user was never actually saved to DB
        return _serialize(await _auth.create_user(
            email=email, name=body.name, password=body.password, role=body.role.upper()
        ))
    except (ValueError, _auth.AuthError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/v1/users/{user_id}", tags=["Users"], status_code=204)
async def delete_user(user_id: str, current_user: dict = Depends(_require_admin)):
    user_id = sanitize_string(user_id, 254)
    try:
        # FIX: was missing await — deactivation was silently dropped, always returned 204
        await _auth.deactivate_user(user_id)
    except _auth.AuthError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
#  EMPLOYEES
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/employees", tags=["Employees"])
async def list_employees(
    search:    Optional[str]  = None,
    available: Optional[bool] = None,
    current_user: dict = Depends(_get_current_user),
):
    search_clean = sanitize_string(search, 200) if search else None
    docs = await _db.list_employees(search=search_clean, available=available)
    return [_serialize_employee(d) for d in docs]


@app.get("/api/v1/employees/{employee_id}", tags=["Employees"])
async def get_employee(employee_id: str, current_user: dict = Depends(_get_current_user)):
    employee_id = sanitize_string(employee_id, 254)
    doc = await _db.get_employee(employee_id)
    if not doc:
        raise _not_found("Employee")
    return _serialize_employee(doc)


@app.post("/api/v1/employees/upload-cv", tags=["Employees"], status_code=201)
async def import_cv(
    request: Request,
    file:  UploadFile = File(...),
    email: str        = Form(...),
    cf_turnstile_token: str = Header(default="", alias="CF-Turnstile-Token"),
    current_user: dict = Depends(_get_current_user),
):
    client_ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else None)
    await verify_turnstile(cf_turnstile_token, client_ip)
    email     = validate_email_field(email)
    pdf_bytes = await validate_pdf_upload(file)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        from services.pdf import extract_text_from_pdf
        from services.llm import ask_llm
        import json, re

        _CV_PROMPT = """
You are a CV parser. Extract structured information from the CV text below and return ONLY a valid JSON object — no markdown, no explanation.

CV TEXT:
{text}

Return this exact JSON structure (fill in all fields, use null if unknown, use [] for empty lists):
{{
  "name": "string",
  "current_role": "string",
  "education": [
    {{
      "degree": "string",
      "field": "string",
      "school": "string",
      "year": 2024
    }}
  ],
  "certifications": [
    {{
      "name": "string",
      "issuer": "string",
      "date": "YYYY"
    }}
  ],
  "skills": ["skill1", "skill2"],
  "projects": [
    {{
      "project_id": "PROJ-001",
      "client": "string",
      "role": "string",
      "start_date": "YYYY-MM",
      "end_date": null,
      "technologies": ["tech1", "tech2"],
      "tasks": []
    }}
  ]
}}
"""
        raw_text = extract_text_from_pdf(tmp_path)
        if not raw_text.strip():
            raise HTTPException(status_code=422, detail="PDF appears to be empty or unreadable.")
        response = ask_llm(_CV_PROMPT.format(text=raw_text[:8000]))

        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()
        else:
            cleaned = re.sub(r"```(?:json)?", "", cleaned).strip().strip("`").strip()

        parsed   = json.loads(cleaned)
        is_new   = not await _db.employee_exists(email)
        employee = await _db.add_employee(
            email          = email,
            name           = sanitize_string(parsed.get("name", ""), 120),
            current_role   = sanitize_string(parsed.get("current_role", ""), 200),
            education      = parsed.get("education", []),
            certifications = parsed.get("certifications", []),
            skills         = [sanitize_string(s, 100) for s in parsed.get("skills", [])],
            projects       = parsed.get("projects", []),
            cv_filename    = file.filename,
        )
        result = _serialize_employee(employee)
        result["created" if is_new else "updated"] = True
        return result

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("CV import failed for %s", email)
        raise HTTPException(status_code=500, detail=f"CV import failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  CV GENERATION
# ─────────────────────────────────────────────────────────────────────────────
async def _run_cv_generation(
    employee_id: str,
    job_id: Optional[str],
    language: str,
    out: str,
) -> None:
    """Fetch employee + job from DB, then run CV generation in a thread executor."""
    from cv_generation.cv_generation import generate_cv as _gen_cv

    emp_doc = await _db.get_employee(employee_id)
    job_doc = await _db.get_job(job_id) if job_id else None

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: _gen_cv(
            employee_id  = employee_id,
            job_id       = job_id,
            language     = language,
            output_path  = out,
            employee_doc = emp_doc,
            job_doc      = job_doc,
        ),
    )


@app.get("/api/v1/employees/{employee_id}/generate-cv", tags=["Employees"])
async def generate_cv_get(
    employee_id: str,
    project_id:  Optional[str] = None,
    job_id:      Optional[str] = None,
    language:    str = "en",
    current_user: dict = Depends(_get_current_user),
):
    employee_id = sanitize_string(employee_id, 254)
    job_id      = sanitize_string(job_id, 100) if job_id else None
    language    = sanitize_string(language, 5)
    if not await _db.get_employee(employee_id):
        raise _not_found("Employee")
    try:
        out = os.path.join(
            tempfile.gettempdir(),
            f"cv_{employee_id.replace('@','_').replace('.','_')}_{job_id or 'general'}.docx",
        )
        await _run_cv_generation(employee_id, job_id, language, out)
        return FileResponse(
            path=out,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=os.path.basename(out),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("CV generation failed for %s", employee_id)
        raise HTTPException(status_code=500, detail=f"CV generation failed: {exc}")


@app.post("/api/v1/cv/generate", tags=["CV"])
async def generate_cv_post(body: GenerateCVRequest, current_user: dict = Depends(_get_current_user)):
    employee_id = sanitize_string(body.employee_id, 254)
    job_id      = sanitize_string(body.job_id, 100) if body.job_id else None
    language    = sanitize_string(body.language, 5)
    if not await _db.get_employee(employee_id):
        raise _not_found("Employee")
    try:
        out = os.path.join(
            tempfile.gettempdir(),
            f"cv_{employee_id.replace('@','_').replace('.','_')}_{job_id or 'general'}.docx",
        )
        await _run_cv_generation(employee_id, job_id, language, out)
        return FileResponse(
            path=out,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=os.path.basename(out),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("CV generation (POST) failed for %s", employee_id)
        raise HTTPException(status_code=500, detail=f"CV generation failed: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
#  GRAPH / KG STATS  (admin)
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/graph/stats", tags=["System"])
async def graph_cache_stats(current_user: dict = Depends(_require_admin)):
    try:
        kg      = _get_kg()
        n_edges = sum(len(v) for v in kg.values())
        return {
            "loaded":  bool(kg),
            "n_nodes": len(kg),
            "n_edges": n_edges,
            "source":  "Neo4j (matching_pipeline_v2)",
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/graph/refresh", tags=["System"])
async def refresh_graph_cache(current_user: dict = Depends(_require_admin)):
    try:
        _invalidate_kg_cache()
        loop    = asyncio.get_event_loop()
        kg      = await loop.run_in_executor(None, _get_kg)
        n_edges = sum(len(v) for v in kg.values())
        return {
            "message":  "Knowledge graph reloaded from Neo4j.",
            "n_nodes":  len(kg),
            "n_edges":  n_edges,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
#  PROJECTS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/projects", tags=["Projects"])
async def list_projects(
    po_id:  Optional[str] = None,
    status: Optional[str] = None,
    current_user: dict = Depends(_get_current_user),
):
    po_id_clean  = sanitize_string(po_id, 254) if po_id else None
    status_clean = sanitize_string(status, 50).upper() if status else None
    project_docs = await _db.list_projects(po_id=po_id_clean, status=status_clean)
    result = []
    for proj in project_docs:
        proj = _serialize(proj)
        proj["jobs"] = _serialize(await _db.get_jobs_by_project(proj["_id"]))
        result.append(proj)
    return result


@app.get("/api/v1/projects/{project_id}", tags=["Projects"])
async def get_project(project_id: str, current_user: dict = Depends(_get_current_user)):
    project_id = sanitize_string(project_id, 100)
    doc = await _db.get_project(project_id)
    if not doc:
        raise _not_found("Project")
    result = _serialize(doc)
    result["jobs"] = _serialize(await _db.get_jobs_by_project(project_id))
    return result


@app.get("/api/v1/projects/{project_id}/details", tags=["Projects"])
async def get_project_details(project_id: str, current_user: dict = Depends(_get_current_user)):
    project_id = sanitize_string(project_id, 100)
    details    = await _build_project_details(project_id)
    if not details:
        raise _not_found("Project")
    return details


@app.post("/api/v1/projects", tags=["Projects"], status_code=201)
async def create_project(
    body: CreateProjectRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(_require_po_or_admin),
):
    check_nosql_injection(body.model_dump())
    import re as _re, uuid

    slug       = _re.sub(r"[^a-z0-9]+", "_", body.name.lower()).strip("_")
    project_id = f"proj_{slug}_{uuid.uuid4().hex[:6]}"

    await _db.upsert_project(
        project_id=project_id, name=body.name, client_name=body.client,
        description="", functional_needs=[], non_functional_needs=[],
        technology_stack=[], job_ids=[], po_id=body.poId,
    )
    for idx, job_in in enumerate(body.jobs):
        j_slug = _re.sub(r"[^a-z0-9]+", "_", job_in.title.lower()).strip("_")
        job_id = f"{project_id}_{j_slug}_{idx}"
        await _db.upsert_job(
            job_id=job_id, project_id=project_id, title=job_in.title,
            description="", headcount=job_in.headcount, required_stack=[],
            responsibilities=[], seniority="mid", job_type="full-time",
            estimated_duration_months=6,
        )
        await _db.add_job_to_project(project_id, job_id)

    await _db.update_project_field(project_id, status=body.status)
    background_tasks.add_task(_run_matching_pipeline, project_id)

    result = _serialize(await _db.get_project(project_id))
    result["jobs"] = _serialize(await _db.get_jobs_by_project(project_id))
    return result


@app.patch("/api/v1/projects/{project_id}/status", tags=["Projects"])
async def update_project_status(
    project_id: str,
    body: UpdateStatusRequest,
    current_user: dict = Depends(_require_po_or_admin),
):
    project_id = sanitize_string(project_id, 100)
    s = body.status.upper()
    if s not in {"IN_PROGRESS", "FINISHED", "CANCELED"}:
        raise HTTPException(status_code=400, detail="status must be IN_PROGRESS, FINISHED, or CANCELED")
    updated = await _db.update_project_field(project_id, status=s)
    if not updated:
        raise _not_found("Project")
    return _serialize(updated)


@app.patch("/api/v1/projects/{project_id}/po", tags=["Projects"])
async def update_project_po(
    project_id: str,
    body: UpdatePORequest,
    current_user: dict = Depends(_require_admin),
):
    project_id = sanitize_string(project_id, 100)
    po_id      = validate_email_field(body.po_id)
    if not await _db.get_active_po(po_id):
        raise HTTPException(status_code=400, detail=f"No active PO user found with id '{po_id}'.")
    updated = await _db.update_project_field(project_id, po_id=po_id)
    if not updated:
        raise _not_found("Project")
    return _serialize(updated)


# ─────────────────────────────────────────────────────────────────────────────
#  MATCHES / ASSIGNMENTS
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/projects/{project_id}/matches", tags=["Matches"])
async def get_project_matches(project_id: str, current_user: dict = Depends(_get_current_user)):
    project_id = sanitize_string(project_id, 100)
    docs = await _db.list_assignments(project_id=project_id)
    result = [_assignment_to_match(d) for d in docs]
    result.sort(key=lambda x: x.get("matchScore", 0), reverse=True)
    return result


@app.get("/api/v1/matches", tags=["Matches"])
async def get_matches(
    project_id: str,
    job_id:     Optional[str] = None,
    status:     Optional[str] = None,
    current_user: dict = Depends(_get_current_user),
):
    project_id = sanitize_string(project_id, 100)
    job_id     = sanitize_string(job_id, 100) if job_id else None
    status     = sanitize_string(status, 50).lower() if status else None
    docs   = await _db.list_assignments(project_id=project_id, job_id=job_id, status=status)
    result = [_assignment_to_match(d) for d in docs]
    result.sort(key=lambda x: x.get("matchScore", 0), reverse=True)
    return result


@app.patch("/api/v1/matches/{match_id}/status", tags=["Matches"])
@app.patch("/api/v1/matches/{match_id}", tags=["Matches"], include_in_schema=False)
async def update_match_status(
    match_id: str,
    body: UpdateMatchStatusRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(_require_po_or_admin),
):
    match_id = sanitize_string(match_id, 100)
    s = body.status.upper()

    try:
        if s == "ACCEPTED":
            assignment = await _db.get_assignment(match_id)
            if not assignment:
                raise _not_found("Match")
            project_id = assignment["project_id"]

            other_pending = await _db.get_assignments_for_employee(
                assignment["employee_id"], status="pending"
            )
            other_project_ids = {
                a["project_id"] for a in other_pending if str(a.get("_id")) != match_id
            }

            await _db.accept_assignment(match_id)

            for pid in other_project_ids:
                background_tasks.add_task(_run_matching_pipeline, pid)

            all_matches = (await _build_project_details(project_id) or {}).get("matches", [])
            return {
                "action":    "accepted",
                "match_id":  match_id,
                "suggestion": None,
                "message":   "Employee accepted for this role.",
                "matches":   all_matches,
            }

        elif s == "REJECTED":
            assignment = await _db.get_assignment(match_id)
            if not assignment:
                raise _not_found("Match")
            job_id     = assignment["job_id"]
            project_id = assignment["project_id"]

            await _db.reject_assignment(match_id)

            suggestion  = None
            next_asgn   = await _db.get_next_pending_for_job(job_id, project_id)
            if next_asgn:
                m = _assignment_to_match(next_asgn)
                m["scorePercentage"] = round((next_asgn.get("adequacy_score") or 0) * 100)
                emp = await _db.get_employee(next_asgn.get("employee_id", ""))
                m["employeeName"] = emp.get("name", next_asgn.get("employee_id", "")) if emp else ""
                m["explanation"]  = next_asgn.get("explanation") or _explain_text(
                    job_id, next_asgn.get("employee_id", ""),
                    next_asgn.get("adequacy_score", 0.0),
                )
                suggestion = m
            else:
                suggestion = await _find_best_replacement(job_id, project_id)

            all_matches = (await _build_project_details(project_id) or {}).get("matches", [])

            if suggestion and suggestion.get("assignment_id"):
                msg = "Candidate rejected. Best replacement automatically assigned."
            elif suggestion:
                msg = "Candidate rejected. Next best match suggested below."
            else:
                msg = "Candidate rejected. No further candidates available for this role."

            return {
                "action":    "rejected",
                "match_id":  match_id,
                "suggestion": suggestion,
                "message":   msg,
                "matches":   all_matches,
            }

        else:
            raise HTTPException(status_code=400, detail="Only ACCEPTED or REJECTED are supported.")

    except (ValueError, HTTPException):
        raise
    except Exception as exc:
        logger.exception("Match status update failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/matches/{match_id}/reject-and-suggest", tags=["Matches"])
@app.post("/api/v1/matches/{match_id}/reject-next", tags=["Matches"], include_in_schema=False)
async def reject_and_find_next(
    match_id: str,
    current_user: dict = Depends(_require_po_or_admin),
):
    match_id   = sanitize_string(match_id, 100)
    assignment = await _db.get_assignment(match_id)
    if not assignment:
        raise _not_found("Match")
    job_id     = assignment["job_id"]
    project_id = assignment["project_id"]
    try:
        await _db.reject_assignment(match_id, reason="Rejected by user — finding next candidate.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    suggestion = await _find_best_replacement(job_id, project_id)
    return {
        "rejected_match_id": match_id,
        "suggestion":        suggestion,
        "action_required":   "none" if suggestion else "manual_search",
        "message": (
            "Best replacement automatically assigned."
            if suggestion else
            "No unassigned candidates available for this role. Please search manually."
        ),
    }


@app.post("/api/v1/matches/{match_id}/unassign", tags=["Matches"])
async def unassign_employee_endpoint(
    match_id: str,
    current_user: dict = Depends(_require_po_or_admin),
):
    match_id   = sanitize_string(match_id, 100)
    assignment = await _db.get_assignment(match_id)
    if not assignment:
        raise _not_found("Match")
    job_id     = assignment["job_id"]
    project_id = assignment["project_id"]
    try:
        await _db.unassign_employee(match_id, reason="Manually unassigned via API.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    excluded     = await _db.get_project_assigned_employee_ids(project_id)
    candidates   = await _search_employees(job_id, project_id, limit=1, min_score=0.0, exclude_ids=excluded)
    new_suggestion = None
    if candidates:
        top = candidates[0]
        new_suggestion = {
            "employee_id":      top["employee_id"],
            "score_percentage": top["score_percentage"],
        }

    all_matches = (await _build_project_details(project_id) or {}).get("matches", [])
    return {
        "action":     "unassigned",
        "match_id":   match_id,
        "suggestion": new_suggestion,
        "message":    "Employee unassigned successfully.",
        "matches":    all_matches,
    }


@app.post("/api/v1/matches/manual-swap", tags=["Matches"], status_code=201)
async def manual_swap(body: ManualSwapRequest, current_user: dict = Depends(_require_po_or_admin)):
    project_id      = sanitize_string(body.project_id, 100)
    job_id          = sanitize_string(body.job_id, 100)
    new_employee_id = sanitize_string(body.new_employee_id, 254)
    check_nosql_injection({"new_employee_id": new_employee_id})

    old_match_rejected = False
    if body.old_match_id:
        old_id   = sanitize_string(body.old_match_id, 100)
        old_asgn = await _db.get_assignment(old_id)
        if old_asgn:
            try:
                if old_asgn["status"] == "accepted":
                    await _db.unassign_employee(old_id, reason="Replaced via manual swap.")
                elif old_asgn["status"] == "pending":
                    await _db.reject_assignment(old_id, reason="Replaced via manual swap.")
                old_match_rejected = True
            except ValueError:
                pass

    try:
        scored = await _search_employees(job_id, project_id, limit=200)
        emp_score = next((r for r in scored if r["employee_id"] == new_employee_id), None)
        actual_score   = emp_score["matching_score"]   if emp_score else 0.0
        matched_skills = emp_score["matched_skills"]   if emp_score else []
        missing_skills = emp_score["missing_skills"]   if emp_score else []

        new_asgn    = await _db.create_assignment(
            employee_id=new_employee_id, project_id=project_id, job_id=job_id,
            assigned_by=current_user.get("sub", "system"), notes="",
        )
        explanation = (emp_score.get("explanation") if emp_score else None) or _explain_text(
            job_id, new_employee_id, actual_score, matched_skills, missing_skills
        )
        await _db.update_assignment_fields(
            str(new_asgn["_id"]),
            explanation    = explanation,
            adequacy_score = actual_score,
        )

        new_match = _assignment_to_match(_serialize(new_asgn))
        new_match.update({
            "explanation":     explanation,
            "scorePercentage": round(actual_score * 100),
            "matchScore":      actual_score,
            "matched_skills":  matched_skills,
            "missing_skills":  missing_skills,
        })
        emp = await _db.get_employee(new_employee_id)
        new_match["employeeName"] = emp.get("name", new_employee_id) if emp else new_employee_id

        all_matches = (await _build_project_details(project_id) or {}).get("matches", [])
        return {
            "action":              "swapped",
            "match_id":            new_match.get("id"),
            "suggestion":          None,
            "message":             "Employee successfully swapped for this role.",
            "old_match_rejected":  old_match_rejected,
            "new_match":           new_match,
            "matches":             all_matches,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Manual swap failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
#  PDF WORKFLOWS
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/api/v1/projects/parse-pdf", tags=["Projects"])
async def parse_project_pdf_only(
    request: Request,
    file: UploadFile = File(...),
    cf_turnstile_token: str = Header(default="", alias="CF-Turnstile-Token"),
    current_user: dict = Depends(_require_po_or_admin),
):
    client_ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else None)
    await verify_turnstile(cf_turnstile_token, client_ip)
    pdf_bytes = await validate_pdf_upload(file)
    pdf_hash  = hashlib.sha256(pdf_bytes).hexdigest()

    if pdf_hash in _parse_cache:
        logger.info("[parse-pdf] Cache hit for %s — skipping Docling + LLM", pdf_hash[:12])
        data = _parse_cache[pdf_hash]
    else:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name
        try:
            from po_parser.project_parser import parse_project_pdf
            data = parse_project_pdf(tmp_path)
            _parse_cache[pdf_hash] = data
        except Exception as exc:
            logger.exception("PDF parse-only failed")
            raise HTTPException(status_code=500, detail=f"PDF parsing failed: {exc}")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    meta = data.get("project", {})
    return {
        "parse_token": pdf_hash,
        "name":        meta.get("name", ""),
        "client":      meta.get("client", ""),
        "description": meta.get("description", ""),
        "jobs":        [
            j.get("title", str(j)) if isinstance(j, dict) else str(j)
            for j in data.get("jobs", [])
        ],
    }


@app.post("/api/v1/projects/ingest-pdf", tags=["Projects"], status_code=201)
async def ingest_project_pdf(
    request: Request,
    file:  UploadFile = File(...),
    po_id: str        = Form(...),
    cf_turnstile_token: str = Header(default="", alias="CF-Turnstile-Token"),
    current_user: dict = Depends(_require_po_or_admin),
):
    client_ip = request.headers.get("CF-Connecting-IP") or (request.client.host if request.client else None)
    await verify_turnstile(cf_turnstile_token, client_ip)
    po_id     = sanitize_string(po_id, 254)
    pdf_bytes = await validate_pdf_upload(file)
    pdf_hash  = hashlib.sha256(pdf_bytes).hexdigest()

    cached_data = _parse_cache.pop(pdf_hash, None)
    if cached_data:
        logger.info("[ingest-pdf] Cache hit for %s — reusing parse result, skipping Docling + LLM", pdf_hash[:12])

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        from po_parser.ingest_project import ingest_project_pdf as _ingest
        summary = await _ingest(tmp_path, po_id=po_id, parsed_data=cached_data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.exception("Project PDF ingest failed")
        raise HTTPException(status_code=500, detail=f"Project ingest failed: {exc}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    project_id = summary["project_id"]
    logger.info("[Ingest] Project '%s' saved (%d jobs). Running pipeline…",
                project_id, summary.get("jobs_count", 0))

    pipeline_triggered = False
    try:
        await _run_matching_pipeline(project_id)
        pipeline_triggered = True
        logger.info("[Ingest] Pipeline complete for '%s'", project_id)
    except Exception as exc:
        logger.error("[Ingest] Pipeline failed for '%s': %s", project_id, exc)

    doc = await _db.get_project(project_id)
    result = _serialize(doc) if doc else {
        "_id": project_id, "name": summary.get("name", ""),
        "client": summary.get("client", ""), "po_id": po_id, "status": "IN_PROGRESS",
    }
    result["jobs"]               = _serialize(await _db.get_jobs_by_project(project_id))
    result["pipeline_triggered"] = pipeline_triggered
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  SEARCH & MANUAL ASSIGN
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/api/v1/projects/{project_id}/jobs/{job_id}/candidates", tags=["Matches"])
async def search_job_candidates(
    project_id: str,
    job_id:     str,
    limit:      int = 50,
    current_user: dict = Depends(_get_current_user),
):
    project_id = sanitize_string(project_id, 100)
    job_id     = sanitize_string(job_id, 100)
    try:
        results = await _search_employees(job_id, project_id, limit=limit, min_score=0.0)
        for rank, r in enumerate(results, start=1):
            r["rank"] = rank
            # Use the rich explanation built by the search service;
            # fall back to the template if it's somehow absent.
            if not r.get("explanation"):
                r["explanation"] = _explain_text(
                    job_id, r["employee_id"], r["matching_score"],
                    r.get("matched_skills", []), r.get("missing_skills", []),
                )
        return results
    except Exception as exc:
        logger.exception("[Candidates] Failed for job '%s': %s", job_id, exc)
        raise HTTPException(status_code=500, detail=f"Candidate search failed: {exc}")


@app.post("/api/v1/projects/{project_id}/jobs/{job_id}/assign", tags=["Matches"], status_code=201)
async def manual_assign_candidate(
    project_id: str,
    job_id:     str,
    body:       ManualAssignRequest,
    current_user: dict = Depends(_require_po_or_admin),
):
    project_id = sanitize_string(project_id, 100)
    job_id     = sanitize_string(job_id, 100)
    emp_id     = sanitize_string(body.employee_id, 254)
    check_nosql_injection({"employee_id": emp_id})

    try:
        scored     = await _search_employees(job_id, project_id, limit=200)
        emp_score  = next((r for r in scored if r["employee_id"] == emp_id), None)
        actual_score   = emp_score["matching_score"] if emp_score else 0.0
        matched_skills = emp_score.get("matched_skills", []) if emp_score else []
        missing_skills = emp_score.get("missing_skills", []) if emp_score else []

        if body.replace_match_id:
            old_id   = sanitize_string(body.replace_match_id, 100)
            old_asgn = await _db.get_assignment(old_id)
            if old_asgn:
                try:
                    if old_asgn["status"] == "accepted":
                        await _db.unassign_employee(old_id, reason="Replaced")
                    else:
                        await _db.reject_assignment(old_id, reason="Replaced")
                except Exception:
                    pass

        rich_explanation = (emp_score.get("explanation") if emp_score else None) or _explain_text(
            job_id, emp_id, actual_score, matched_skills, missing_skills
        )

        existing = await _db.find_pending_assignment(emp_id, project_id, job_id)
        if existing:
            await _db.update_assignment_fields(
                str(existing["_id"]),
                explanation=rich_explanation, adequacy_score=actual_score,
            )
            result = _assignment_to_match(existing)
            result.update({
                "explanation":     rich_explanation,
                "scorePercentage": round(actual_score * 100),
                "matched_skills":  matched_skills,
                "missing_skills":  missing_skills,
            })
            all_matches = (await _build_project_details(project_id) or {}).get("matches", [])
            return {
                "action": "assigned", "match_id": result.get("id"),
                "suggestion": None, "message": "Employee assigned to this role.",
                "matches": all_matches,
            }

        new_asgn    = await _db.create_assignment(
            employee_id=emp_id, project_id=project_id, job_id=job_id,
            assigned_by=current_user.get("sub", "system"), notes="",
        )
        await _db.update_assignment_fields(
            str(new_asgn["_id"]),
            explanation=rich_explanation, adequacy_score=actual_score,
        )
        result = _assignment_to_match(_serialize(new_asgn))
        result.update({
            "explanation":     rich_explanation,
            "scorePercentage": round(actual_score * 100),
            "matched_skills":  matched_skills,
            "missing_skills":  missing_skills,
        })
        all_matches = (await _build_project_details(project_id) or {}).get("matches", [])
        return {
            "action": "assigned", "match_id": result.get("id"),
            "suggestion": None, "message": "Employee assigned to this role.",
            "matches": all_matches,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Manual assign failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/projects/{project_id}/jobs/{job_id}/candidates/{employee_id}/explain", tags=["Matches"])
async def explain_candidate_fit(
    project_id: str, job_id: str, employee_id: str,
    current_user: dict = Depends(_get_current_user),
):
    project_id  = sanitize_string(project_id, 100)
    job_id      = sanitize_string(job_id, 100)
    employee_id = sanitize_string(employee_id, 254)
    try:
        scored = await _search_employees(job_id, project_id, limit=200)
        match  = next((r for r in scored if r["employee_id"] == employee_id), None)
        explanation = (
            (match.get("explanation") if match else None)
            or _explain_text(
                job_id, employee_id,
                match["matching_score"]  if match else 0.0,
                match.get("matched_skills", []) if match else [],
                match.get("missing_skills", []) if match else [],
            )
        )
        return {"explanation": explanation, "job_id": job_id, "employee_id": employee_id}
    except Exception as exc:
        logger.exception("Explain candidate fit failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/assignments/{assignment_id}/reject-with-suggestion", tags=["Matches"])
async def reject_assignment_with_suggestion(
    assignment_id: str,
    current_user: dict = Depends(_require_po_or_admin),
):
    assignment_id = sanitize_string(assignment_id, 100)
    try:
        asgn = await _db.get_assignment(assignment_id)
        if not asgn:
            raise HTTPException(status_code=404, detail="Assignment not found")
        job_id     = asgn.get("job_id")
        project_id = asgn.get("project_id")

        await _db.reject_assignment(assignment_id, reason="Rejected by user")

        candidates = await _search_employees(
            job_id, project_id, limit=1,
            exclude_ids={asgn.get("employee_id")},
        )
        if not candidates:
            return {"message": "Assignment rejected", "assignment_id": assignment_id, "suggestion": None}

        top = candidates[0]
        top["explanation"] = _explain_text(
            job_id, top["employee_id"], top["matching_score"],
            top.get("matched_skills", []), top.get("missing_skills", []),
        )
        return {"message": "Assignment rejected", "assignment_id": assignment_id, "suggestion": top}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Reject with suggestion failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ─────────────────────────────────────────────────────────────────────────────
#  JIRA SYNC
# ─────────────────────────────────────────────────────────────────────────────
async def _run_jira_sync(date: str | None = None) -> dict:
    import httpx

    base_url   = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    jira_email = os.environ.get("JIRA_EMAIL", "")
    jira_token = os.environ.get("JIRA_API_TOKEN", "")

    if not base_url or not jira_email or not jira_token:
        raise ValueError(
            "JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN must be set in .env"
        )

    auth    = (jira_email, jira_token)
    headers = {"Accept": "application/json"}
    stats   = {"projects": 0, "issues_processed": 0, "tasks_added": 0, "skipped": 0}
    _email_cache: dict[str, str] = {}

    async with httpx.AsyncClient(auth=auth, headers=headers, timeout=30) as client:

        resp     = await client.get(f"{base_url}/rest/api/3/project/search", params={"maxResults": 100})
        resp.raise_for_status()
        projects = resp.json().get("values", [])
        stats["projects"] = len(projects)
        logger.info("[JiraSync] Found %d project(s)", len(projects))

        for project in projects:
            key  = project["key"]
            name = project["name"]

            date_filter = f' AND updated >= "{date}"' if date else ""
            jql     = f'project = "{key}" AND statusCategory = Done{date_filter} ORDER BY updated ASC'
            issues  = []
            start   = 0
            while True:
                r = await client.get(
                    f"{base_url}/rest/api/3/search/jql",
                    params={
                        "jql":        jql,
                        "startAt":    start,
                        "maxResults": 100,
                        "fields":     "summary,description,assignee,customfield_10016,labels,updated,issuetype",
                    },
                )
                r.raise_for_status()
                batch = r.json().get("issues", [])
                issues.extend(batch)
                start += len(batch)
                if start >= r.json().get("total", 0):
                    break

            logger.info("[JiraSync] [%s] %d done issue(s)", key, len(issues))

            for issue in issues:
                fields     = issue["fields"]
                assignee   = fields.get("assignee") or {}
                account_id = assignee.get("accountId", "").strip()
                if not account_id:
                    stats["skipped"] += 1
                    continue

                if account_id not in _email_cache:
                    try:
                        ur = await client.get(
                            f"{base_url}/rest/api/3/user",
                            params={"accountId": account_id},
                        )
                        _email_cache[account_id] = ur.json().get("emailAddress", "").strip()
                    except Exception:
                        _email_cache[account_id] = ""

                emp_email = _email_cache[account_id]
                if not emp_email:
                    stats["skipped"] += 1
                    continue

                story_pts  = int(fields.get("customfield_10016") or 0)
                difficulty = "hard" if story_pts >= 8 else "medium" if story_pts >= 3 else "easy"

                desc_text = ""
                for block in (fields.get("description") or {}).get("content", []):
                    for inline in block.get("content", []):
                        if inline.get("type") == "text":
                            desc_text += inline.get("text", "")

                issue_date  = (fields.get("updated") or "")[:10]
                last_update = await _db.get_last_update(emp_email)
                if last_update and issue_date and issue_date <= last_update:
                    stats["skipped"] += 1
                    continue

                stats["issues_processed"] += 1
                try:
                    added = await _db.add_jira_task(
                        email          = emp_email,
                        project_id     = key,
                        project_name   = name,
                        jira_id        = issue["key"],
                        title          = fields.get("summary", ""),
                        description    = desc_text.strip(),
                        technologies   = fields.get("labels", []),
                        story_points   = story_pts,
                        difficulty     = difficulty,
                        task_type      = (fields.get("issuetype") or {}).get("name", "task").lower(),
                        responsibility = "implementation",
                        date           = issue_date,
                    )
                    if added:
                        stats["tasks_added"] += 1
                except Exception as exc:
                    logger.warning("[JiraSync] Failed to save task %s for %s: %s",
                                   issue["key"], emp_email, exc)

    return stats


@app.post("/api/v1/jira/sync", tags=["Jira"])
async def jira_sync(
    background_tasks: BackgroundTasks,
    date: Optional[str] = None,
    current_user: dict  = Depends(_require_admin),
):
    if date:
        date = sanitize_string(date, 20)
        import re as _re
        if not _re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD format.")

    background_tasks.add_task(_run_jira_sync, date)
    return {
        "message":     "Jira sync started in the background.",
        "date_filter": date or "all (no filter)",
    }


# ─────────────────────────────────────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def _startup_event():
    loop = asyncio.get_event_loop()

    # ── 1. Beanie ODM ─────────────────────────────────────────────────────────
    try:
        from db.models import Employee, Job, Project, Assignment, User, CVUploadLog
        from motor.motor_asyncio import AsyncIOMotorClient
        import beanie

        motor_client = AsyncIOMotorClient(os.environ["MONGODB_URL"])
        await beanie.init_beanie(
            database        = motor_client[os.getenv("DB_NAME", "Profile")],
            document_models = [Employee, Job, Project, Assignment, User, CVUploadLog],
        )
        logger.info("[Startup] Beanie ODM initialised")
    except Exception as exc:
        logger.critical("[Startup] Beanie init failed: %s", exc, exc_info=True)
        # FIX: re-raise so uvicorn refuses to serve traffic with a broken DB layer
        raise

    # ── 2. A2A agent servers ───────────────────────────────────────────────────
    try:
        await loop.run_in_executor(None, _ensure_a2a_servers)
        logger.info("[Startup] A2A agents ready on ports 8101 / 8102 / 8103 / 8104")
    except Exception as exc:
        logger.error("[Startup] A2A agent startup failed: %s", exc)

    # ── 3. Neo4j KG cache warm-up ─────────────────────────────────────────────
    try:
        kg      = await loop.run_in_executor(None, _get_kg)
        n_edges = sum(len(v) for v in kg.values())
        logger.info("[Startup] KG cache warm: %d skill nodes | %d edges", len(kg), n_edges)
    except Exception as exc:
        logger.error("[Startup] KG warm-up failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
#  GLOBAL EXCEPTION HANDLER
# ─────────────────────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def _global_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s", request.url)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred."},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host    = os.getenv("HOST", "0.0.0.0"),
        port    = int(os.getenv("PORT", "8000")),
        reload  = os.getenv("RELOAD", "true").lower() == "true",
        workers = int(os.getenv("WORKERS", "1")),
    )