# SmartStaff Backend — API Reference

## Base URL

```
http://localhost:8000
```

## Authentication

All endpoints except `/auth/login` and `/auth/register` require a valid JWT token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

---

## Authentication Endpoints

### POST `/auth/login`

User login. Returns JWT access token.

**Request:**
```json
{
  "email": "user@company.com",
  "password": "secure_password",
  "turnstile_token": "0.A1B2C3D4..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "user@company.com",
    "email": "user@company.com",
    "name": "John Doe",
    "role": "PO",
    "is_sys_admin": false
  }
}
```

**Error (401 Unauthorized):**
```json
{
  "detail": "Invalid email or password"
}
```

---

### POST `/auth/logout`

User logout. Invalidates the current session.

**Request:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

---

### POST `/auth/refresh`

Refresh JWT token (extend expiration).

**Request:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## CV Management Endpoints

### POST `/cv/upload`

Upload and parse a CV (PDF).

**Request:**
- **Content-Type:** `multipart/form-data`
- **Fields:**
  - `file` (binary) — PDF file (max 50 MB)
  - `email` (string) — employee email (optional; extracted from CV if omitted)
  - `turnstile_token` (string) — Cloudflare Turnstile token

```bash
curl -X POST http://localhost:8000/cv/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@resume.pdf" \
  -F "email=alice@company.com" \
  -F "turnstile_token=0.A1B2C3D4..."
```

**Response (200 OK):**
```json
{
  "_id": "alice@company.com",
  "email": "alice@company.com",
  "name": "Alice Smith",
  "current_role": "Senior Python Engineer",
  "skills": [
    "Python",
    "FastAPI",
    "Docker",
    "MongoDB",
    "LLM",
    "LangGraph"
  ],
  "education": [
    {
      "degree": "M.S.",
      "field": "Computer Science",
      "school": "Stanford University",
      "year": 2020
    }
  ],
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect",
      "issuer": "AWS",
      "date": "2024"
    }
  ],
  "projects": [
    {
      "project_id": "PROJECT-001",
      "client": "Google",
      "role": "Backend Engineer",
      "start_date": "2022-06",
      "end_date": null,
      "technologies": ["Python", "FastAPI", "MongoDB"]
    }
  ],
  "source": {
    "cv_parsed": true,
    "jira_sync": false,
    "last_update": "2026-06-16"
  }
}
```

**Error (400 Bad Request):**
```json
{
  "detail": "Invalid PDF: file too large or corrupted"
}
```

---

### GET `/cv/{email}`

Retrieve stored employee profile.

**Request:**
```
Authorization: Bearer <token>
GET /cv/alice@company.com
```

**Response (200 OK):**
```json
{
  "_id": "alice@company.com",
  "email": "alice@company.com",
  "name": "Alice Smith",
  "current_role": "Senior Python Engineer",
  "skills": ["Python", "FastAPI", "Docker", ...],
  ...
}
```

---

### GET `/cv/list`

List all employee profiles.

**Query Parameters:**
- `skip` (integer, default=0) — pagination offset
- `limit` (integer, default=50) — max records

**Response (200 OK):**
```json
{
  "employees": [
    {
      "_id": "alice@company.com",
      "name": "Alice Smith",
      "current_role": "Senior Python Engineer",
      "skills": [...]
    },
    {
      "_id": "bob@company.com",
      "name": "Bob Johnson",
      "current_role": "DevOps Engineer",
      "skills": [...]
    }
  ],
  "total": 47,
  "skip": 0,
  "limit": 50
}
```

---

## Project Intake Endpoints

### POST `/po/upload`

Upload and parse a project document (PO/specification).

**Request:**
- **Content-Type:** `multipart/form-data`
- **Fields:**
  - `file` (binary) — PDF file (max 100 MB)
  - `project_name` (string, optional) — override detected name
  - `turnstile_token` (string) — Cloudflare Turnstile token

```bash
curl -X POST http://localhost:8000/po/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@project_spec.pdf" \
  -F "project_name=CRM_Platform" \
  -F "turnstile_token=0.A1B2C3D4..."
```

**Response (201 Created):**
```json
{
  "_id": "PROJECT-001",
  "name": "CRM Platform",
  "client": "Acme Corp",
  "description": "Enterprise CRM system with real-time sync...",
  "technology_stack": [
    "Python",
    "FastAPI",
    "React",
    "PostgreSQL",
    "Docker",
    "Kubernetes"
  ],
  "functional_needs": [
    "User authentication",
    "Customer management",
    "Real-time notifications"
  ],
  "non_functional_needs": [
    "99.9% uptime",
    "Support 10k+ concurrent users",
    "Response time < 200ms"
  ],
  "job_ids": [
    "JOB-001",
    "JOB-002",
    "JOB-003"
  ],
  "status": "IN_PROGRESS",
  "ingested_at": "2026-06-16T10:30:00Z"
}
```

---

### GET `/po/{project_id}`

Retrieve project details.

**Request:**
```
Authorization: Bearer <token>
GET /po/PROJECT-001
```

**Response (200 OK):**
```json
{
  "_id": "PROJECT-001",
  "name": "CRM Platform",
  "client": "Acme Corp",
  ...
}
```

---

### GET `/po/list`

List all projects.

**Query Parameters:**
- `skip` (integer, default=0)
- `limit` (integer, default=50)
- `status` (string, optional) — filter by status (IN_PROGRESS, COMPLETED, ARCHIVED)

**Response (200 OK):**
```json
{
  "projects": [...],
  "total": 12,
  "skip": 0,
  "limit": 50
}
```

---

## Matching Pipeline Endpoints

### POST `/matching/run`

Execute the full matching pipeline.

**Request:**
```json
{
  "employee_ids": [
    "alice@company.com",
    "bob@company.com",
    "charlie@company.com"
  ],
  "job_ids": [
    "JOB-001",
    "JOB-002"
  ],
  "project_id": "PROJECT-001",
  "timeout_seconds": 600,
  "max_iterations": 3
}
```

**Response (202 Accepted):**
```json
{
  "run_id": "run_20260616_103045_abc123",
  "status": "RUNNING",
  "created_at": "2026-06-16T10:30:45Z",
  "message": "Pipeline execution started. Check /matching/status/{run_id} for updates."
}
```

---

### GET `/matching/status/{run_id}`

Check pipeline execution status.

**Request:**
```
Authorization: Bearer <token>
GET /matching/status/run_20260616_103045_abc123
```

**Response (200 OK) — Running:**
```json
{
  "run_id": "run_20260616_103045_abc123",
  "status": "RUNNING",
  "current_step": "validation_agent",
  "current_iteration": 2,
  "progress_percent": 65,
  "elapsed_seconds": 42.5,
  "estimated_remaining_seconds": 25
}
```

**Response (200 OK) — Completed:**
```json
{
  "run_id": "run_20260616_103045_abc123",
  "status": "COMPLETED",
  "current_step": "explanation_agent",
  "current_iteration": 2,
  "progress_percent": 100,
  "elapsed_seconds": 67.3,
  "assignments": [
    {
      "employee_id": "alice@company.com",
      "job_id": "JOB-001",
      "project_id": "PROJECT-001",
      "adequacy_score": 0.92,
      "explanation": "Excellent match: 9/10 core skills, experience with similar projects, strong seniority alignment."
    },
    {
      "employee_id": "bob@company.com",
      "job_id": "JOB-002",
      "project_id": "PROJECT-001",
      "adequacy_score": 0.78,
      "explanation": "Good fit: 7/10 core skills, some gap skills in DevOps tooling but transferable from Kubernetes experience."
    }
  ],
  "metadata": {
    "total_iterations": 2,
    "total_employees": 3,
    "total_jobs": 2,
    "unmatched_jobs": 0
  }
}
```

**Response (200 OK) — Failed:**
```json
{
  "run_id": "run_20260616_103045_abc123",
  "status": "FAILED",
  "error": "Timeout: scoring_agent exceeded 300s",
  "error_details": "NVIDIA API unavailable or very slow",
  "elapsed_seconds": 300.1
}
```

---

### GET `/matching/results/{run_id}`

Retrieve full matching results (assignments + metadata).

**Request:**
```
Authorization: Bearer <token>
GET /matching/results/run_20260616_103045_abc123
```

**Response (200 OK):**
```json
{
  "run_id": "run_20260616_103045_abc123",
  "status": "COMPLETED",
  "created_at": "2026-06-16T10:30:45Z",
  "completed_at": "2026-06-16T10:31:52Z",
  "assignments": [
    {
      "_id": "ObjectId(...)",
      "employee_id": "alice@company.com",
      "project_id": "PROJECT-001",
      "job_id": "JOB-001",
      "adequacy_score": 0.92,
      "explanation": "...",
      "status": "pending",
      "assigned_by": "po@company.com"
    }
  ],
  "metadata": {
    "total_iterations": 2,
    "total_employees_evaluated": 3,
    "total_jobs": 2,
    "matched_jobs": 2,
    "matching_algorithm": "Hungarian (scipy.optimize.linear_sum_assignment)",
    "average_score": 0.85,
    "min_score": 0.78,
    "max_score": 0.92
  }
}
```

---

## Assignment Management Endpoints

### GET `/assignments/list`

List all assignments.

**Query Parameters:**
- `skip` (integer, default=0)
- `limit` (integer, default=50)
- `status` (string, optional) — filter by status (pending, accepted, rejected, unassigned)
- `project_id` (string, optional) — filter by project
- `employee_id` (string, optional) — filter by employee

**Response (200 OK):**
```json
{
  "assignments": [
    {
      "_id": "ObjectId(...)",
      "employee_id": "alice@company.com",
      "project_id": "PROJECT-001",
      "job_id": "JOB-001",
      "assigned_by": "po@company.com",
      "status": "pending",
      "adequacy_score": 0.92,
      "explanation": "Excellent match...",
      "created_at": "2026-06-16T10:30:45Z",
      "updated_at": "2026-06-16T10:30:45Z"
    }
  ],
  "total": 5,
  "skip": 0,
  "limit": 50
}
```

---

### GET `/assignments/{assignment_id}`

Retrieve a single assignment.

**Request:**
```
Authorization: Bearer <token>
GET /assignments/507f1f77bcf86cd799439011
```

**Response (200 OK):**
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "employee_id": "alice@company.com",
  "project_id": "PROJECT-001",
  "job_id": "JOB-001",
  "assigned_by": "po@company.com",
  "status": "pending",
  "adequacy_score": 0.92,
  "explanation": "Excellent match...",
  "notes": "",
  "created_at": "2026-06-16T10:30:45Z",
  "updated_at": "2026-06-16T10:30:45Z"
}
```

---

### PATCH `/assignments/{assignment_id}`

Update assignment status (accept/reject).

**Request:**
```json
{
  "status": "accepted",
  "notes": "Approved by resource manager"
}
```

**Response (200 OK):**
```json
{
  "_id": "507f1f77bcf86cd799439011",
  "employee_id": "alice@company.com",
  "project_id": "PROJECT-001",
  "job_id": "JOB-001",
  "status": "accepted",
  "updated_at": "2026-06-16T10:45:00Z",
  ...
}
```

---

## Admin Endpoints

### GET `/admin/users`

List all portal users.

**Request:**
```
Authorization: Bearer <token> (admin only)
GET /admin/users?role=PO&skip=0&limit=50
```

**Query Parameters:**
- `role` (string, optional) — filter by role (PO, RH, ADMIN)
- `skip` (integer, default=0)
- `limit` (integer, default=50)

**Response (200 OK):**
```json
{
  "users": [
    {
      "_id": "po@company.com",
      "email": "po@company.com",
      "name": "Project Owner",
      "role": "PO",
      "is_sys_admin": false,
      "active": true,
      "created_at": "2025-01-01T00:00:00Z",
      "last_login": "2026-06-16T09:00:00Z"
    }
  ],
  "total": 3,
  "skip": 0,
  "limit": 50
}
```

---

### POST `/admin/users`

Create a new portal user.

**Request:**
```json
{
  "email": "newuser@company.com",
  "name": "New User",
  "password": "temporary_password",
  "role": "RH",
  "is_sys_admin": false
}
```

**Response (201 Created):**
```json
{
  "_id": "newuser@company.com",
  "email": "newuser@company.com",
  "name": "New User",
  "role": "RH",
  "is_sys_admin": false,
  "active": true,
  "created_at": "2026-06-16T10:50:00Z"
}
```

---

### PATCH `/admin/users/{email}`

Update user profile.

**Request:**
```json
{
  "name": "Updated Name",
  "role": "ADMIN",
  "active": true
}
```

**Response (200 OK):**
```json
{
  "_id": "newuser@company.com",
  "email": "newuser@company.com",
  "name": "Updated Name",
  "role": "ADMIN",
  "is_sys_admin": false,
  "active": true
}
```

---

### DELETE `/admin/users/{email}`

Deactivate or delete a user.

**Request:**
```
Authorization: Bearer <token> (admin only)
DELETE /admin/users/newuser@company.com
```

**Response (204 No Content)**

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message",
  "error_code": "ERROR_CODE",
  "timestamp": "2026-06-16T10:50:00Z"
}
```

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | OK — request succeeded |
| 201 | Created — resource created |
| 202 | Accepted — async operation started |
| 204 | No Content — delete/update succeeded |
| 400 | Bad Request — invalid input |
| 401 | Unauthorized — missing/invalid JWT token |
| 403 | Forbidden — insufficient permissions |
| 404 | Not Found — resource doesn't exist |
| 409 | Conflict — resource already exists |
| 429 | Too Many Requests — rate limited |
| 500 | Internal Server Error — unexpected exception |
| 503 | Service Unavailable — database/LLM down |

---

## WebSocket Endpoints (Real-Time Updates)

### WS `/ws/pipeline/{run_id}`

Subscribe to real-time pipeline execution updates.

**Connect:**
```javascript
const ws = new WebSocket(
  'ws://localhost:8000/ws/pipeline/run_20260616_103045_abc123',
  ['Authorization', 'Bearer <token>']
);

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Pipeline update:', update);
};
```

**Message Format:**
```json
{
  "event": "step_started",
  "step": "scoring_agent",
  "iteration": 1,
  "timestamp": "2026-06-16T10:30:45Z"
}
```

**Message Types:**
- `pipeline_started` — execution began
- `step_started` — agent step initiated
- `step_completed` — agent step finished (with results)
- `iteration_completed` — one iteration finished
- `pipeline_completed` — entire pipeline done (with assignments)
- `pipeline_failed` — error occurred

---

## Rate Limiting

All endpoints are rate-limited:
- **500 requests per hour** per user
- **10 requests per minute** for `/matching/run` (heavy computation)
- **100 requests per minute** for `/cv/upload` and `/po/upload`

If you exceed the limit, you'll get:

```json
{
  "detail": "Rate limit exceeded. Try again in 60 seconds.",
  "retry_after_seconds": 60
}
```

---

## Examples

### Complete Workflow: Upload CV → Upload PO → Run Matching

```bash
# 1. Login
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"po@company.com","password":"pass","turnstile_token":"0.A1B2..."}' \
  | jq -r '.access_token')

# 2. Upload employee CVs
curl -X POST http://localhost:8000/cv/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@alice.pdf" \
  -F "turnstile_token=0.A1B2..."

curl -X POST http://localhost:8000/cv/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@bob.pdf" \
  -F "turnstile_token=0.A1B2..."

# 3. Upload project document
curl -X POST http://localhost:8000/po/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@project_spec.pdf" \
  -F "turnstile_token=0.A1B2..."

# 4. Run matching pipeline
RUN_ID=$(curl -X POST http://localhost:8000/matching/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "employee_ids":["alice@company.com","bob@company.com"],
    "job_ids":["JOB-001","JOB-002"],
    "project_id":"PROJECT-001"
  }' | jq -r '.run_id')

# 5. Check status (poll every 5s)
while true; do
  curl -X GET "http://localhost:8000/matching/status/$RUN_ID" \
    -H "Authorization: Bearer $TOKEN" | jq '.'
  sleep 5
done

# 6. Once completed, fetch results
curl -X GET "http://localhost:8000/matching/results/$RUN_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

# 7. Accept/reject assignments
curl -X PATCH "http://localhost:8000/assignments/507f1f77bcf86cd799439011" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status":"accepted","notes":"Approved by RH"}'
```

---

## Support

For API issues or questions:
1. Check this reference document
2. Review test files (`tests/test_*.py`) for usage examples
3. Enable debug logging: `export LOG_LEVEL=DEBUG` before running
4. Check Raindrop Workshop UI for tracing: `http://localhost:5899`
