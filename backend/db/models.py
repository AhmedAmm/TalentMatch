"""
db/models.py
=============
Beanie ODM document models for every MongoDB collection.

Beanie wraps the native async PyMongo driver and exposes an ORM-style API:
  - class-level find / get / count queries (no raw filter dicts)
  - instance-level .save() / .insert() / .delete()
  - Pydantic v2 validation on every read and write

These classes are the single source of truth for data shape.
No raw ``$set`` / ``$addToSet`` / ``find_one`` calls appear in
business logic — all queries go through the ORM methods here or
through db/operations.py.

Collections
-----------
  employees      → Employee
  jobs           → Job
  projects       → Project
  assignment     → Assignment   (ObjectId PK — Beanie default)
  users          → User
  cv_upload_logs → CVUploadLog  (ObjectId PK)

Initialisation (call once at startup)
--------------------------------------
    from db.models import init_beanie_odm
    await init_beanie_odm()
"""
from __future__ import annotations

import os
from typing import Any, Optional

from beanie import Document, init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ──────────────────────────────────────────────────────────────────────────────
# Shared sub-models  (plain Pydantic — not Documents)
# ──────────────────────────────────────────────────────────────────────────────

class JiraTaskComplexity(BaseModel):
    story_points:   int = 0
    difficulty:     Optional[str] = "medium"
    type:           Optional[str] = ""
    responsibility: Optional[str] = "implementation"


class JiraTask(BaseModel):
    jira_id:      str
    title:        Optional[str] = ""
    description:  Optional[str] = ""
    technologies: list[str] = []
    complexity:   JiraTaskComplexity = Field(default_factory=JiraTaskComplexity)
    date:         Optional[str] = ""


class EmployeeProject(BaseModel):
    project_id:   str
    client:       Optional[str] = ""   # null-safe: some DB docs store null
    role:         Optional[str] = ""
    start_date:   Optional[str] = None
    end_date:     Optional[str] = None
    technologies: list[str] = []
    tasks:        list[Any] = []       # raw Any — normalized to list[JiraTask] by validator

    @field_validator("tasks", mode="before")
    @classmethod
    def _normalize_tasks(cls, v: list) -> list:
        """
        Coerce legacy string tasks → minimal JiraTask dicts.
        Old CV-parsed documents stored tasks as plain description strings.
        """
        result = []
        for item in (v or []):
            if isinstance(item, str):
                result.append(JiraTask(jira_id="legacy", description=item))
            elif isinstance(item, dict):
                result.append(JiraTask.model_validate(item))
            elif isinstance(item, JiraTask):
                result.append(item)
            # silently drop anything else (None, int, …)
        return result


class SkillSource(BaseModel):
    cv_parsed:   bool = False
    jira_sync:   bool = False
    last_update: Optional[str] = None


class Certification(BaseModel):
    """Structured certification entry matching the DB schema {name, issuer, date}."""
    name:   str = ""
    issuer: str = ""
    date:   str = ""


# ──────────────────────────────────────────────────────────────────────────────
# employees   (string _id = email)
# ──────────────────────────────────────────────────────────────────────────────

class Employee(Document):
    """Beanie ODM document for the ``employees`` collection."""
    model_config = ConfigDict(populate_by_name=True)

    id:             str = Field(alias="_id")   # email is the primary key
    email:          str = ""
    name:           str = ""
    current_role:   str = ""
    available:      bool = True
    education:      list[Any] = []
    certifications: list[Certification] = []   # objects {name, issuer, date}
    skills:         list[str] = []
    projects:       list[EmployeeProject] = []
    source:         SkillSource = Field(default_factory=SkillSource)

    class Settings:
        name         = "employees"
        use_revision = False

    def to_dict(self) -> dict:
        d = self.model_dump(by_alias=False)
        d["_id"] = d.pop("id")
        return d

    def merge_skills(self, new_skills: list[str]) -> None:
        """Merge without duplicates (ORM-style $addToSet)."""
        self.skills = list(dict.fromkeys(self.skills + new_skills))

    def merge_projects(self, new_projects: list[dict]) -> None:
        """Add project stubs that are not already present by project_id."""
        existing_ids = {p.project_id for p in self.projects}
        for p in new_projects:
            pid = p.get("project_id") if isinstance(p, dict) else p.project_id
            if pid not in existing_ids:
                self.projects.append(
                    EmployeeProject.model_validate(p) if isinstance(p, dict) else p
                )
                existing_ids.add(pid)


# ──────────────────────────────────────────────────────────────────────────────
# jobs   (string _id = job_id)
# ──────────────────────────────────────────────────────────────────────────────

class Job(Document):
    """Beanie ODM document for the ``jobs`` collection."""
    model_config = ConfigDict(populate_by_name=True)

    id:                        str = Field(alias="_id")
    project_id:                str
    title:                     str = ""
    description:               str = ""
    headcount:                 int = 1
    required_stack:            list[Any] = []
    responsibilities:          list[str] = []
    seniority:                 str = ""
    type:                      str = ""
    estimated_duration_months: int = 0
    filled:                    int = 0
    remaining:                 int = 1
    embedding:                 list[float] = []

    class Settings:
        name         = "jobs"
        use_revision = False

    def to_dict(self) -> dict:
        d = self.model_dump(by_alias=False)
        d["_id"] = d.pop("id")
        return d

    def apply_headcount_delta(self, delta: int) -> None:
        """Increment filled / decrement remaining by ``delta``."""
        self.filled    += delta
        self.remaining -= delta


# ──────────────────────────────────────────────────────────────────────────────
# projects   (string _id = project_id)
# ──────────────────────────────────────────────────────────────────────────────

class Project(Document):
    """Beanie ODM document for the ``projects`` collection."""
    model_config = ConfigDict(populate_by_name=True)

    id:                   str = Field(alias="_id")
    name:                 str = ""
    client:               str = ""
    description:          str = ""
    source_pdf:           Optional[str] = None
    functional_needs:     list[str] = []
    non_functional_needs: list[str] = []
    technology_stack:     list[str] = []
    embedding:            list[float] = []
    job_ids:              list[str] = []
    po_id:                Optional[str] = None
    ingested_at:          Optional[str] = None
    status:               str = "IN_PROGRESS"

    class Settings:
        name         = "projects"
        use_revision = False

    def to_dict(self) -> dict:
        d = self.model_dump(by_alias=False)
        d["_id"] = d.pop("id")
        return d

    def add_job(self, job_id: str) -> None:
        if job_id not in self.job_ids:
            self.job_ids.append(job_id)


# ──────────────────────────────────────────────────────────────────────────────
# assignment   (ObjectId _id — Beanie default)
# ──────────────────────────────────────────────────────────────────────────────

class Assignment(Document):
    """Beanie ODM document for the ``assignment`` collection."""
    employee_id:    str
    project_id:     str
    job_id:         str
    assigned_by:    str
    status:         str = "pending"    # pending | accepted | rejected | unassigned
    adequacy_score: Optional[float] = None
    explanation:    str = ""
    notes:          str = ""
    created_at:     str = ""
    updated_at:     str = ""

    class Settings:
        name         = "assignment"
        use_revision = False

    def to_dict(self) -> dict:
        d = self.model_dump()
        d["_id"] = str(self.id)
        d.pop("id", None)
        return d


# ──────────────────────────────────────────────────────────────────────────────
# users   (string _id = email)
# ──────────────────────────────────────────────────────────────────────────────

class User(Document):
    """Beanie ODM document for the ``users`` collection."""
    model_config = ConfigDict(populate_by_name=True)

    id:              str = Field(alias="_id")
    email:           str = ""
    name:            str = ""
    role:            str = ""    # PO | RH | ADMIN
    is_sys_admin:    bool = False
    active:          bool = True
    hashed_password: str = ""
    created_at:      Optional[str] = None
    last_login:      Optional[str] = None

    class Settings:
        name         = "users"
        use_revision = False

    def to_dict(self) -> dict:
        d = self.model_dump(by_alias=False)
        d["_id"] = d.pop("id")
        d.pop("hashed_password", None)   # never expose the hash
        return d


# ──────────────────────────────────────────────────────────────────────────────
# cv_upload_logs   (ObjectId _id)
# ──────────────────────────────────────────────────────────────────────────────

class CVUploadLog(Document):
    """Beanie ODM document for the ``cv_upload_logs`` collection."""
    email:       str
    filename:    Optional[str] = None
    uploaded_at: str = ""

    class Settings:
        name         = "cv_upload_logs"
        use_revision = False


# ──────────────────────────────────────────────────────────────────────────────
# Beanie initialisation
# ──────────────────────────────────────────────────────────────────────────────

_mongo_client: Optional[AsyncIOMotorClient] = None


async def init_beanie_odm() -> None:
    """
    Initialise Beanie with the native async PyMongo client.

    Call once at application startup (FastAPI on_event / lifespan, or CLI).
    Safe to call multiple times — reinitialises if already called.
    """
    global _mongo_client
    from dotenv import load_dotenv
    load_dotenv()

    url     = os.environ["MONGODB_URL"]
    db_name = os.getenv("DB_NAME", "Profile")

    _motor_client = AsyncIOMotorClient(url)
    await init_beanie(
        database        = _motor_client[db_name],
        document_models = [Employee, Job, Project, Assignment, User, CVUploadLog],
    )