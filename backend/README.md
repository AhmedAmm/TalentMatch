# SmartStaff Backend — Complete Overview

Welcome to the SmartStaff backend repository! This document serves as your entry point for understanding the entire backend architecture, modules, and workflows.

## 📚 Documentation Index

### Getting Started
- **[BACKEND_DOCUMENTATION.md](BACKEND_DOCUMENTATION.md)** — Complete technical guide including:
  - Architecture overview and component diagram
  - Module-by-module reference (database, services, matching pipeline, etc.)
  - Running the backend (prerequisites, startup, env vars)
  - Testing and troubleshooting
  - Performance optimization tips

- **[API_REFERENCE.md](API_REFERENCE.md)** — Detailed REST API documentation:
  - All endpoints with request/response examples
  - Authentication & security
  - Error handling
  - WebSocket real-time updates
  - Rate limiting
  - Complete workflow examples

### Domain Knowledge
- **[DB_shema.md](DB_shema.md)** — MongoDB database schema:
  - Collections: employees, jobs, projects, assignments, users, cv_upload_logs
  - Document structure and field specifications
  - Relationships and data flow

- **[KG_Structre.md](KG_Structre.md)** — Neo4j Knowledge Graph structure:
  - Purpose: model technology transferability for intelligent matching
  - 248 technology nodes across 12 domains
  - 9 relationship types (TRANSFERABLE_TO, REQUIRES, PART_OF, etc.)
  - Node properties and category taxonomy

- **[tech_knowledge_graph.cypher](tech_knowledge_graph.cypher)** — Neo4j import script:
  - Executable Cypher code to build the entire knowledge graph
  - Node definitions with properties
  - Relationship creation with weights
  - Import instructions for Neo4j Browser or CLI

### Scoring & Matching
- **[docs/scoring_formula.md](docs/scoring_formula.md)** — Matching algorithm breakdown:
  - Core skills match (65%)
  - Nice-to-have skills (15%)
  - Gap skills penalty (15%)
  - Seniority alignment (5%)

- **[docs/benchmark.md](docs/benchmark.md)** — Performance benchmarks:
  - Pipeline execution times
  - Scoring agent response times
  - Database query performance
  - Recommendations for optimization

---

## 🏗️ Architecture at a Glance

```
┌─ Frontend (React/Vite) ─────────────────────────┐
│                                                 │
│  Login → Dashboard → Upload → Match → Assign   │
└──────────────────┬──────────────────────────────┘
                   │ REST API + WebSocket
                   ▼
┌─ FastAPI Backend (main.py) ──────────────────────┐
│                                                  │
│  • Security layer (auth, validation, sanitize)  │
│  • REST routers (/cv, /po, /matching, /auth)    │
│  • Services (LLM, PDF, search)                   │
│  • Database ORM (Beanie + PyMongo)               │
│  • Matching orchestrator (scoring → hungarian)   │
│                                                  │
└──────────────────┬───────────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
   MongoDB    Neo4j KG   NVIDIA NIM LLM
```

---

## 🚀 Quick Start

### Prerequisites

```bash
# System
Python 3.10+
MongoDB (local or Atlas)
Neo4j (local or AuraDB)

# API Keys
NVIDIA NIM API key (for LLM-based parsing)
Cloudflare Turnstile key (for security)
JWT secret key
```

### Installation

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env    # Edit with your credentials
python start.py         # Starts uvicorn on :8000
```

### Verify Installation

```bash
# Check API is running
curl http://localhost:8000/docs

# Check database connection
curl -X GET http://localhost:8000/admin/health \
  -H "Authorization: Bearer <your-token>"

# Check knowledge graph
curl -X GET http://localhost:8000/kg/stats \
  -H "Authorization: Bearer <your-token>"
```

---

## 📦 Project Structure

```
backend/
├── main.py                       # FastAPI app entry point
├── start.py                      # Startup script (better than uvicorn directly)
├── requirements.txt              # Python dependencies
├── .env                          # Environment config (create from .env.example)
│
├── DB_shema.md                   # MongoDB schema documentation
├── KG_Structre.md                # Neo4j KG structure documentation
├── tech_knowledge_graph.cypher   # KG import script
│
├── BACKEND_DOCUMENTATION.md      # [YOU ARE HERE] Complete tech guide
├── API_REFERENCE.md              # REST API documentation
│
├── db/                           # Database layer (Beanie ODM)
│   ├── models.py                 # MongoDB document models
│   └── operations.py             # CRUD interface
│
├── matching_pipeline_v2/         # Core matching engine
│   ├── orchestrator.py           # Main orchestrator (scores → hungarian → validation)
│   ├── config.py                 # Pipeline configuration (weights, timeouts)
│   ├── knowledge_graph.py        # Neo4j client
│   ├── search_service.py         # Semantic search (embeddings)
│   ├── llm_factory.py            # LLM client factory
│   │
│   ├── scoring_agent/            # Scoring Agent (A2A)
│   ├── validation_agent/         # Validation Agent (A2A)
│   ├── coeff_tuner_agent/        # Coefficient Tuner Agent (A2A)
│   └── explanation_agent/        # Explanation Agent (A2A)
│
├── services/                     # External service clients
│   ├── llm.py                    # NVIDIA NIM LLM + Raindrop tracing
│   └── pdf.py                    # PDF extraction (Docling + pypdf)
│
├── security/                     # Security & validation
│   ├── auth.py                   # JWT authentication
│   ├── middleware.py             # CORS, logging middleware
│   ├── validators.py             # Input validation (PDF, email, password)
│   ├── sanitizers.py             # Text sanitization & NoSQL injection prevention
│   └── turnstile.py              # Cloudflare Turnstile verification
│
├── po_parser/                    # Project document intake
│   ├── project_parser.py         # Extract name, reqs, tech stack from PO
│   └── ingest_project.py         # Upload → parse → store pipeline
│
├── profile_update/               # Real-time employee enrichment
│   ├── jira_sync.py              # Fetch JIRA tasks
│   └── orchestrator.py           # Sync all employees
│
├── cv_generation/                # CV document generation
│   └── cv_generation.py          # Generate DOCX from profile
│
├── scripts/                      # Utility scripts
│   └── update_kg.py              # Periodic knowledge graph updates
│
├── docs/                         # Additional documentation
│   ├── scoring_formula.md        # Detailed scoring algorithm
│   └── benchmark.md              # Performance metrics
│
├── tests/                        # Test suite
│   ├── conftest.py               # Pytest fixtures
│   ├── test_full_pipeline.py     # End-to-end tests
│   ├── test_orchestrator.py      # Matching pipeline tests
│   ├── test_scoring_agent.py     # Scoring logic tests
│   ├── test_knowledge_graph.py   # KG query tests
│   ├── test_search_service.py    # Semantic search tests
│   ├── test_validation_agent.py  # Validation logic tests
│   └── test_project_parser.py    # PO parsing tests
│
└── tools/                        # Legacy/utility tools (may be deprecated)
```

---

## 🔄 Data Flow Examples

### 1. CV Upload & Profile Creation

```
POST /cv/upload (resume.pdf)
    ↓
validate_pdf_upload()
    ↓
extract_pdf_text()  [Docling]
    ↓
ask_llm("Parse CV text into JSON")
    ↓
add_employee()  [insert into MongoDB]
    ↓
200 OK { email, name, skills, projects, education }
```

### 2. Project Intake

```
POST /po/upload (project_spec.pdf)
    ↓
validate_pdf_upload()
    ↓
extract_pdf_text()  [Docling]
    ↓
parse_project_document()  [LLM + regex extraction]
    ↓
add_project()  [insert into MongoDB]
    ↓
create_jobs()  [one per role]
    ↓
201 Created { project_id, job_ids[] }
```

### 3. Full Matching Pipeline

```
POST /matching/run
  {
    employee_ids: ["alice@...", "bob@..."],
    job_ids: ["JOB-001", "JOB-002"],
    project_id: "PROJECT-001"
  }
    ↓
[Iteration 1]
  → scoring_agent()     [N×M score matrix via A2A LLM]
  → hungarian()         [scipy optimal assignment]
  → validation_agent()  [human review: accept/modify/reject]
    ↓
[If rejected: Iteration 2]
  → coeff_tuner_agent() [boost gap skills weights]
  → scoring_agent()     [re-score with new weights]
  → hungarian()
  → validation_agent()
    ↓
[Final]
  → explanation_agent() [write hiring recommendations]
    ↓
202 Accepted { run_id }
  (poll /matching/status/{run_id} for progress)
    ↓
200 OK { assignments[], metadata }
```

---

## 🔐 Security

Every endpoint is protected by:

1. **Authentication** — JWT token required (except `/auth/login`)
2. **Authorization** — Role-based access control (PO, RH, ADMIN)
3. **Input Validation** — Pydantic models with strict field validators
4. **Sanitization** — HTML/NoSQL injection prevention
5. **Rate Limiting** — 500 req/hr per user, 10 req/min for `/matching/run`
6. **Turnstile** — Cloudflare CAPTCHA for CV/PO uploads

---

## 📊 Knowledge Graph (Neo4j)

The **Tech Knowledge Graph** is the secret sauce behind intelligent matching:

- **248 technology nodes** (Python, React, Kubernetes, etc.)
- **284 relationships** (TRANSFERABLE_TO, REQUIRES, PART_OF, etc.)
- **12 domains**: Frontend, Backend, DevOps, ML, LLM, Cloud, Database, etc.

### Examples

- **React → Vue** (0.85 weight) — strong transferability
- **Kubernetes → Helm** (REQUIRES) — Helm requires K8s knowledge
- **Python → PyTorch** (0.75) — Python developers can quickly learn PyTorch
- **AWS → GCP** (0.65) — cloud concepts transfer, different APIs

The matching algorithm uses these relationships to:
- Score candidates beyond exact keyword matching
- Identify hidden skill gaps
- Boost scores for transferable technologies

---

## 🧪 Testing

Run the full test suite:

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_orchestrator.py -v

# With coverage report
pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html
```

Key test files:
- `test_full_pipeline.py` — End-to-end matching with real data
- `test_orchestrator.py` — Scoring, Hungarian algorithm, validation loop
- `test_scoring_agent.py` — Score matrix generation
- `test_knowledge_graph.py` — KG queries and transferability
- `test_project_parser.py` — PO PDF parsing
- `test_search_service.py` — Semantic embeddings

---

## 🔧 Common Tasks

### Add a New Endpoint

1. **Define Pydantic model** in `main.py`:
```python
class MyRequest(BaseModel):
    field1: str
    @field_validator("field1")
    @classmethod
    def _clean(cls, v):
        return sanitize_string(v, 100)
```

2. **Create route**:
```python
@app.post("/my/endpoint", dependencies=[Depends(_require_po_or_admin)])
async def my_handler(req: MyRequest, current_user: dict = Depends(_get_current_user)) -> dict:
    """
    Brief description of what this endpoint does.
    
    Parameters
    ----------
    req : MyRequest
        The request payload
    current_user : dict
        Authenticated user (from JWT)
    
    Returns
    -------
    dict
        Response data
    """
    # Validate & sanitize
    check_nosql_injection(req.field1)
    
    # Business logic
    result = await _db.my_operation(req.field1)
    
    # Return
    return {"status": "success", "data": result}
```

3. **Add tests** in `tests/test_new_feature.py`
4. **Document** in `API_REFERENCE.md`

### Modify Matching Algorithm

1. Edit weights in `matching_pipeline_v2/config.py`:
```python
CORE_SKILLS_WEIGHT = 0.70  # was 0.65
```

2. Update agent prompts in `*_agent/a2a.py`

3. Run tests: `pytest tests/test_orchestrator.py -v`

4. Benchmark: `pytest tests/ --benchmark`

### Update Knowledge Graph

1. Add/modify relationships in `tech_knowledge_graph.cypher`
2. Import in Neo4j Browser: `:source tech_knowledge_graph.cypher`
3. Test queries in `knowledge_graph.py`
4. Update matching logic if needed

---

## 📈 Performance Tips

1. **Batch operations** — upload 10 CVs together vs one-by-one
2. **Cache KG** — queries are immutable; cache for 1 hour
3. **Limit pipeline runs** — takes 30–60 seconds; throttle to 1/min
4. **Index MongoDB** — on `employee.email`, `job.project_id`, `assignment.employee_id`
5. **Monitor bottlenecks** — enable Raindrop tracing to see which agent is slow

### Typical Performance

| Operation | Time | Notes |
|-----------|------|-------|
| CV upload | 15–30s | Docling extraction + LLM parsing |
| PO intake | 20–40s | PDF extraction + project parsing |
| Matching (3 employees, 2 jobs) | 45–90s | 2 iterations, all agents |
| Knowledge graph lookup | <100ms | Cached in memory |
| Search (semantic) | 200–500ms | Embedding generation + KNN |

---

## 🐛 Debugging

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
python start.py
```

### Watch Pipeline Execution

```bash
export RAINDROP_LOCAL_DEBUGGER=http://localhost:5899
python start.py
# Then open http://localhost:5899 in browser (requires local Raindrop daemon)
```

### Check Database

```bash
# MongoDB
mongosh "mongodb+srv://..." --eval "db.employees.count()"

# Neo4j
cypher-shell -u neo4j -p <pass> "MATCH (n:Technology) RETURN count(n)"
```

### Common Issues

| Symptom | Solution |
|---------|----------|
| "LLM call timeout" | Check NVIDIA API key; increase timeout in config |
| "MongoDB connection failed" | Check MONGO_URL; verify IP whitelist in Atlas |
| "No matching relationships in KG" | Import cypher: `:source tech_knowledge_graph.cypher` |
| "PDF parse fails" | Ensure PDF not encrypted; try with different PDF |
| "Rate limit exceeded" | Wait 60s; reduce request frequency or contact admin |

---

## 📞 Support & Contribution

### Getting Help

1. **Check this README** — most questions are answered here
2. **Review test files** — show usage examples for all features
3. **Read inline comments** — especially in `matching_pipeline_v2/`
4. **Enable debug logging** — see exactly what's happening
5. **Check Raindrop traces** — visualize pipeline execution

### Contributing

1. **Create feature branch**: `git checkout -b feature/my-feature`
2. **Write tests first**: `tests/test_my_feature.py`
3. **Implement feature**: follow existing code style
4. **Run tests**: `pytest tests/ -v`
5. **Update docs**: `BACKEND_DOCUMENTATION.md` + `API_REFERENCE.md`
6. **Submit PR**: with test coverage and documentation

---

## 📋 Environment Variables

Create a `.env` file in the `backend/` directory:

```bash
# Database
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/?retryWrites=true&w=majority
NEO4J_URI=neo4j+s://aura.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password

# LLM & Services
NVIDIA_API_KEY=nvapi-xxxxxxxxx
NVIDIA_PARSER_MODEL=qwen/qwen2.5-7b-instruct
RAINDROP_LOCAL_DEBUGGER=http://localhost:5899  # Optional

# Security
JWT_SECRET_KEY=your-secret-key-change-this
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# JIRA Integration (for profile sync)
JIRA_URL=https://jira.company.com
JIRA_USERNAME=your_username
JIRA_API_TOKEN=your_token

# Cloudflare Turnstile
TURNSTILE_SECRET_KEY=your_turnstile_key

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Logging
LOG_LEVEL=INFO
```

---

## 📝 License

See [LICENSE](LICENSE) file.

---

**Last Updated:** 2026-06-16  
**Version:** 2.0.0  
**Maintained By:** SmartStaff Team
