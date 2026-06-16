"""
matching_pipeline_v2/models.py
================================
Shared Pydantic data models for the entire matching pipeline.

Every agent and the orchestrator import from here — no data-model
duplication across files.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Employee & Job input models
# ---------------------------------------------------------------------------

class SkillRecord(BaseModel):
    """
    Rich skill entry with scoring metadata.

    All three fields (last_used, duration_months, complexity) are optional so
    that plain-string skills from the database can be normalised into this
    model with safe defaults.
    """
    name: str
    last_used: Optional[datetime] = None       # None → recency score = 0
    duration_months: int = Field(default=0, ge=0)
    complexity: int = Field(default=1, ge=1, le=3)   # 1=basic, 2=mid, 3=expert


class Employee(BaseModel):
    """
    Available employee.  `skills` accepts both plain strings and rich
    SkillRecord objects so that older database documents work unchanged.
    """
    email: str
    name: str
    skills: list[SkillRecord | str]
    # Personal skill adjacency list (merged with the global KG at scoring time)
    knowledge_graph: dict[str, list[str]] = Field(default_factory=dict)

    def normalised_skills(self) -> list[SkillRecord]:
        """Return all skills as SkillRecord objects (strings get safe defaults)."""
        return [
            s if isinstance(s, SkillRecord) else SkillRecord(name=s)
            for s in self.skills
        ]


class Job(BaseModel):
    """Open job slot to be filled."""
    job_id: str
    title: str
    required_skills: list[str]


# ---------------------------------------------------------------------------
# Pipeline input
# ---------------------------------------------------------------------------

class PipelineRequest(BaseModel):
    """
    Full payload passed to run_pipeline().

    `global_knowledge_graph` is a shared tech ontology (e.g. "Python" → ["Data Analysis",
    "Machine Learning"]).  `weights` is seeded to 1.0 for every skill and
    updated each iteration by the CoeffTuner agent.
    """
    employees: list[Employee]
    jobs: list[Job]
    global_knowledge_graph: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Shared ontology: skill → [semantically related skills]",
    )
    weights: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="job_id → {skill → coefficient}.  Auto-initialised to 1.0.",
    )


# ---------------------------------------------------------------------------
# Scoring outputs
# ---------------------------------------------------------------------------

class SkillScore(BaseModel):
    """Decomposed score for one (employee, skill) pair."""
    raw_score: float
    recency_component: float
    duration_component: float
    complexity_component: float


class ScoreDetail(BaseModel):
    """Per (employee, job) breakdown stored by the orchestrator after scoring."""
    employee_email: str
    job_id: str
    score: float
    matched_skills: list[str]    # required skills the employee directly has
    inferred_skills: list[str]   # required skills covered via KG hops
    missing_skills: list[str]    # required skills not covered at all


# ---------------------------------------------------------------------------
# Assignment (Hungarian output)
# ---------------------------------------------------------------------------

class Assignment(BaseModel):
    """One optimal employee → job mapping produced by the Hungarian algorithm."""
    employee_email: str
    employee_name: str
    job_id: str
    job_title: str
    score: float
    matched_skills: list[str]
    inferred_skills: list[str]
    missing_skills: list[str]


# ---------------------------------------------------------------------------
# Validation outputs
# ---------------------------------------------------------------------------

class XAIJobReport(BaseModel):
    """XAI breakdown for a single job's assignment."""
    job_id: str
    job_title: str
    coverage_ratio: float             # fraction of required skills covered
    matched_skills: list[str]
    inferred_skills: list[str]
    missing_skills: list[str]
    semantic_gaps: list[str]          # skills close in KG but still absent
    quality_score: float


class ValidationReport(BaseModel):
    """Full result returned by the Validation Agent."""
    decision: str                     # "finalize" | "adjust"
    avg_score: float
    min_score: float
    collective_gaps: dict[str, list[str]]   # job_id → [skills every employee lacks]
    xai_reports: list[XAIJobReport]
    reasoning: str
    # Populated only when decision == "adjust"; passed verbatim to CoeffTuner
    adjustment_report: Optional[dict] = None


# ---------------------------------------------------------------------------
# Coefficient-tuner outputs
# ---------------------------------------------------------------------------

class TuningChange(BaseModel):
    """What changed for one job during a tuning step."""
    boosted_skills: list[str]
    gap_priorities: dict[str, float]   # skill → priority score
    old_weights: dict[str, float]
    new_weights: dict[str, float]


class TuningResult(BaseModel):
    """Full result returned by the CoeffTuner Agent."""
    weights: dict[str, dict[str, float]]
    changes: dict[str, TuningChange]   # job_id → change record


# ---------------------------------------------------------------------------
# Explanation outputs
# ---------------------------------------------------------------------------

class ExplanationEntry(BaseModel):
    """
    Final hire recommendation for one assignment.

    recommendation levels:
      strong_hire  — score ≥ 0.80 and ≤ 1 missing skill
      hire         — score ≥ 0.60
      consider     — score ≥ 0.40
      pass         — score < 0.40
    """
    employee_email: str
    employee_name: str
    job_id: str
    job_title: str
    score: float
    recommendation: str
    key_strengths: list[str]
    concrete_examples: list[str]
    gaps_to_address: list[str]
    summary: str


# ---------------------------------------------------------------------------
# Final pipeline result
# ---------------------------------------------------------------------------

class PipelineResult(BaseModel):
    """Returned by the orchestrator after the pipeline completes."""
    assignments: list[Assignment]
    explanations: list[ExplanationEntry]
    iterations: int
    final_avg_score: float
