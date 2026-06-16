# Backend Fix Prompt for nw_main2.py

## Context
You are working on `nw_main2.py`, a FastAPI backend for SmartStaff. There are two critical bugs to fix.

## Bug 1: Reject creates duplicate assignment with 0% score and "Manually assigned via UI"

### Root Cause
When `PATCH /api/v1/matches/{match_id}/status` is called with `{"status": "REJECTED"}`, the handler at line ~851 correctly:
1. Rejects the assignment
2. Looks for the next pending assignment in the DB for the same job
3. Returns it as `suggestion` with real score

**BUT**: The frontend then calls `POST /api/v1/projects/{pid}/jobs/{jid}/assign` (the `manual_assign_candidate` endpoint) to "assign" the suggestion. This creates a **duplicate** assignment because the suggested employee already has a pending assignment in the DB. The new duplicate has:
- `notes="Manually assigned via UI"` (wrong label)
- `adequacy_score=0` because `SearchService.search_employees_for_job()` runs AFTER `_db.create_assignment()`, and the employee is now already assigned so SearchService excludes them from results

### Fix Required
In the `manual_assign_candidate` endpoint (line ~1211), **compute the score BEFORE creating the assignment**, and **check if an assignment already exists for this employee+job+project** to avoid duplicates:

```python
@app.post("/api/v1/projects/{project_id}/jobs/{job_id}/assign", tags=["Matches"], status_code=201)
async def manual_assign_candidate(
    project_id: str, job_id: str, body: ManualAssignRequest,
    current_user: dict = Depends(_require_po_or_admin),
):
    project_id = sanitize_string(project_id, 100)
    job_id     = sanitize_string(job_id, 100)
    emp_id     = sanitize_string(body.employee_id, 254)
    check_nosql_injection({"employee_id": emp_id})
    
    try:
        # ── 1. Compute score BEFORE creating assignment ──────────────────
        actual_score   = 0.0
        matched_skills = []
        missing_skills = []
        try:
            search_svc = SearchService()
            scored = search_svc.search_employees_for_job(job_id, project_id, limit=200)
            emp_score_data = next((r for r in scored if r["employee_id"] == emp_id), None)
            if emp_score_data:
                actual_score   = emp_score_data["matching_score"]
                matched_skills = emp_score_data.get("matched_skills", [])
                missing_skills = emp_score_data.get("missing_skills", [])
        except Exception:
            pass

        # ── 2. Handle replace (if swapping out an old match) ─────────────
        if body.replace_match_id:
            old_id = sanitize_string(body.replace_match_id, 100)
            old = _db.get_assignment(old_id)
            if old:
                try:
                    if old["status"] == "accepted":
                        _db.unassign_employee(old_id, reason="Replaced")
                    else:
                        _db.reject_assignment(old_id, reason="Replaced")
                except Exception:
                    pass

        # ── 3. Check for existing pending assignment (avoid duplicates) ──
        existing = _db.assignments.find_one({
            "employee_id": emp_id,
            "project_id":  project_id,
            "job_id":      job_id,
            "status":      "pending",
        })
        
        if existing:
            # Just update the existing assignment's score + explanation
            existing["_id"] = str(existing["_id"])
            explanation = ""
            try:
                explanation = explain_assignment(
                    job_id, emp_id, project_id, actual_score,
                    matched_skills, missing_skills,
                )
            except Exception:
                explanation = f"Match score: {round(actual_score * 100)}/100."
            
            _db.assignments.update_one(
                {"_id": existing["_id"]},
                {"$set": {"explanation": explanation, "adequacy_score": actual_score}}
            )
            result = _assignment_to_match(existing)
            result["explanation"]      = explanation
            result["scorePercentage"]  = round(actual_score * 100)
            result["score_percentage"] = round(actual_score * 100)
            result["matched_skills"]   = matched_skills
            result["missing_skills"]   = missing_skills
            return result
        
        # ── 4. Create new assignment with pre-computed score ─────────────
        new_asgn = _db.create_assignment(
            employee_id=emp_id, project_id=project_id, job_id=job_id,
            assigned_by=current_user.get("sub", "system"),
            notes="",
        )
        
        explanation = ""
        try:
            explanation = explain_assignment(
                job_id, emp_id, project_id, actual_score,
                matched_skills, missing_skills,
            )
        except Exception:
            explanation = f"Match score: {round(actual_score * 100)}/100."

        _db.assignments.update_one(
            {"_id": new_asgn["_id"]},
            {"$set": {"explanation": explanation, "adequacy_score": actual_score}}
        )
        
        result = _assignment_to_match(_serialize(new_asgn))
        result["explanation"]      = explanation
        result["scorePercentage"]  = round(actual_score * 100)
        result["score_percentage"] = round(actual_score * 100)
        result["matched_skills"]   = matched_skills
        result["missing_skills"]   = missing_skills
        return result
        
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Manual assign failed")
        raise HTTPException(status_code=500, detail=str(exc))
```

## Bug 2: System suggests employees already assigned to the same project

### Root Cause
There are THREE places where candidate suggestions are generated, and the exclusion logic is inconsistent:

1. **`update_match_status` REJECTED handler** (line ~862): Queries `_db.assignments.find({"job_id": job_id, "project_id": project_id, "status": "pending"})` — this returns employees already assigned to THIS job. Fine for same-job suggestions, but doesn't check if they're assigned to OTHER jobs in the same project.

2. **SearchService fallback in reject handler** (line ~884-888): Excludes employees from the assignments collection for this project — but only by `project_id`, not filtering by status. This means it excludes even rejected employees, but misses employees who were assigned via a different mechanism.

3. **`search_job_candidates` endpoint** (line ~1178): Calls `SearchService.search_employees_for_job()` which may not filter by project-level assignment at all.

### Fix Required
In ALL three places, build a comprehensive exclusion set that includes every employee who has a `pending` or `accepted` assignment on ANY job within this project:

```python
# Utility function — add near the helpers section:
def _get_project_assigned_employees(project_id: str, exclude_statuses: set = None) -> set:
    """Get all employee IDs with pending or accepted assignments in this project."""
    query = {"project_id": project_id}
    if exclude_statuses:
        query["status"] = {"$nin": list(exclude_statuses)}
    else:
        query["status"] = {"$in": ["pending", "accepted"]}
    docs = _db.assignments.find(query, {"employee_id": 1})
    return {d["employee_id"] for d in docs}
```

### Fix in `update_match_status` REJECTED handler (line ~860-906):

Replace the SearchService fallback block (line ~882-906) with:

```python
            else:
                try:
                    search_svc = SearchService()
                    # Exclude ALL employees assigned to ANY job in this project (pending or accepted)
                    excluded = _get_project_assigned_employees(project_id)
                    all_res  = search_svc.search_employees_for_job(job_id, project_id, limit=10, min_score=0.0)
                    filtered = [r for r in all_res if r["employee_id"] not in excluded]
                    if filtered:
                        top = filtered[0]
                        top["scorePercentage"] = round(top["matching_score"] * 100)
                        top["matchScore"]      = top["matching_score"]
                        emp_doc = _db.employees.find_one({"_id": top["employee_id"]}, {"name": 1})
                        top["employeeName"] = emp_doc.get("name", top["employee_id"]) if emp_doc else top["employee_id"]
                        try:
                            top["explanation"] = explain_assignment(
                                job_id, top["employee_id"], project_id, top["matching_score"],
                                top.get("matched_skills", []), top.get("missing_skills", []),
                            )
                        except Exception:
                            top["explanation"] = f"Match score: {top['scorePercentage']}/100."
                        suggestion = top
                except Exception as exc_inner:
                    logger.warning("[AutoSuggest] Real-time scoring failed: %s", exc_inner)
```

### Fix in `search_job_candidates` endpoint (line ~1178):

After getting results from SearchService, filter out employees already on the project:

```python
@app.get("/api/v1/projects/{project_id}/jobs/{job_id}/candidates", tags=["Matches"])
async def search_job_candidates(
    project_id: str, job_id: str, limit: int = 50,
    current_user: dict = Depends(_get_current_user),
):
    project_id = sanitize_string(project_id, 100)
    job_id     = sanitize_string(job_id, 100)
    try:
        search_svc = SearchService()
        results = search_svc.search_employees_for_job(job_id, project_id, limit * 2)  # fetch extra to compensate for filtering
        
        # Filter out employees already assigned (pending/accepted) to ANY job in this project
        excluded = _get_project_assigned_employees(project_id)
        results = [r for r in results if r["employee_id"] not in excluded]
        results = results[:limit]  # trim to requested limit
        
        for rank, r in enumerate(results, start=1):
            r["rank"]             = rank
            r["score_percentage"] = round(r["matching_score"] * 100)
        # ... rest unchanged (explanation generation for top 5, etc.)
```

### Fix in `reject_and_find_next` endpoint (line ~927):

Same pattern — use `_get_project_assigned_employees()` instead of the manual exclusion:

```python
        # Replace lines ~968-973:
        excluded = _get_project_assigned_employees(project_id)
        all_res  = search_svc.search_employees_for_job(job_id, project_id, limit=10, min_score=0.0)
        filtered = [r for r in all_res if r["employee_id"] not in excluded]
```

### Fix in `manual_swap` endpoint:

Same pattern for the SearchService call inside manual_swap.

## Summary of Changes

1. Add `_get_project_assigned_employees()` helper function
2. Fix `manual_assign_candidate`: compute score BEFORE creating assignment, check for existing pending assignment to avoid duplicates, remove `notes="Manually assigned via UI"`
3. Fix `search_job_candidates`: filter out project-level assigned employees
4. Fix `update_match_status` REJECTED: use project-level exclusion in SearchService fallback
5. Fix `reject_and_find_next`: same project-level exclusion
6. Fix `manual_swap`: compute real score via SearchService (same pattern as manual_assign_candidate)

All fixes ensure:
- No employee is ever suggested if they're already pending/accepted on ANY job in the same project
- Scores are always computed before assignment creation (never 0%)
- No duplicate assignments are created
- Notes field is clean (no misleading "Manually assigned via UI")
