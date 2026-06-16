"""
matching_pipeline_v2/config.py
================================
All environment-variable reads live here.
No other module should call os.getenv directly.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
MONGODB_URL: str = os.environ["MONGODB_URL"]
DB_NAME: str = os.getenv("DB_NAME", "Profile")

# ---------------------------------------------------------------------------
# LLM  (NVIDIA NIM — both ReAct agents and PDF/CV parser)
# ---------------------------------------------------------------------------
NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"

# Kimi K2 for ALL agents — 128K context, supports multiple registered tools,
# sequential tool calling, superior instruction-following vs 8B models.
NVIDIA_AGENT_MODEL: str = os.getenv("NVIDIA_AGENT_MODEL", "moonshotai/kimi-k2-instruct")
NVIDIA_ORCHESTRATOR_MODEL: str = os.getenv("NVIDIA_ORCHESTRATOR_MODEL", "moonshotai/kimi-k2-instruct")
NVIDIA_TEMPERATURE: float = 0.2
NVIDIA_MAX_TOKENS: int = 4096
# Validation agent needs more headroom: it outputs the full xai_report in its
# JSON response (9 assignments × 7 jobs ≈ 5-6 KB), which exceeds 4096 tokens.
NVIDIA_VALIDATOR_MAX_TOKENS: int = int(os.getenv("NVIDIA_VALIDATOR_MAX_TOKENS", "16384"))

# ---------------------------------------------------------------------------
# Neo4j  (tech knowledge graph)
# ---------------------------------------------------------------------------
NEO4J_URI:      str = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER:     str = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
# The KG lives in a named database (old pipeline default: "project").
# The default Neo4j database is "neo4j" — always set this explicitly.
NEO4J_DATABASE: str = os.getenv("NEO4J_DATABASE", "project")

# Edge-type transfer weights applied when the relationship has no explicit
# `weight` property (TRANSFERABLE_TO and EQUIVALENT_IN carry their own).
NEO4J_EDGE_WEIGHTS: dict[str, float] = {
    "TRANSFERABLE_TO":  1.0,   # uses the edge's own weight property
    "EQUIVALENT_IN":    1.0,   # uses the edge's own weight property
    "EXTENDS":          0.85,
    "REQUIRES":         0.90,
    "PART_OF":          0.80,
    "OFTEN_USED_WITH":  0.50,
    "BRIDGES":          0.60,
    "EVOLVED_INTO":     0.70,
    "IMPLEMENTS":       0.80,
}

# ---------------------------------------------------------------------------
# A2A sub-agent ports (overridable via .env)
# ---------------------------------------------------------------------------
SCORER_PORT: int      = int(os.getenv("SCORER_PORT",      "8101"))
VALIDATOR_PORT: int   = int(os.getenv("VALIDATOR_PORT",   "8102"))
TUNER_PORT: int       = int(os.getenv("TUNER_PORT",       "8103"))
EXPLANATION_PORT: int = int(os.getenv("EXPLANATION_PORT", "8104"))

SCORER_URL:      str = f"http://localhost:{SCORER_PORT}"
VALIDATOR_URL:   str = f"http://localhost:{VALIDATOR_PORT}"
TUNER_URL:       str = f"http://localhost:{TUNER_PORT}"
EXPLANATION_URL: str = f"http://localhost:{EXPLANATION_PORT}"

# ---------------------------------------------------------------------------
# LangSmith tracing (all optional — tracing is off when unset)
# Set in .env:
#   LANGCHAIN_TRACING_V2=true
#   LANGCHAIN_API_KEY=ls__<key>
#   LANGCHAIN_PROJECT=matching-pipeline
# ---------------------------------------------------------------------------
LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "matching-pipeline")

os.environ.setdefault("LANGCHAIN_TRACING_V2", LANGCHAIN_TRACING_V2)
os.environ.setdefault("LANGCHAIN_API_KEY",     LANGCHAIN_API_KEY)
os.environ.setdefault("LANGCHAIN_PROJECT",     LANGCHAIN_PROJECT)
