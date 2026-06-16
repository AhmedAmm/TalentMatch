"""
matching_pipeline_v2/run.py
=============================
CLI entry point for the matching pipeline.

What this does
--------------
1. Starts four A2A agent servers in background daemon threads:
     Scoring Agent     → http://localhost:8101
     Validation Agent  → http://localhost:8102
     CoeffTuner Agent  → http://localhost:8103
     Explanation Agent → http://localhost:8104
2. Loads available employees and open jobs via the existing Beanie ORM
   (tools/db.py + tools/models.py) — no raw pymongo queries.
3. Runs the orchestrator (LangGraph ReAct agent).
4. Prints the final summary.

Usage
-----
    python -m matching_pipeline_v2.run <project_id>

Data loading uses:
  • tools.db.get_open_jobs(project_id)   → jobs with remaining > 0
  • tools.models.Employee.find(available=True) → no db.py wrapper exists,
    so we query Beanie directly for available employees
"""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time

import requests

import matching_pipeline_v2.config as cfg
from matching_pipeline_v2.knowledge_graph   import load_kg
from matching_pipeline_v2.scoring_agent     import ScoringAgentServer,     SCORER_PORT
from matching_pipeline_v2.validation_agent  import ValidationAgentServer,  VALIDATOR_PORT
from matching_pipeline_v2.coeff_tuner_agent import CoeffTunerAgentServer,  TUNER_PORT
from matching_pipeline_v2.explanation_agent import ExplanationAgentServer, EXPLANATION_PORT
from matching_pipeline_v2.orchestrator      import run_pipeline

from python_a2a import run_server

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# A2A server startup helpers
# ---------------------------------------------------------------------------

def _start_server(agent, port: int) -> None:
    """Start a single A2A agent server (blocking — runs in a daemon thread)."""
    run_server(agent, host="0.0.0.0", port=port, debug=False)


def _wait_for_server(port: int, timeout: int = 60) -> None:
    """Poll until the server at `port` responds, or raise TimeoutError."""
    url      = f"http://localhost:{port}/a2a"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(url, timeout=2)
            return
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(f"Server on port {port} did not start within {timeout}s.")


def start_all_servers() -> None:
    """Launch all four A2A agent servers as daemon threads, then wait for readiness."""
    servers = [
        (ScoringAgentServer(),     SCORER_PORT),
        (ValidationAgentServer(),  VALIDATOR_PORT),
        (CoeffTunerAgentServer(),  TUNER_PORT),
        (ExplanationAgentServer(), EXPLANATION_PORT),
    ]
    for agent, port in servers:
        t = threading.Thread(target=_start_server, args=(agent, port), daemon=True)
        t.start()
        logger.info("Started %s on port %d", agent.__class__.__name__, port)

    logger.info("Waiting for all A2A servers to be ready…")
    for _, port in servers:
        _wait_for_server(port)
    logger.info("All A2A servers ready.")


# ---------------------------------------------------------------------------
# Data loading — Beanie ORM
# ---------------------------------------------------------------------------

async def _load_employees() -> list[dict]:
    """
    Fetch all available employees via the Beanie Employee document.

    No db.py wrapper exists for this query, so we call the Beanie document
    directly.  Returns plain dicts so the rest of the pipeline stays
    ORM-agnostic.

    Skills are stored as list[str] in the Employee document.  The `projects`
    field carries rich EmployeeProject sub-documents whose `technologies` list
    is used as evidence in the Explanation Agent.
    """
    from db.models import Employee

    docs = await Employee.find(Employee.available == True).to_list()  # noqa: E712

    employees = []
    for doc in docs:
        # Build a personal KG from each EmployeeProject's technologies list:
        # if two skills co-appear in the same project, they share an edge
        # (weight 1.0 — employee-declared relationship).
        personal_kg: dict[str, list[str]] = {}
        for project in (doc.projects or []):
            techs = [t.strip().lower() for t in (project.technologies or []) if t]
            for tech in techs:
                for related in techs:
                    if related != tech:
                        personal_kg.setdefault(tech, [])
                        if related not in personal_kg[tech]:
                            personal_kg[tech].append(related)

        employees.append({
            "email":           doc.id,
            "name":            doc.name,
            "skills":          doc.skills or [],
            "knowledge_graph": personal_kg,
            # Pass full project history for the Explanation Agent to cite
            "projects":        [p.model_dump() for p in (doc.projects or [])],
        })

    return employees


async def _load_jobs(project_id: str) -> list[dict]:
    """
    Fetch open jobs for the project using the existing db.py ORM wrapper.

    get_open_jobs(project_id) returns jobs where remaining > 0, which is the
    correct semantics for matching (no point filling an already-filled slot).
    """
    from db.operations import get_open_jobs

    raw_jobs = await get_open_jobs(project_id)

    return [
        {
            "job_id":          job["job_id"],
            "title":           job.get("title", ""),
            # ORM stores the field as required_stack; rename for the pipeline
            "required_skills": [
                s.strip() for s in job.get("required_stack", []) if s
            ],
        }
        for job in raw_jobs
    ]


def _load_knowledge_graph() -> dict[str, dict[str, float]]:
    """
    Load the weighted tech knowledge graph from Neo4j.

    Returns WeightedKG: { skill_lower: { neighbour_lower: transfer_weight } }
    Falls back to an empty dict if Neo4j is unreachable.
    """
    logger.info("Loading tech knowledge graph from Neo4j…")
    kg = load_kg()
    if not kg:
        logger.warning(
            "Knowledge graph is empty — matching will use direct skills only.  "
            "Check NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env."
        )
    return kg


# ---------------------------------------------------------------------------
# Main (async — required by Beanie ORM)
# ---------------------------------------------------------------------------

async def _async_main(project_id: str) -> None:
    # Initialise Beanie with the Motor async client
    from motor.motor_asyncio import AsyncIOMotorClient

    motor_client = AsyncIOMotorClient(cfg.MONGODB_URL)
    # init_beanie_odm uses the module-level Motor client set by get_motor_client();
    # we pass it directly to Beanie's init instead.
    import beanie
    from db.models import Employee, Job, Project, Assignment, User, CVUploadLog
    await beanie.init_beanie(
        database=motor_client[cfg.DB_NAME],
        document_models=[Employee, Job, Project, Assignment, User, CVUploadLog],
    )

    employees = await _load_employees()
    jobs      = await _load_jobs(project_id)
    motor_client.close()

    if not employees:
        print("No available employees found in the database.")
        sys.exit(1)
    if not jobs:
        print(f"No open jobs found for project '{project_id}'.")
        sys.exit(1)

    logger.info(
        "Loaded %d employee(s) and %d open job(s).",
        len(employees), len(jobs),
    )

    # Load KG (sync — Neo4j driver is synchronous)
    knowledge_graph = _load_knowledge_graph()
    logger.info("KG: %d skill nodes loaded.", len(knowledge_graph))

    # Run the orchestrator (LangGraph ReAct — synchronous)
    print(f"\nStarting matching pipeline for project: {project_id}")
    print("=" * 60)
    summary, assignments = run_pipeline(employees, jobs, knowledge_graph)
    print(f"\n── Pipeline result ({len(assignments)} assignment(s)) ─────────────")
    print(summary)
    print("─────────────────────────────────────────────────────────\n")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python -m matching_pipeline_v2.run <project_id>")
        sys.exit(1)

    project_id = sys.argv[1]

    # Start A2A servers (sync — runs in daemon threads)
    start_all_servers()

    # Run async data loading + pipeline
    asyncio.run(_async_main(project_id))


if __name__ == "__main__":
    main()
