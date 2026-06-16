"""
matching_pipeline_v2
======================
Multi-agent job-matching pipeline.

Architecture
------------
Four specialised ReAct agents communicate over A2A (Agent-to-Agent protocol).
The LangGraph ReAct orchestrator coordinates them via a scored-assignment loop.

Agents
------
  ScoringAgent     (port 8101) — skill-match score matrix
      tools: score_employee_skills, expand_employee_knowledge_graph,
             expand_job_requirements, compute_score_matrix

  ValidationAgent  (port 8102) — XAI-based assignment quality assessment
      tools: analyze_assignment_quality, trace_skill_inference_path,
             structure_adjustment_report

  CoeffTunerAgent  (port 8103) — gap-priority ranking + coverage-elasticity
      tools: rank_gap_priorities, apply_coverage_elasticity

  ExplanationAgent (port 8104) — evidence-backed hire recommendations
      tools: find_relevant_work_examples, assess_hire_recommendation,
             compile_explanation

Pipeline loop (orchestrator)
-----------------------------
  call_scorer → run_hungarian → call_validator
    ├─ FINALIZE → call_explanation → summary
    └─ ADJUST (max 3×) → call_coeff_tuner → call_scorer → …

Entry point
-----------
  python -m matching_pipeline_v2.run <project_id>

Programmatic entry
------------------
  from matching_pipeline_v2.orchestrator import run_pipeline
  summary = run_pipeline(employees, jobs, global_knowledge_graph)
"""
from matching_pipeline_v2.orchestrator import run_pipeline

__all__ = ["run_pipeline"]
