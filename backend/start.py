"""
start.py
=========
SmartStaff backend startup script.

What this does
--------------
1. Validates the Python version (3.11+ required).
2. Loads .env and checks every required environment variable.
3. Verifies that all key packages are installed.
4. Tests the MongoDB connection (hard requirement — exits on failure).
5. Tests the Neo4j connection (soft requirement — warns but continues).
6. Checks that A2A agent ports 8101-8104 are free (agents start inside the app).
7. Starts the FastAPI application via uvicorn.
   The app startup event then starts the four A2A agents and warms the KG cache.

Usage
-----
    python start.py                  # default: 0.0.0.0:8000, reload=on
    python start.py --port 9000
    python start.py --host 127.0.0.1 --port 8080 --no-reload
    python start.py --workers 4      # production (disables reload automatically)
    python start.py --check-only     # run all checks then exit without starting

Environment variables (set in .env or shell)
--------------------------------------------
Required
    MONGODB_URL         MongoDB connection string
    JWT_SECRET          Long random string for JWT signing

Highly recommended
    GROQ_API_KEY        Groq API key (matching pipeline ReAct agents)
    NVIDIA_API_KEY      NVIDIA NIM API key (PDF / CV parsing)
    NEO4J_URI           Neo4j bolt URI          (default bolt://localhost:7687)
    NEO4J_USER          Neo4j username          (default neo4j)
    NEO4J_PASSWORD      Neo4j password

Optional
    DB_NAME             MongoDB database name   (default Profile)
    HOST                Uvicorn bind host       (default 0.0.0.0)
    PORT                Uvicorn bind port       (default 8000)
    RELOAD              Hot-reload on change    (default true)
    WORKERS             Uvicorn worker count    (default 1)
    CF_TURNSTILE_SECRET Cloudflare Turnstile secret (bot protection)
    JIRA_BASE_URL       Jira instance URL       (needed for /api/v1/jira/sync)
    JIRA_EMAIL          Jira account email
    JIRA_API_TOKEN      Jira API token
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Console output helpers ───────────────────────────────────────────────────
# Use ASCII-safe symbols so the script works on Windows cp1252 consoles.

def _c(text: str, code: str) -> str:
    """Apply an ANSI colour code when the terminal supports it."""
    no_colour = os.name == "nt" and not os.environ.get("TERM")
    return text if no_colour else f"\033[{code}m{text}\033[0m"

def _ok(msg: str)   -> None: print(f"  [OK]  {msg}")
def _warn(msg: str) -> None: print(f"  [!!]  {msg}")
def _fail(msg: str) -> None: print(f"  [XX]  {msg}")
def _info(msg: str) -> None: print(f"  [--]  {msg}")

ROOT = Path(__file__).parent


# ─────────────────────────────────────────────────────────────────────────────
# 1. Python version
# ─────────────────────────────────────────────────────────────────────────────

def check_python() -> bool:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 11):
        _fail(f"Python 3.11+ required. Current: {major}.{minor}")
        return False
    _ok(f"Python {major}.{minor}.{sys.version_info.micro}")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# 2. .env + environment variables
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_VARS = [
    ("MONGODB_URL",   "MongoDB connection string"),
    ("JWT_SECRET",    "JWT signing secret (long random string)"),
]

RECOMMENDED_VARS = [
    ("NVIDIA_API_KEY",  "NVIDIA NIM API key (all LLM calls)"),
    ("NEO4J_URI",       "Neo4j bolt URI"),
    ("NEO4J_USER",      "Neo4j username"),
    ("NEO4J_PASSWORD",  "Neo4j password"),
]


def load_env() -> bool:
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=False)
            _ok(f".env loaded from {env_path}")
        except ImportError:
            _warn(".env file found but python-dotenv not installed — variables not loaded")
    else:
        _warn(".env file not found — relying on shell environment variables")
    return True


def check_env_vars() -> bool:
    ok = True
    for var, desc in REQUIRED_VARS:
        val = os.getenv(var, "")
        if val:
            masked = val[:6] + "…" if len(val) > 6 else "***"
            _ok(f"{var} = {masked}  ({desc})")
        else:
            _fail(f"{var} is not set  ({desc})")
            ok = False

    for var, desc in RECOMMENDED_VARS:
        val = os.getenv(var, "")
        if val:
            masked = val[:6] + "…" if len(val) > 6 else "***"
            _ok(f"{var} = {masked}  ({desc})")
        else:
            _warn(f"{var} not set  — {desc}")

    return ok


# ─────────────────────────────────────────────────────────────────────────────
# 3. MongoDB connectivity
# ─────────────────────────────────────────────────────────────────────────────

def check_mongodb() -> bool:
    url = os.getenv("MONGODB_URL", "")
    if not url:
        _fail("MONGODB_URL not set — cannot test MongoDB connection")
        return False
    try:
        import pymongo
        client = pymongo.MongoClient(url, serverSelectionTimeoutMS=5000)
        info   = client.server_info()
        client.close()
        _ok(f"MongoDB reachable  (version {info.get('version', '?')})")
        return True
    except ImportError:
        _warn("pymongo not installed — skipping MongoDB check")
        return True
    except Exception as exc:
        _fail(f"MongoDB unreachable: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# 4. Neo4j connectivity (soft — pipeline degrades gracefully if absent)
# ─────────────────────────────────────────────────────────────────────────────

def check_neo4j() -> bool:
    uri      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
    user     = os.getenv("NEO4J_USER",     "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
        driver.close()
        _ok(f"Neo4j reachable  ({uri})")
        return True
    except ImportError:
        _warn("neo4j package not installed — skipping Neo4j check")
        return True
    except Exception as exc:
        _warn(f"Neo4j unreachable ({uri}): {exc}")
        _warn("Matching pipeline will run without the knowledge graph.")
        return True   # non-fatal — pipeline degrades gracefully


# ─────────────────────────────────────────────────────────────────────────────
# 5. Package availability
# ─────────────────────────────────────────────────────────────────────────────

REQUIRED_PACKAGES = [
    ("fastapi",        "fastapi"),
    ("uvicorn",        "uvicorn"),
    ("beanie",         "beanie"),
    ("pymongo",        "pymongo"),
    ("jwt",            "PyJWT"),
    ("bcrypt",         "bcrypt"),
    ("httpx",          "httpx"),
    ("pydantic",       "pydantic"),
    ("docling",        "docling"),
    ("pdfplumber",     "pdfplumber"),
    ("langchain_core", "langchain-core"),
    ("langgraph",      "langgraph"),
    ("python_a2a",     "python-a2a"),
    ("scipy",          "scipy"),
    ("numpy",          "numpy"),
]


def check_packages() -> bool:
    ok = True
    for import_name, pip_name in REQUIRED_PACKAGES:
        try:
            __import__(import_name)
            _ok(f"{pip_name}")
        except ImportError:
            _fail(f"{pip_name} not installed  →  pip install {pip_name}")
            ok = False
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# 6. A2A agent port availability
# ─────────────────────────────────────────────────────────────────────────────

# Ports used by the four matching-pipeline A2A agents.
# These agents run as daemon threads inside the FastAPI process — they must not
# be bound by another process when the app starts.
A2A_PORTS = {
    8101: "Scoring Agent",
    8102: "Validation Agent",
    8103: "CoeffTuner Agent",
    8104: "Explanation Agent",
}


def check_a2a_ports() -> bool:
    """Verify that all four A2A agent ports are free before starting the app."""
    import socket
    ok = True
    for port, name in A2A_PORTS.items():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", port))
        if result == 0:
            # Port is already bound — something is using it
            _fail(
                f"Port {port} is already in use  "
                f"({name}).  Kill the process holding it and retry."
            )
            ok = False
        else:
            _ok(f"Port {port} free  ({name})")
    return ok


# ─────────────────────────────────────────────────────────────────────────────
# 7. Uvicorn launcher
# ─────────────────────────────────────────────────────────────────────────────

def start_server(host: str, port: int, reload: bool, workers: int) -> None:
    import uvicorn

    print()
    print(_c("-" * 60, "36"))
    print(_c(f"  SmartStaff API  ->  http://{host}:{port}", "1"))
    print(_c(f"  Docs            ->  http://{host}:{port}/docs", "36"))
    if reload:
        print(_c("  Mode: development  (hot-reload enabled)", "33"))
    else:
        print(_c(f"  Mode: production   (workers={workers})", "32"))
    print(_c("-" * 60, "36"))
    print()

    # reload and workers are mutually exclusive in uvicorn
    if reload:
        uvicorn.run(
            "main:app",
            host      = host,
            port      = port,
            reload    = True,
            log_level = "info",
        )
    else:
        uvicorn.run(
            "main:app",
            host      = host,
            port      = port,
            workers   = workers,
            log_level = "info",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SmartStaff backend — pre-flight checks + uvicorn launcher",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host",       default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port",       type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--no-reload",  action="store_true", help="Disable hot-reload (use for production)")
    parser.add_argument("--workers",    type=int, default=int(os.getenv("WORKERS", "1")), help="Uvicorn worker count (only when --no-reload)")
    parser.add_argument("--check-only", action="store_true", help="Run checks then exit without starting the server")
    args = parser.parse_args()

    # Change to backend root so relative imports resolve correctly
    os.chdir(ROOT)

    print()
    print(_c("=" * 52, "36"))
    print(_c("       SmartStaff Backend  --  Pre-flight", "1"))
    print(_c("=" * 52, "36"))
    print()

    checks: list[tuple[str, bool]] = []

    print(_c("[ Python ]", "1"))
    checks.append(("Python 3.11+", check_python()))

    print()
    print(_c("[ Environment ]", "1"))
    load_env()
    checks.append(("Required env vars", check_env_vars()))

    print()
    print(_c("[ Packages ]", "1"))
    checks.append(("Required packages", check_packages()))

    print()
    print(_c("[ MongoDB ]", "1"))
    checks.append(("MongoDB connection", check_mongodb()))

    print()
    print(_c("[ Neo4j ]", "1"))
    check_neo4j()   # soft — warns but does not block startup

    print()
    print(_c("[ A2A Agent Ports ]", "1"))
    _info("Agents start inside the app process on these ports:")
    checks.append(("A2A ports 8101-8104 free", check_a2a_ports()))

    # Summary
    print()
    print(_c("[ Summary ]", "1"))
    all_ok = True
    for name, passed in checks:
        if passed:
            _ok(name)
        else:
            _fail(name)
            all_ok = False

    if not all_ok:
        print()
        print(_c("  Pre-flight failed. Fix the errors above before starting.", "31"))
        sys.exit(1)

    if args.check_only:
        print()
        _ok("All checks passed. Exiting (--check-only).")
        sys.exit(0)

    reload = not args.no_reload
    if args.workers > 1:
        reload = False   # uvicorn does not support reload + multiple workers

    start_server(
        host    = args.host,
        port    = args.port,
        reload  = reload,
        workers = args.workers,
    )


if __name__ == "__main__":
    main()
