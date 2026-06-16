# SmartStaff Backend API Specification — Optimized for Minimal Round-Trips

## Context

You are maintaining `nw_main2.py`, a FastAPI backend for SmartStaff (AI-powered employee-project matching). The frontend is a React SPA that currently makes too many API calls per user action. This document specifies **all** endpoints the backend must expose, with emphasis on new composite endpoints that reduce frontend round-trips.

**Key principle: Every action endpoint must return enough data so the frontend NEVER needs to call `loadData()` again after an action.**

---

## Database Collections (MongoDB)

- `users` — `{ _id: str (email), name, email, role: "PO"|"RH"|"ADMIN", password_hash, active }`
- `employees` — `{ _id: str (email), name, email, current_role, skills[], education[], certifications[], projects[], cv_filename, available, avatar_url, stats: { technical, communication, leadership, problemSolving, teamwork } }`
- `projects` — `{ _id: str, name, client, description, status: "IN_PROGRESS"|"FINISHED"|"CANCELED", po_id, job_ids[] }`
- `jobs` — `{ _id: str, project_id, title, description, headcount, required_stack[], responsibilities[], seniority, job_type, estimated_duration_months }`
- `assignments` — `{ _id: str, employee_id, project_id, job_id, status: "pending"|"accepted"|"rejected", adequacy_score: float 0-1, explanation, notes, assigned_by, assigned_at }`

---

## Existing Helper Functions (keep as-is)

```python
def _serialize(doc)          # Recursively converts ObjectId → str, strips password_hash
def _serialize_employee(doc) # Returns { id, name, email, about, skills, isAvailable, avatarUrl, experiences[], stats }
def _assignment_to_match(doc) # Returns { id, projectId, jobId, employeeId, status, matchReason, matchScore, scorePercentage, explanation }
def _get_current_user(authorization) # JWT auth dependency
def _require_admin(current_user)     # Admin/RH guard
def _require_po_or_admin(current_user) # PO/Admin/RH guard
```

---

## NEW Helper Function to Add

```python
def _get_project_assigned_employee_ids(project_id: str) -> set[str]:
    """Return all employee IDs with pending or accepted assignments in this project (any job)."""
    docs = _db.assignments.find(
        {"project_id": project_id, "status": {"$in": ["pending", "accepted"]}},
        {"employee_id": 1}
    )
    return {d["employee_id"] for d in docs}


def _build_project_details(project_id: str) -> dict:
    """
    Build the full project details payload in ONE database sweep.
    Returns { project, matches[] } where each match has embedded employee summary.
    This is the single-source-of-truth response for the project details page.
    """
    proj = _db.get_project(project_id)
    if not proj:
        return None

    result = _serialize(proj)
    result["jobs"] = _serialize(list(_db.jobs.find({"project_id": project_id})))

    # Get all non-rejected assignments
    assignment_docs = list(_db.assignments.find({
        "project_id": project_id,
        "status": {"$in": ["pending", "accepted"]}
    }))

    # Batch-fetch all referenced employees in ONE query
    emp_ids = list({a["employee_id"] for a in assignment_docs})
    emp_docs = {
        d["_id"]: d
        for d in _db.employees.find({"_id": {"$in": emp_ids}})
    } if emp_ids else {}

    matches = []
    for a in assignment_docs:
        a["_id"] = str(a["_id"])
        m = _assignment_to_match(a)

        # Embed lightweight employee summary (no full experiences/projects)
        emp = emp_docs.get(a["employee_id"])
        if emp:
            stored_stats = emp.get("stats", {})
            m["employee"] = {
                "id":        emp.get("_id") or emp.get("email", ""),
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

    # Sort by score descending
    matches.sort(key=lambda x: x.get("matchScore", 0), reverse=True)
    result["matches"] = matches
    return result
```

---

## ENDPOINT SPECIFICATION

### 1. Health

#### `GET /health`
- **Auth:** None
- **Response:** `{ "status": "ok" }`

#### `GET /`
- **Auth:** None
- **Response:** `{ "status": "ok", "service": "SmartStaff API", "version": "2.0.0" }`

---

### 2. Auth

#### `POST /api/v1/auth/login`
- **Auth:** None
- **Body:** `{ "email": str, "password": str }`
- **Response:** `{ "access_token": str, "token_type": "bearer", "user": { "id", "name", "email", "role" } }`
- **IMPORTANT:** Return the `user` object directly in the login response so the frontend doesn't need a second `GET /auth/me` call. The `user` object must include `id` (same as `_id`), `name`, `email`, and `role`.

#### `GET /api/v1/auth/me`
- **Auth:** Bearer JWT
- **Response:** `{ "_id", "name", "email", "role" }`

#### `POST /api/v1/auth/logout`
- **Auth:** Bearer JWT
- **Response:** `{ "message": "Logged out successfully." }`

---

### 3. Users (Admin)

#### `GET /api/v1/users`
- **Auth:** Admin/RH
- **Response:** `[ { "_id", "name", "email", "role", "active" }, ... ]`

#### `POST /api/v1/users`
- **Auth:** Admin/RH
- **Body:** `{ "name", "email", "role": "PO"|"RH"|"ADMIN", "password" }`
- **Response (201):** The created user object

#### `DELETE /api/v1/users/{user_id}`
- **Auth:** Admin/RH
- **Response (204):** No content

---

### 4. Employees

#### `GET /api/v1/employees`
- **Auth:** Any authenticated user
- **Query:** `?search=str&available=bool`
- **Response:** `[ { id, name, email, about, skills[], isAvailable, avatarUrl, experiences[], stats } ]`

#### `GET /api/v1/employees/{employee_id}`
- **Auth:** Any authenticated user
- **Response:** Full employee object with experiences, stats, etc.

#### `POST /api/v1/employees/upload-cv`
- **Auth:** Any authenticated user
- **Body:** FormData with `email` + `file` (PDF)
- **Response (201):** Employee object with `"created": true` or `"updated": true`

---

### 5. Projects

#### `GET /api/v1/projects`
- **Auth:** Any authenticated user
- **Query:** `?po_id=str&status=str`
- **Response:** `[ { _id, name, client, status, po_id, jobs: [{ _id, title, headcount }] } ]`
- **Note:** Each project includes its jobs array. No matches — this is for the dashboard list view.

#### ★ `GET /api/v1/projects/{project_id}/details` — **NEW COMPOSITE ENDPOINT**
- **Auth:** Any authenticated user
- **Purpose:** Single call that returns everything the project details page needs. Replaces 3 separate calls (`getProjectById` + `getMatchesForProject` + `getEmployees`).
- **Response:**
```json
{
  "_id": "proj_abc123",
  "name": "Project Alpha",
  "client": "Acme Corp",
  "status": "IN_PROGRESS",
  "po_id": "user@example.com",
  "description": "",
  "jobs": [
    { "_id": "job_1", "title": "Backend Developer", "headcount": 3, "project_id": "proj_abc123" },
    { "_id": "job_2", "title": "DevOps Engineer", "headcount": 1, "project_id": "proj_abc123" }
  ],
  "matches": [
    {
      "id": "match_001",
      "projectId": "proj_abc123",
      "jobId": "job_1",
      "employeeId": "alice@company.com",
      "status": "ACCEPTED",
      "matchScore": 0.85,
      "scorePercentage": 85,
      "matchReason": "",
      "explanation": "Strong match based on Python, FastAPI, and PostgreSQL experience...",
      "employee": {
        "id": "alice@company.com",
        "name": "Alice Martin",
        "email": "alice@company.com",
        "about": "Senior Backend Developer",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "avatarUrl": null,
        "stats": { "technical": 85, "communication": 70, "leadership": 60, "problemSolving": 80, "teamwork": 75 }
      }
    },
    {
      "id": "match_002",
      "projectId": "proj_abc123",
      "jobId": "job_1",
      "employeeId": "bob@company.com",
      "status": "PENDING",
      "matchScore": 0.72,
      "scorePercentage": 72,
      "explanation": "Good fit for Python requirements but lacks FastAPI experience...",
      "employee": {
        "id": "bob@company.com",
        "name": "Bob Smith",
        "email": "bob@company.com",
        "about": "Full Stack Developer",
        "skills": ["Python", "Django", "React"],
        "avatarUrl": null,
        "stats": { "technical": 75, "communication": 65, "leadership": 50, "problemSolving": 70, "teamwork": 80 }
      }
    }
  ]
}
```
- **Implementation:** Use `_build_project_details(project_id)`. Only returns pending + accepted matches (not rejected). Employee data is embedded — no separate employee fetch needed.
- **This is the MOST IMPORTANT endpoint for performance.**

#### `GET /api/v1/projects/{project_id}`
- **Auth:** Any authenticated user
- **Response:** Project + jobs (no matches, no employees). Keep for backward compatibility.

#### `POST /api/v1/projects`
- **Auth:** PO/Admin/RH
- **Body:** `{ "name", "client", "status", "poId", "jobs": [{ "title", "headcount" }] }`
- **Response (201):** Project object with jobs array. Pipeline runs in background.

#### `PATCH /api/v1/projects/{project_id}/status`
- **Auth:** PO/Admin/RH
- **Body:** `{ "status": "IN_PROGRESS"|"FINISHED"|"CANCELED" }`
- **Response:** Updated project object (same shape as `GET /projects/{id}`)

#### `PATCH /api/v1/projects/{project_id}/po`
- **Auth:** Admin/RH only
- **Body:** `{ "po_id": str }`
- **Response:** Updated project object

---

### 6. PDF Ingestion

#### `POST /api/v1/projects/parse-pdf`
- **Auth:** PO/Admin/RH
- **Body:** FormData with `file` (PDF)
- **Response:** `{ "name", "client", "description", "jobs": ["title1", "title2"] }`
- **Note:** Preview only — does NOT write to DB.

#### `POST /api/v1/projects/ingest-pdf`
- **Auth:** PO/Admin/RH
- **Body:** FormData with `file` (PDF) + `po_id` (str)
- **Response:** Full project object with jobs + `pipeline_triggered: bool`
- **Note:** Parses PDF → saves project + jobs → runs matching pipeline SYNCHRONOUSLY → returns result.

---

### 7. Matches / Assignments — **ACTION ENDPOINTS**

**Critical design rule:** Every action endpoint must return the full updated `matches[]` array (with embedded employees) for the affected project, so the frontend can replace its local state in one shot without calling `GET /projects/{id}/details` again.

The response shape for action endpoints:

```json
{
  "action": "accepted" | "rejected" | "unassigned" | "assigned" | "swapped",
  "match_id": "the affected match ID",
  "suggestion": null | { ... },          // only for reject/unassign
  "message": "Human-readable message",
  "matches": [                            // FULL updated match list for this project
    { "id", "projectId", "jobId", "employeeId", "status", "matchScore", "scorePercentage", "explanation",
      "employee": { "id", "name", "email", "about", "skills", "avatarUrl", "stats" }
    }
  ]
}
```

#### `GET /api/v1/projects/{project_id}/matches`
- **Auth:** Any authenticated user
- **Response:** `[ { id, projectId, jobId, employeeId, status, matchReason, matchScore, scorePercentage, explanation } ]`
- **Note:** Keep for backward compat, but frontend should prefer `/projects/{id}/details`.

#### ★ `PATCH /api/v1/matches/{match_id}/status` — **UPDATED**
- **Auth:** PO/Admin/RH
- **Body:** `{ "status": "ACCEPTED" | "REJECTED" }`
- **For ACCEPTED:**
  1. Mark assignment as accepted
  2. Automatically reject other pending assignments for the same employee in other projects (optional, run matching pipeline for affected projects in background)
  3. Return updated matches for this project
- **For REJECTED:**
  1. Mark assignment as rejected
  2. Look for next pending assignment for the same job (sorted by score desc)
  3. If none found, use SearchService to find next best candidate NOT already assigned to this project (pending or accepted on ANY job)
  4. If a new candidate is found from SearchService, create a new pending assignment with computed score + explanation
  5. Return updated matches for this project + suggestion info
- **Response:**
```json
{
  "action": "accepted",
  "match_id": "match_001",
  "message": "Employee accepted for this role.",
  "matches": [ ... full updated match list with embedded employees ... ]
}
```
or for REJECTED:
```json
{
  "action": "rejected",
  "match_id": "match_002",
  "suggestion": {
    "id": "match_003",
    "employeeId": "carol@company.com",
    "employeeName": "Carol Davis",
    "scorePercentage": 68,
    "explanation": "..."
  },
  "message": "Candidate rejected. Next best match suggested.",
  "matches": [ ... full updated match list with embedded employees ... ]
}
```

#### ★ `POST /api/v1/matches/{match_id}/unassign` — **UPDATED**
- **Auth:** PO/Admin/RH
- **Behavior:** Unassign an accepted employee. Run pipeline in background for replacement.
- **Response:** Same action response shape with `"action": "unassigned"` + full `matches[]`.

#### ★ `POST /api/v1/projects/{project_id}/jobs/{job_id}/assign` — **UPDATED**
- **Auth:** PO/Admin/RH
- **Body:** `{ "employee_id": str, "replace_match_id": str | null }`
- **CRITICAL FIX:** 
  1. Compute score via SearchService BEFORE creating assignment
  2. Check if a pending assignment already exists for this employee+job+project — if so, update it instead of creating duplicate
  3. Generate explanation
  4. Optionally reject the old match if `replace_match_id` is provided
- **Response:** Action response with `"action": "assigned"` + full `matches[]`.

#### `POST /api/v1/matches/manual-swap` — Keep but fix
- **Auth:** PO/Admin/RH
- **Body:** `{ "project_id", "job_id", "new_employee_id", "old_match_id?" }`
- **FIX:** Compute real score via SearchService before creating assignment (same fix as manual assign).
- **Response:** Action response with `"action": "swapped"` + full `matches[]`.

---

### 8. Candidate Search

#### `GET /api/v1/projects/{project_id}/jobs/{job_id}/candidates`
- **Auth:** Any authenticated user
- **Query:** `?limit=50`
- **Response:** `{ "job_id", "job_title", "candidates": [ { "employee_id", "name", "matching_score", "score_percentage", "rank", "matched_skills", "missing_skills", "explanation" } ] }`
- **CRITICAL FIX:** Filter out ALL employees who have a pending or accepted assignment on ANY job in this project. Use `_get_project_assigned_employee_ids(project_id)`. Fetch `limit * 2` from SearchService, filter, then trim to `limit`.

#### `POST /api/v1/projects/{project_id}/jobs/{job_id}/candidates/{employee_id}/explain`
- **Auth:** Any authenticated user
- **Response:** `{ "explanation", "job_id", "employee_id" }`

---

### 9. CV Generation

#### `POST /api/v1/cv/generate`
- **Auth:** Any authenticated user
- **Body:** `{ "employee_id", "project_id?", "job_id?", "language": "en" }`
- **Response:** Binary .docx file

#### `GET /api/v1/employees/{employee_id}/generate-cv`
- **Auth:** Any authenticated user
- **Query:** `?project_id=str&job_id=str&language=en`
- **Response:** Binary .docx file

---

### 10. System (Admin)

#### `GET /api/v1/graph/stats`
- **Auth:** Admin/RH
- **Response:** `{ "loaded": bool, ... stats }`

#### `POST /api/v1/graph/refresh`
- **Auth:** Admin/RH
- **Response:** `{ "message", ... stats }`

---

## Summary of Changes from Current `nw_main2.py`

### New Endpoints
1. **`GET /api/v1/projects/{project_id}/details`** — Composite endpoint returning project + jobs + matches with embedded employee data. Implementation uses `_build_project_details()`.

### Modified Endpoints
2. **`POST /api/v1/auth/login`** — Include `user` object in response (avoid extra `/auth/me` call).
3. **`PATCH /api/v1/matches/{match_id}/status`** — Return full `matches[]` with embedded employees for the project.
4. **`POST /api/v1/matches/{match_id}/unassign`** — Return full `matches[]`.
5. **`POST /api/v1/projects/{pid}/jobs/{jid}/assign`** — Compute score BEFORE creating assignment. Check for existing pending assignment to avoid duplicates. Return full `matches[]`.
6. **`POST /api/v1/matches/manual-swap`** — Compute real score via SearchService. Return full `matches[]`.
7. **`GET /api/v1/projects/{pid}/jobs/{jid}/candidates`** — Exclude employees already assigned (pending/accepted) to ANY job in this project.

### New Helper Functions
8. **`_get_project_assigned_employee_ids(project_id)`** — Returns set of employee IDs with pending/accepted assignments in project.
9. **`_build_project_details(project_id)`** — Builds composite response with embedded employee data.

### Bug Fixes (from previous session)
10. `ProjectJobIn` model: add `headcount: int = 1` field.
11. `create_project`: use `job_in.headcount` instead of hardcoded `1`.
12. All SearchService usages: use `_get_project_assigned_employee_ids()` for exclusion.
13. `manual_assign_candidate`: compute score BEFORE `_db.create_assignment()`, check for existing pending assignment.

---

## Call Reduction Summary

| Page / Action | Before (calls) | After (calls) | Saved |
|---|---|---|---|
| Project details load | 3 (project + matches + employees) | **1** (`/details`) | 2 |
| Accept match | 1 + 3 reload = 4 | **1** (returns matches) | 3 |
| Reject match | 1-2 + 3 reload = 4-5 | **1** (returns matches) | 3-4 |
| Unassign | 1 + 3 reload = 4 | **1** (returns matches) | 3 |
| Manual assign/swap | 1 + 3 reload = 4 | **1** (returns matches) | 3 |
| Status change | 1 + 3 reload = 4 | **1** (returns project) + no match reload needed | 3 |
| Login | 1-2 (login + /me) | **1** (login returns user) | 0-1 |
| **Total per session** | **~20-30 calls** | **~8-10 calls** | **~60% reduction** |
