# SmartStaff Backend Documentation

## Overview

SmartStaff is an intelligent **employee-to-project matching system** powered by AI and a **knowledge graph** that understands technology transferability. It combines:

1. **Profile Management** — Parse CVs, extract skills/projects/education
2. **Project Intake** — Parse project documents (POs), extract requirements
3. **Matching Pipeline** — Use a scoring agent + Hungarian algorithm for optimal assignments
4. **Validation & Explanation** — AI-driven review and recommendation explanation

---

## Architecture

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React/Vite)                   │
│                                                              │
│  Login → Dashboard → Upload CV/PO → View Matches → Assign  │
└────────────────────┬────────────────────────────────────────┘
                     │ (REST API + WebSockets)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND (main.py)                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Security Layer                                      │   │
│  │  - Authentication (JWT) / Authorization              │   │
│  │  - NoSQL Injection Prevention                        │   │
│  │  - PDF Validation                                    │   │
│  │  - Turnstile (CAPTCHA) Verification                 │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Business Logic Routers                              │   │
│  │  - /auth → User login/logout                         │   │
│  │  - /cv → CV upload, parsing, extraction             │   │
│  │  - /po → Project document intake                     │   │
│  │  - /matching → Run full matching pipeline            │   │
│  │  - /assignments → Manage assignments                 │   │
│  │  - /admin → User management                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Services Layer (services/)                          │   │
│  │  - PDF Extraction (Docling)                          │   │
│  │  - LLM Calls (NVIDIA NIM)                            │   │
│  │  - Raindrop Workshop (tracing)                       │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Database Layer (db/)                               │   │
│  │  - Beanie ODM (async PyMongo wrapper)                │   │
│  │  - Models: Employee, Job, Project, Assignment, User │   │
│  │  - Operations: CRUD queries                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Matching Pipeline (matching_pipeline_v2/)           │   │
│  │                                                       │   │
│  │  1. Scoring Agent → N×M score matrix                 │   │
│  │  2. Hungarian Algorithm → optimal assignment         │   │
│  │  3. Validation Agent → human-in-loop check           │   │
│  │  4. Coefficient Tuner Agent → gap skills boost       │   │
│  │  5. Explanation Agent → recommendations              │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   MongoDB (Beanie ODM)     │
        │   Collections:             │
        │   - employees              │
        │   - jobs                   │
        │   - projects               │
        │   - assignment             │
        │   - users                  │
        │   - cv_upload_logs         │
        └────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │   Neo4j Knowledge Graph    │
        │   (tech transferability)   │
        └────────────────────────────┘
```

---

## Module Reference

### 1. **Database Layer** (`db/`)

#### `db/models.py`

Beanie ODM document models — the single source of truth for all MongoDB data.

**Collections:**
- `employees` (PK: email)
- `jobs` (PK: job_id)
- `projects` (PK: project_id)
- `assignment` (PK: ObjectId)
- `users` (PK: email)
- `cv_upload_logs` (PK: ObjectId)

**Key Classes:**
- `Employee` — person profile extracted from CV + enriched with JIRA tasks
- `Job` — specific hiring slot within a project
- `Project` — client project with requirements and tech stack
- `Assignment` — matching result: employee → job
- `User` — portal user (PO, RH, ADMIN)

**Usage:**
```python
from db.models import init_beanie_odm, Employee
await init_beanie_odm()  # Call once at startup

emp = await Employee.get("alice@example.com")
emp.merge_skills(["Python", "Docker"])
await emp.save()
```

#### `db/operations.py`

High-level async CRUD interface. All business logic imports this, never raw PyMongo.

**Key Functions:**
- `add_employee(email, name, ...)` — upsert employee from CV
- `get_employee(email)` — fetch by email
- `list_employees()` — all employees
- `add_job(job_id, project_id, ...)` — upsert job
- `get_job(job_id)` — fetch job
- `add_project(project_id, ...)` — upsert project
- `add_assignment(employee_id, project_id, job_id, ...)` — create assignment record

---

### 2. **Services Layer** (`services/`)

#### `services/llm.py`

NVIDIA NIM LLM client with Raindrop Workshop integration.

**Used by:**
- `po_parser/` — extract requirements from PO PDFs
- `profile_update/` — parse CV text and JIRA tasks
- `scripts/update_kg.py` — maintain knowledge graph

**Key Functions:**
- `ask_llm(prompt, system_prompt=None)` — sync LLM call (returns str)
- `begin_interaction(event)` — open Raindrop tracing span
- `finish_interaction()` — close span

**Environment:**
```
NVIDIA_API_KEY       = NVIDIA NIM API key
NVIDIA_PARSER_MODEL  = qwen/qwen2.5-7b-instruct (default)
RAINDROP_LOCAL_DEBUGGER = http://localhost:5899 (optional, enables tracing)
```

#### `services/pdf.py`

PDF extraction using Docling (ML-based) + pypdf (legacy fallback).

**Key Functions:**
- `extract_pdf_text(file_bytes)` → str
- `get_pdf_page_count(file_bytes)` → int

---

### 3. **Matching Pipeline** (`matching_pipeline_v2/`)

The core **deterministic orchestrator** — NO LLM brain, NO ReAct. Instead, it:

1. Calls **Scoring Agent** → N×M score matrix (employee × job)
2. Runs **Hungarian Algorithm** (scipy) → optimal 1:1 assignment
3. Calls **Validation Agent** → human-in-loop accept/reject
4. If rejected: calls **Coefficient Tuner Agent** → boost gap-skill weights
5. Repeats (max 3 iterations)
6. Calls **Explanation Agent** → hiring recommendations

#### `matching_pipeline_v2/orchestrator.py`

Main entry point: `async def run_pipeline(employees, jobs, projects, ...) → dict`

**Returns:**
```json
{
  "assignments": [
    {
      "employee_id": "alice@company.com",
      "job_id": "JOB-123",
      "project_id": "PROJECT-ABC",
      "adequacy_score": 0.92,
      "explanation": "Excellent fit for Backend role..."
    }
  ],
  "metadata": {
    "total_iterations": 2,
    "total_duration_s": 45.3,
    "pipeline_version": "v2"
  }
}
```

#### `matching_pipeline_v2/scoring_agent/`

A2A agent that scores each employee against each job.

**Scoring formula** (see `docs/scoring_formula.md`):
- Core skills match (65%)
- Nice-to-have skills (15%)
- Gap skills penalty (15%)
- Seniority alignment (5%)

#### `matching_pipeline_v2/validation_agent/`

A2A agent that reviews the current assignment and decides:
- `"accept"` → finalize
- `"modify"` → send feedback to tuner
- `"reject"` → mark iteration as failed

#### `matching_pipeline_v2/coeff_tuner_agent/`

A2A agent that boosts gap-skill match weights based on validator feedback.

#### `matching_pipeline_v2/explanation_agent/`

A2A agent that writes human-readable explanations for each assignment.

#### `matching_pipeline_v2/knowledge_graph.py`

Neo4j client that queries the **Tech Knowledge Graph**:
- `get_transferable_techs(tech)` — which techs transfer to this one?
- `get_similarity_score(tech_a, tech_b)` → float 0..1

#### `matching_pipeline_v2/search_service.py`

Semantic search using OpenAI embeddings:
- `embed_text(text)` → list[float]
- `search_projects_by_query(text, top_k)` → Project[]
- `search_employees_by_query(text, top_k)` → Employee[]

---

### 4. **Profile Update** (`profile_update/`)

Real-time sync with JIRA to enrich employee project data.

#### `profile_update/jira_sync.py`

Fetch JIRA tasks for a given employee:
- `fetch_jira_tasks(employee_email)` → list[JiraTask]
- Extracts: title, description, story points, tech tags, difficulty

#### `profile_update/orchestrator.py`

Main entry point: `async def sync_all_employees() → dict`

Syncs all employees in MongoDB with JIRA, updates their tasks/projects in real-time.

---

### 5. **CV Parsing** (`cv_generation/` + profile intake)

#### CV Extraction Flow

```
POST /cv (PDF binary)
  ↓
services/pdf.py::extract_pdf_text()  (Docling or pypdf)
  ↓
services/llm.py::ask_llm()  (parse text → JSON)
  ↓
validate JSON structure
  ↓
db/operations.py::add_employee()  (upsert in MongoDB)
  ↓
200 OK { email, name, skills, projects, education }
```

#### `cv_generation/cv_generation.py`

Generate DOCX CV from stored profile data.

**Key function:**
- `generate_cv_docx(employee_id) → bytes` — returns .docx file

---

### 6. **Project Intake** (`po_parser/`)

Parse project documents (e.g., specifications, requirements).

#### `po_parser/project_parser.py`

Main parser:
- `parse_project_document(text) → ProjectData` — extract name, client, reqs, tech stack, jobs

#### `po_parser/ingest_project.py`

Pipeline:
```
POST /po (PDF)
  ↓
extract_pdf_text()
  ↓
parse_project_document()
  ↓
db/operations.py::add_project()
  ↓
200 OK { project_id, name, jobs[] }
```

---

### 7. **Security** (`security/`)

All incoming data is validated and sanitized **before** business logic.

#### `security/validators.py`

- `validate_pdf(file_bytes)` — max size, page count, MIME type
- `validate_email_format(email)` → bool
- `validate_password(pwd)` → (is_valid, reason)

#### `security/sanitizers.py`

- `sanitize_string(text)` → str (remove/escape dangerous chars)
- `sanitize_object_id(oid_str)` → str (reject invalid MongoDB ObjectId)

#### `security/auth.py`

JWT-based authentication:
- `create_access_token(data)` → str
- `decode_token(token)` → dict (payload)
- `hash_password(pwd)` → str
- `verify_password(pwd, hash)` → bool

#### `security/middleware.py`

- `get_current_user(token)` → User (FastAPI dependency)
- CORS configuration
- Request logging

#### `security/turnstile.py`

Cloudflare Turnstile verification:
- `verify_turnstile_token(token)` → (is_valid, error_reason)

---

### 8. **Configuration** (`matching_pipeline_v2/config.py`)

Central config for the matching pipeline:

```python
# Scoring weights
CORE_SKILLS_WEIGHT = 0.65
NICE_TO_HAVE_WEIGHT = 0.15
GAP_SKILLS_WEIGHT = 0.15
SENIORITY_WEIGHT = 0.05

# Hungarian algorithm
MIN_MATCH_SCORE = 0.5  # Skip assignments below this

# Iteration limits
MAX_ITERATIONS = 3
TIMEOUT_PER_AGENT_CALL_S = 300  # 5 minutes
```

---

## REST API Reference

See [API_REFERENCE.md](API_REFERENCE.md) for detailed endpoint docs.

### Top-Level Routes

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/auth/login` | POST | User login |
| `/auth/logout` | POST | User logout |
| `/auth/refresh` | POST | Refresh JWT token |
| `/cv/upload` | POST | Upload & parse CV |
| `/po/upload` | POST | Upload & parse project doc |
| `/matching/run` | POST | Execute full matching pipeline |
| `/matching/status/{run_id}` | GET | Check pipeline status |
| `/assignments/list` | GET | List all assignments |
| `/assignments/{id}` | PATCH | Update assignment (accept/reject) |
| `/admin/users` | GET | List all users |
| `/admin/users` | POST | Create user |
| `/admin/employees` | GET | List all employees |
| `/admin/projects` | GET | List all projects |

---

## Running the Backend

### Prerequisites

```bash
# Backend
python 3.10+
pip install -r requirements.txt

# Services
MongoDB (local or Atlas)
Neo4j (local or AuraDB)
NVIDIA NIM API key (for LLM)
```

### Start the Server

```bash
# Option 1: via start.py (recommended)
python start.py
# Runs on http://localhost:8000

# Option 2: direct uvicorn
uvicorn main:app --reload --port 8000
```

### Environment Variables

```bash
# MongoDB
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority

# Neo4j Knowledge Graph
NEO4J_URI=neo4j+s://aura.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=...

# LLM & Parsing
NVIDIA_API_KEY=nvapi-...
NVIDIA_PARSER_MODEL=qwen/qwen2.5-7b-instruct

# Raindrop Workshop (optional — local tracing)
RAINDROP_LOCAL_DEBUGGER=http://localhost:5899

# Security
JWT_SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# JIRA (for profile sync)
JIRA_URL=https://jira.company.com
JIRA_USERNAME=...
JIRA_API_TOKEN=...

# Cloudflare Turnstile
TURNSTILE_SECRET_KEY=...
```

---

## Testing

Run the test suite:

```bash
pytest tests/ -v

# Specific test
pytest tests/test_orchestrator.py -v

# With coverage
pytest tests/ --cov=matching_pipeline_v2 --cov-report=html
```

**Test files:**
- `test_full_pipeline.py` — end-to-end matching
- `test_knowledge_graph.py` — KG queries
- `test_orchestrator.py` — scoring + validation loop
- `test_scoring_agent.py` — score matrix generation
- `test_validation_agent.py` — validation logic
- `test_search_service.py` — semantic search
- `test_project_parser.py` — PO parsing

---

## Troubleshooting

### LLM Call Hangs

**Symptom:** Scoring agent takes >5 minutes

**Fix:**
1. Check NVIDIA API key in `.env`
2. Verify network connectivity to `integrate.api.nvidia.com`
3. Increase `TIMEOUT_PER_AGENT_CALL_S` in config.py

### MongoDB Connection Fails

**Symptom:** `ConnectionFailure` on startup

**Fix:**
1. Verify `MONGO_URL` in `.env`
2. Check IP whitelist in MongoDB Atlas
3. Ensure network access to cluster

### Neo4j Knowledge Graph Empty

**Symptom:** `"No matching relationships found"`

**Fix:**
1. Log into Neo4j Browser
2. Run the import: `:source tech_knowledge_graph.cypher`
3. Verify: `MATCH (n:Technology) RETURN count(n)` should return 248

### PDF Extraction Fails

**Symptom:** `"Failed to parse PDF"`

**Fix:**
1. Ensure PDF is not encrypted
2. Ensure PDF is not corrupted (try `pdfinfo` tool)
3. Check file size < 50 MB
4. Try with a different PDF

---

## Performance Tips

1. **Batch CV uploads** — use background tasks for large volumes
2. **Cache KG queries** — the tech knowledge graph is immutable; cache results for 1 hour
3. **Index MongoDB** — create indexes on `employee.email`, `job.project_id`
4. **Limit matching runs** — pipeline takes 30–60s; throttle to 1 run per minute
5. **Monitor Raindrop traces** — identify bottleneck agents (usually explanation)

---

## Contributing

### Adding a New Endpoint

1. Create route handler in `main.py` or dedicated router
2. Add Pydantic model for request/response
3. Add security checks (JWT, turnstile, sanitization)
4. Write tests in `tests/`
5. Document in `API_REFERENCE.md`

### Modifying the Matching Pipeline

1. Edit `matching_pipeline_v2/config.py` for weights
2. Modify agent prompts in `*_agent/a2a.py`
3. Update `orchestrator.py` for new steps
4. Write test in `tests/test_orchestrator.py`
5. Run `pytest tests/ -v` to verify

### Adding Neo4j Relationships

1. Edit `tech_knowledge_graph.cypher`
2. Import in Neo4j Browser: `:source tech_knowledge_graph.cypher`
3. Test relationship queries in `knowledge_graph.py`
4. Update `search_service.py` if needed

---

## Support

For issues, questions, or improvements:
- Create an issue in the GitHub repo
- Check existing test cases for usage examples
- Review inline code comments (esp. in `matching_pipeline_v2/`)
- Enable Raindrop tracing for visual debugging of pipeline runs
