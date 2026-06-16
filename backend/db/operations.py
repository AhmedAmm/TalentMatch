"""
db/operations.py
===========
Async public DB interface — the only file the rest of the application imports
for data access.

Every operation uses the Beanie ODM (db/models.py).
No raw PyMongo query operators ($set, $addToSet, find_one …) appear here.
All mutations go through .save() on a Beanie Document instance.

Function signatures are identical to the previous bare-PyMongo version so
every call-site in nw_main2.py / routers/tools.py remains unchanged,
except callers must now ``await`` the results.

Prerequisites
-------------
    await init_beanie_odm()     # called in nw_main2.py lifespan / startup

Usage
-----
    from db.operations import get_employee, add_employee
    emp = await get_employee("alice@example.com")
"""
from __future__ import annotations

from datetime import datetime

from db.models import Assignment, Certification, CVUploadLog, Employee, EmployeeProject, Job, JiraTask, JiraTaskComplexity, Project, User


# ──────────────────────────────────────────────────────────────────────────────
# Employee
# ──────────────────────────────────────────────────────────────────────────────

async def add_employee(
    email: str,
    name: str,
    current_role: str,
    education: list = None,
    certifications: list = None,
    skills: list = None,
    projects: list = None,
    cv_filename: str = None,
) -> dict:
    """
    Create the employee if they don't exist, or update ALL their CV fields.
    Skills and projects are merged (no duplicates) — never wiped.
    Jira-synced tasks are never touched.
    """
    if not email or not isinstance(email, str):
        raise ValueError("Valid email is required")

    education      = education or []
    certifications = [
        Certification.model_validate(c) if isinstance(c, dict) else c
        for c in (certifications or [])
    ]
    new_skills     = list(set(skills or []))
    new_projects   = projects or []

    emp = await Employee.get(email)
    if emp is None:
        emp = Employee(
            id=email,
            email=email,
            name=name,
            current_role=current_role,
            education=education,
            certifications=certifications,
            skills=new_skills,
            available=True,
        )
        emp.source.cv_parsed   = True
        emp.source.last_update = datetime.utcnow().strftime("%Y-%m-%d")
        emp.merge_projects(new_projects)
        await emp.insert()
    else:
        emp.name           = name
        emp.current_role   = current_role
        emp.education      = education
        emp.certifications = certifications
        emp.source.cv_parsed   = True
        emp.source.last_update = datetime.utcnow().strftime("%Y-%m-%d")
        emp.merge_skills(new_skills)
        emp.merge_projects(new_projects)
        await emp.save()

    # Log the CV upload
    log = CVUploadLog(email=email, filename=cv_filename, uploaded_at=datetime.utcnow().isoformat())
    await log.insert()

    print(f"[DB] CV upserted for '{email}'.")
    return emp.to_dict()


async def upsert_employee_from_jira(email: str, name: str) -> None:
    """Create a minimal employee document if it doesn't exist yet."""
    if not email:
        raise ValueError("Valid email is required")
    existing = await Employee.get(email)
    if existing is None:
        emp = Employee(id=email, email=email, name=name, available=True)
        await emp.insert()


async def add_jira_task(
    email: str,
    project_id: str,
    project_name: str,
    jira_id: str,
    title: str,
    description: str,
    technologies: list,
    story_points: int,
    difficulty: str,
    task_type: str,
    responsibility: str,
    date: str,
) -> bool:
    """
    Add a task to an employee's project.
    Creates the project stub if it doesn't exist yet.
    Skips silently if the task (jira_id) was already added.
    """
    if not email:
        raise ValueError("Email is required")

    technologies = technologies or []
    await upsert_employee_from_jira(email, "")

    emp = await Employee.get(email)
    if emp is None:
        return False

    # Find or create the project entry
    proj_entry = next(
        (p for p in emp.projects if p.project_id == project_id), None
    )
    if proj_entry is None:
        proj_entry = EmployeeProject(
            project_id=project_id,
            client=project_name,
        )
        emp.projects.append(proj_entry)

    # Skip if task already exists
    if any(t.jira_id == jira_id for t in proj_entry.tasks):
        print(f"[DB] Task '{jira_id}' already exists, skipping.")
        return False

    task = JiraTask(
        jira_id=jira_id,
        title=title,
        description=description,
        technologies=technologies,
        complexity=JiraTaskComplexity(
            story_points=story_points,
            difficulty=difficulty,
            type=task_type,
            responsibility=responsibility,
        ),
        date=date,
    )
    proj_entry.tasks.append(task)

    # Merge technologies into project and global skills
    proj_entry.technologies = list(dict.fromkeys(proj_entry.technologies + technologies))
    emp.merge_skills(technologies)
    emp.source.jira_sync   = True
    emp.source.last_update = datetime.utcnow().strftime("%Y-%m-%d")

    await emp.save()
    print(f"[DB] Task '{jira_id}' → '{email}' | added: True")
    return True


async def get_employee(email: str) -> dict | None:
    emp = await Employee.get(email)
    return emp.to_dict() if emp else None


async def get_last_update(email: str) -> str | None:
    emp = await Employee.get(email)
    return emp.source.last_update if emp else None


async def employee_exists(email: str) -> bool:
    return await Employee.get(email) is not None


# ──────────────────────────────────────────────────────────────────────────────
# Projects
# ──────────────────────────────────────────────────────────────────────────────

async def upsert_project(
    project_id: str,
    name: str,
    client_name: str,
    description: str,
    functional_needs: list,
    non_functional_needs: list,
    technology_stack: list,
    job_ids: list,
    po_id: str = None,
    source_pdf: str = None,
    embedding: list = None,
) -> dict:
    """Insert or update a project document."""
    if not project_id:
        raise ValueError("project_id is required")

    if po_id:
        po = await User.find_one(User.id == po_id, User.role == "PO", User.active != False)
        if not po:
            raise ValueError(
                f"No PO user found for id: '{po_id}'. "
                "Make sure the user exists and has role 'PO'."
            )

    proj = await Project.get(project_id)
    if proj is None:
        proj = Project(
            id=project_id,
            name=name,
            client=client_name,
            description=description,
            source_pdf=source_pdf,
            functional_needs=functional_needs or [],
            non_functional_needs=non_functional_needs or [],
            technology_stack=technology_stack or [],
            embedding=embedding or [],
            ingested_at=datetime.utcnow().strftime("%Y-%m-%d"),
            po_id=po_id,
        )
        for jid in (job_ids or []):
            proj.add_job(jid)
        await proj.insert()
    else:
        proj.name                 = name
        proj.client               = client_name
        proj.description          = description
        proj.source_pdf           = source_pdf
        proj.functional_needs     = functional_needs or []
        proj.non_functional_needs = non_functional_needs or []
        proj.technology_stack     = technology_stack or []
        proj.embedding            = embedding or []
        proj.ingested_at          = datetime.utcnow().strftime("%Y-%m-%d")
        if po_id:
            proj.po_id = po_id
        for jid in (job_ids or []):
            proj.add_job(jid)
        await proj.save()

    print(f"[DB] Project upserted: '{project_id}'.")
    return proj.to_dict()


async def add_job_to_project(project_id: str, job_id: str) -> None:
    """Add a job_id reference to a project's job_ids array (no duplicates)."""
    proj = await Project.get(project_id)
    if proj:
        proj.add_job(job_id)
        await proj.save()


async def get_project(project_id: str) -> dict | None:
    proj = await Project.get(project_id)
    return proj.to_dict() if proj else None


# ──────────────────────────────────────────────────────────────────────────────
# Jobs
# ──────────────────────────────────────────────────────────────────────────────

async def upsert_job(
    job_id: str,
    project_id: str,
    title: str,
    description: str,
    headcount: int,
    required_stack: list,
    responsibilities: list,
    seniority: str,
    job_type: str,
    estimated_duration_months: int,
    embedding: list = None,
) -> dict:
    """
    Insert or update a job document.
    On insert: filled=0, remaining=headcount.
    On update: only metadata changes; filled/remaining managed by accept/unassign.
    """
    if not job_id or not project_id:
        raise ValueError("job_id and project_id are required")

    job = await Job.get(job_id)
    if job is None:
        job = Job(
            id=job_id,
            project_id=project_id,
            title=title,
            description=description,
            headcount=headcount,
            required_stack=required_stack or [],
            responsibilities=responsibilities or [],
            seniority=seniority,
            type=job_type,
            estimated_duration_months=estimated_duration_months,
            embedding=embedding or [],
            filled=0,
            remaining=headcount,
        )
        await job.insert()
    else:
        job.project_id                = project_id
        job.title                     = title
        job.description               = description
        job.headcount                 = headcount
        job.required_stack            = required_stack or []
        job.responsibilities          = responsibilities or []
        job.seniority                 = seniority
        job.type                      = job_type
        job.estimated_duration_months = estimated_duration_months
        job.embedding                 = embedding or []
        await job.save()

    print(f"[DB] Job upserted: '{job_id}' → project '{project_id}'.")
    return job.to_dict()


async def get_job(job_id: str) -> dict | None:
    job = await Job.get(job_id)
    return job.to_dict() if job else None


async def get_jobs_by_project(project_id: str) -> list:
    """Return all jobs for a given project."""
    docs = await Job.find(Job.project_id == project_id).to_list()
    return [j.to_dict() for j in docs]


async def get_open_jobs(project_id: str = None) -> list:
    """Return all jobs where remaining > 0, optionally filtered by project."""
    from beanie.operators import GT
    conditions = [GT(Job.remaining, 0)]
    if project_id:
        conditions.append(Job.project_id == project_id)
    docs = await Job.find(*conditions).to_list()
    return [j.to_dict() for j in docs]


# ──────────────────────────────────────────────────────────────────────────────
# Assignments
# ──────────────────────────────────────────────────────────────────────────────

async def create_assignment(
    employee_id: str,
    project_id: str,
    job_id: str,
    assigned_by: str,
    notes: str = "",
) -> dict:
    """Create a new assignment in 'pending' status."""
    if not employee_id or not project_id or not job_id or not assigned_by:
        raise ValueError("employee_id, project_id, job_id, and assigned_by are all required")

    emp = await Employee.get(employee_id)
    if not emp:
        raise ValueError(f"Employee '{employee_id}' not found")
    if not emp.available:
        raise ValueError(f"Employee '{employee_id}' is not available for assignment")

    job = await Job.get(job_id)
    if not job:
        raise ValueError(f"Job '{job_id}' not found")
    if job.remaining <= 0:
        raise ValueError(f"Job '{job_id}' has no remaining headcount")

    now = datetime.utcnow().isoformat()
    a   = Assignment(
        employee_id=employee_id,
        project_id=project_id,
        job_id=job_id,
        assigned_by=assigned_by,
        status="pending",
        created_at=now,
        updated_at=now,
        notes=notes,
    )
    await a.insert()
    print(f"[DB] Assignment created: '{a.id}' → employee '{employee_id}' / job '{job_id}'")
    return a.to_dict()


async def accept_assignment(assignment_id: str) -> dict:
    """
    Accept a pending assignment.
    Side-effects: employee → unavailable, other pending cleared, job filled++.
    """
    from beanie import PydanticObjectId
    from beanie.operators import NE
    try:
        oid = PydanticObjectId(assignment_id)
    except Exception:
        raise ValueError(f"Invalid assignment id: '{assignment_id}'")

    a = await Assignment.get(oid)
    if not a:
        raise ValueError(f"Assignment '{assignment_id}' not found")
    if a.status != "pending":
        raise ValueError(
            f"Assignment '{assignment_id}' is '{a.status}', only 'pending' can be accepted"
        )

    # Mark accepted
    a.status     = "accepted"
    a.updated_at = datetime.utcnow().isoformat()
    await a.save()

    # Employee → unavailable
    emp = await Employee.get(a.employee_id)
    if emp:
        emp.available = False
        await emp.save()

    # Delete other pending assignments for this employee
    others = await Assignment.find(
        Assignment.employee_id == a.employee_id,
        Assignment.status      == "pending",
        NE(Assignment.id,        a.id),
    ).to_list()
    for other in others:
        await other.delete()
    if others:
        print(f"[DB] Removed {len(others)} other pending assignment(s) for '{a.employee_id}'")

    # Job filled++
    job = await Job.get(a.job_id)
    if job:
        job.apply_headcount_delta(1)
        await job.save()

    print(f"[DB] Assignment '{assignment_id}' accepted → "
          f"employee '{a.employee_id}' marked unavailable")
    return a.to_dict()


async def reject_assignment(assignment_id: str, reason: str = "") -> dict:
    """Reject a pending assignment. Employee stays available; job counters unchanged."""
    from beanie import PydanticObjectId
    try:
        oid = PydanticObjectId(assignment_id)
    except Exception:
        raise ValueError(f"Invalid assignment id: '{assignment_id}'")

    a = await Assignment.get(oid)
    if not a:
        raise ValueError(f"Assignment '{assignment_id}' not found")
    if a.status != "pending":
        raise ValueError(
            f"Assignment '{assignment_id}' is '{a.status}', only 'pending' can be rejected"
        )

    a.status     = "rejected"
    a.updated_at = datetime.utcnow().isoformat()
    if reason:
        a.notes = reason
    await a.save()

    print(f"[DB] Assignment '{assignment_id}' rejected")
    return a.to_dict()


async def unassign_employee(assignment_id: str, reason: str = "") -> dict:
    """Remove an accepted assignment and make the employee available again."""
    from beanie import PydanticObjectId
    try:
        oid = PydanticObjectId(assignment_id)
    except Exception:
        raise ValueError(f"Invalid assignment id: '{assignment_id}'")

    a = await Assignment.get(oid)
    if not a:
        raise ValueError(f"Assignment '{assignment_id}' not found")
    if a.status != "accepted":
        raise ValueError(
            f"Assignment '{assignment_id}' is '{a.status}', only 'accepted' can be unassigned"
        )

    a.status     = "unassigned"
    a.updated_at = datetime.utcnow().isoformat()
    if reason:
        a.notes = reason
    await a.save()

    emp = await Employee.get(a.employee_id)
    if emp:
        emp.available = True
        await emp.save()

    job = await Job.get(a.job_id)
    if job:
        job.apply_headcount_delta(-1)
        await job.save()

    print(f"[DB] Assignment '{assignment_id}' unassigned → "
          f"employee '{a.employee_id}' is available again")
    return a.to_dict()


async def get_assignment(assignment_id: str) -> dict | None:
    """Fetch a single assignment by its ObjectId string."""
    from beanie import PydanticObjectId
    try:
        oid = PydanticObjectId(assignment_id)
    except Exception:
        return None
    a = await Assignment.get(oid)
    return a.to_dict() if a else None


async def get_assignments_for_employee(employee_id: str, status: str = None) -> list:
    """Return all assignments for an employee, optionally filtered by status."""
    query = [Assignment.employee_id == employee_id]
    if status:
        query.append(Assignment.status == status)
    docs = await Assignment.find(*query).to_list()
    return [a.to_dict() for a in docs]


async def get_assignments_for_job(job_id: str, status: str = None) -> list:
    """Return all assignments for a job, optionally filtered by status."""
    query = [Assignment.job_id == job_id]
    if status:
        query.append(Assignment.status == status)
    docs = await Assignment.find(*query).to_list()
    return [a.to_dict() for a in docs]


# ──────────────────────────────────────────────────────────────────────────────
# Users
# ──────────────────────────────────────────────────────────────────────────────

async def get_user(user_id: str) -> dict | None:
    """Fetch a single user by ID (email), excluding password_hash."""
    doc = await User.get(user_id)
    if not doc:
        return None
    d = doc.to_dict()
    d.pop("hashed_password", None)
    return d


async def list_users() -> list:
    """Return all users, excluding password_hash."""
    docs = await User.find().to_list()
    result = []
    for doc in docs:
        d = doc.to_dict()
        d.pop("hashed_password", None)
        result.append(d)
    return result


async def get_active_po(po_id: str) -> dict | None:
    """Return a user only if they exist, have role PO, and are active."""
    doc = await User.find_one(
        User.id == po_id,
        User.role == "PO",
        User.active != False,  # noqa: E712
    )
    return doc.to_dict() if doc else None


# ──────────────────────────────────────────────────────────────────────────────
# Projects (extra queries)
# ──────────────────────────────────────────────────────────────────────────────

async def list_projects(po_id: str = None, status: str = None) -> list:
    """Return projects, optionally filtered by PO or status."""
    conditions = []
    if po_id:
        conditions.append(Project.po_id == po_id)
    if status:
        conditions.append(Project.status == status)
    docs = await Project.find(*conditions).to_list()
    return [p.to_dict() for p in docs]


async def update_project_field(project_id: str, **fields) -> dict | None:
    """
    Update one or more scalar fields on a project document.
    Example: await update_project_field(pid, status="FINISHED", po_id="x@y.com")
    """
    proj = await Project.get(project_id)
    if not proj:
        return None
    for key, value in fields.items():
        setattr(proj, key, value)
    await proj.save()
    return proj.to_dict()


# ──────────────────────────────────────────────────────────────────────────────
# Employees (extra queries)
# ──────────────────────────────────────────────────────────────────────────────

async def list_employees(search: str = None, available: bool = None) -> list:
    """
    Return employees, optionally filtered by availability and/or a search string
    (name or email contains, case-insensitive).
    """
    conditions = []
    if available is not None:
        conditions.append(Employee.available == available)
    docs = await Employee.find(*conditions).to_list()
    if search:
        sl = search.lower()
        docs = [d for d in docs if sl in d.name.lower() or sl in d.email.lower()]
    return [e.to_dict() for e in docs]


# ──────────────────────────────────────────────────────────────────────────────
# Assignments (extra queries)
# ──────────────────────────────────────────────────────────────────────────────

async def list_assignments(
    project_id: str = None,
    job_id: str = None,
    status: str = None,
    statuses: list[str] = None,
) -> list:
    """
    Flexible assignment query.
    `statuses` is a list (e.g. ["pending","accepted"]); `status` is a single value.
    Both can be combined with project_id / job_id filters.
    """
    from beanie.operators import In
    conditions = []
    if project_id:
        conditions.append(Assignment.project_id == project_id)
    if job_id:
        conditions.append(Assignment.job_id == job_id)
    if statuses:
        conditions.append(In(Assignment.status, statuses))
    elif status:
        conditions.append(Assignment.status == status)
    docs = await Assignment.find(*conditions).to_list()
    return [a.to_dict() for a in docs]


async def find_pending_assignment(
    employee_id: str, project_id: str, job_id: str
) -> dict | None:
    """Return a pending assignment for a specific (employee, project, job) triple."""
    doc = await Assignment.find_one(
        Assignment.employee_id == employee_id,
        Assignment.project_id == project_id,
        Assignment.job_id == job_id,
        Assignment.status == "pending",
    )
    return doc.to_dict() if doc else None


async def get_next_pending_for_job(job_id: str, project_id: str) -> dict | None:
    """Return the highest-scored pending assignment for a job, or None."""
    docs = await Assignment.find(
        Assignment.job_id == job_id,
        Assignment.project_id == project_id,
        Assignment.status == "pending",
    ).sort(-Assignment.adequacy_score).limit(1).to_list()
    return docs[0].to_dict() if docs else None


async def update_assignment_fields(assignment_id: str, **fields) -> None:
    """
    Patch one or more fields on an assignment without changing its status.
    Example: await update_assignment_fields(aid, explanation="...", adequacy_score=0.87)
    """
    from beanie import PydanticObjectId
    try:
        oid = PydanticObjectId(assignment_id)
    except Exception:
        return
    a = await Assignment.get(oid)
    if a:
        for key, value in fields.items():
            setattr(a, key, value)
        a.updated_at = datetime.utcnow().isoformat()
        await a.save()


async def get_project_assigned_employee_ids(project_id: str) -> set[str]:
    """
    Return the set of employee IDs that have a pending or accepted assignment
    anywhere in the given project.  Used to prevent double-booking.
    """
    from beanie.operators import In
    docs = await Assignment.find(
        Assignment.project_id == project_id,
        In(Assignment.status, ["pending", "accepted"]),
    ).to_list()
    return {a.employee_id for a in docs}