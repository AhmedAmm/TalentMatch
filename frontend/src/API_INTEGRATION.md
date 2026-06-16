# SmartStaff Frontend-Backend API Integration Guide

> **Frontend**: React + Vite (port 5173)
> **Backend**: FastAPI (port 8000)
> **Base URL**: `VITE_API_BASE_URL=http://localhost:8000/api/v1` (with Vite proxy redirecting `/api/*` to `http://127.0.0.1:8000`)

---

## Architecture Overview

```
Browser
  |
  |-- React Router (SPA)
  |     |-- /              -> Dashboard (role switch: ADMIN | PO | RH)
  |     |-- /users         -> ManageUsers (ADMIN only)
  |     |-- /cv            -> RHDashboard (RH only)
  |     |-- /project/:id   -> POProjectDetails
  |     |-- /employee/:id  -> EmployeeProfile
  |
  |-- AuthContext (global state: user, token)
  |     |-- On mount: reads localStorage token -> GET /auth/me
  |     |-- login(): POST /auth/login -> stores JWT -> GET /auth/me
  |     |-- logout(): clears localStorage token
  |
  |-- apiClient.ts (centralized HTTP layer)
        |-- request<T>(): attaches Bearer token, sets Content-Type, handles errors
        |-- Normalizers: normalizeUser, normalizeProject, normalizeEmployee, normalizeMatch
```

---

## Authentication Flow

### 1. Login (`LoginPage.tsx`)

```
User submits email + password
    |
    v
AuthContext.login(email, password)
    |
    v
api.login(email, password)
    |-- POST /auth/login
    |   Body: { "email": "...", "password": "..." }
    |   Response: { "access_token": "jwt..." }
    |
    |-- setToken(token) -> localStorage
    |
    |-- GET /auth/me  (fetch full user profile)
    |   Headers: Authorization: Bearer <jwt>
    |   Response: { "_id": "...", "name": "...", "email": "...", "role": "PO" }
    |
    v
AuthContext sets user -> Dashboard renders based on user.role
```

> **Important**: The backend requires passwords >= 8 characters. Shorter passwords return HTTP 422.

### 2. Session Persistence (on page reload)

```
AuthProvider mounts
    |
    v
Reads localStorage('access_token')
    |-- If token exists -> GET /auth/me
    |   |-- Success: set user state
    |   |-- 401 error: clearToken(), show login
    |-- If no token -> show login
```

### 3. Logout

```
AuthContext.logout()
    |-- clearToken() -> removes from localStorage
    |-- setUser(null) -> redirects to login
```

---

## Page-by-Page API Call Map

### Dashboard (`/`) - Role Router

The `Dashboard.tsx` component reads `user.role` from `AuthContext` and renders the appropriate sub-dashboard:

| Role    | Component         | Description                    |
|---------|-------------------|--------------------------------|
| `ADMIN` | `AdminDashboard`  | All projects + PO reassignment |
| `PO`    | `PODashboard`     | My projects + PDF upload       |
| `RH`    | `RHDashboard`     | Employee list + CV upload      |

---

### Admin Dashboard (`AdminDashboard.tsx`)

**On mount:**
```
Promise.all([
  api.getProjects()        -> GET /projects
  api.getUsers()           -> GET /users
])
```

**PO Reassignment:**
```
handleChangePO(projectId, newPoId)
    |
    v
api.reassignProjectPO(projectId, poId)
    |-- PATCH /projects/{project_id}/po
    |   Body: { "po_id": "new_po@email.com" }
    |   Auth: ADMIN required
    |
    v
api.getProjects()  (reload list)
```

---

### Manage Users (`/users`) - `ManageUsers.tsx`

**On mount:**
```
api.getUsers() -> GET /users (ADMIN or RH required)
```

**Add user:**
```
api.addUser({ name, email, role, password })
    |-- POST /users
    |   Body: { "name": "...", "email": "...", "role": "PO|RH|ADMIN", "password": "..." }
    |   Default password: "defaultPass123!" (if not provided)
    |   Auth: ADMIN required
```

**Delete user:**
```
api.deleteUser(userId)
    |-- DELETE /users/{user_id}
    |   Returns: 204 No Content
    |   Auth: ADMIN required
```

---

### PO Dashboard (`PODashboard.tsx`)

**On mount:**
```
api.getProjects({ po_id: user.id })
    |-- GET /projects?po_id=<current_user_email>
```

**PDF Upload Flow (2-step):**
```
Step 1: Parse PDF (preview)
    api.parsePDF(file)
        |-- POST /projects/parse-pdf
        |   Body: FormData { file: <PDF> }
        |   Response: { name, client, description, jobs: ["title1", ...] }

Step 2: Ingest PDF (create project + trigger matching)
    api.ingestPDF(file, poId)
        |-- POST /projects/ingest-pdf
        |   Body: FormData { file: <PDF>, po_id: "<email>" }
        |   Response: Project object with jobs
        |   Side-effect: triggers background smart matching pipeline
```

**Navigate to project:**
```
onClick -> navigate(`/project/${project.id}`)
```

---

### PO Project Details (`/project/:id`) - `POProjectDetails.tsx`

This is the most API-intensive page. It manages the full candidate matching workflow.

**On mount:**
```
Promise.all([
  api.getProjectById(id)          -> GET /projects/{id}
  api.getMatchesForProject(id)    -> GET /projects/{id}/matches
  api.getEmployees()              -> GET /employees
])
```

The matches are enriched client-side by joining with employees:
```js
matches.map(match => ({
  ...match,
  employee: allEmployees.find(e => e.id === match.employeeId)
}))
```

**Accept a match:**
```
handleAccept(matchId)
    |-- PATCH /matches/{match_id}/status
    |   Body: { "status": "ACCEPTED" }
    |   Side-effects (backend):
    |     1. Mark assignment accepted
    |     2. Mark employee unavailable
    |     3. Cancel all other PENDING assignments for this employee
    |     4. Re-trigger matching for affected projects (background)
    |
    v
Reload all data (project + matches + employees)
```

**Reject + auto-assign next:**
```
handleReject(matchId)
    |
    v
api.rejectWithSuggestion(matchId)
    |-- POST /assignments/{assignment_id}/reject-with-suggestion
    |   Response: {
    |     message: "Assignment rejected",
    |     assignment_id: "...",
    |     suggestion: {              // or null
    |       employee_id: "...",
    |       name: "...",
    |       matching_score: 0.85,
    |       score_percentage: 85,
    |       explanation: "...",
    |       matched_skills: [...],
    |       missing_skills: [...]
    |     }
    |   }
    |
    |-- If suggestion exists:
    |   api.manualAssign(projectId, jobId, suggestion.employee_id)
    |       |-- POST /projects/{project_id}/jobs/{job_id}/assign
    |       |   Body: { "employee_id": "..." }
    |       |   Side-effects: computes real score, generates AI explanation
    |
    v
Reload all data
```

**Unassign an accepted employee:**
```
handleUnassign(matchId)
    |-- POST /matches/{match_id}/unassign
    |   Side-effects:
    |     1. Mark employee available again
    |     2. Re-trigger matching for the vacant job (background)
    |
    v
Reload all data
```

**Update project status:**
```
handleUpdateStatus(status)  // 'FINISHED' | 'CANCELED' | 'IN_PROGRESS'
    |-- PATCH /projects/{project_id}/status
    |   Body: { "status": "FINISHED" }
```

**Smart Candidate Search (swap flow):**
```
handleOpenCandidateSearch(jobId)
    |-- api.searchCandidates(projectId, jobId)
    |   GET /projects/{project_id}/jobs/{job_id}/candidates?limit=50
    |   Response: {
    |     job_id: "...",
    |     job_title: "...",
    |     candidates: [
    |       {
    |         employee_id, name, matching_score, score_percentage,
    |         rank, matched_skills, missing_skills, explanation
    |       }, ...
    |     ]
    |   }
    |   Note: Top 5 candidates get AI-generated explanations

handleManualAssign(jobId, employeeId, oldMatchId?)
    |-- POST /projects/{project_id}/jobs/{job_id}/assign
    |   Body: { "employee_id": "...", "replace_match_id": "..." }
    |   Response: Match with explanation + score_percentage + skill badges
```

**AI Explainability Report (per match):**
```
handleLoadExplanation(matchId, jobId, employeeId)
    |-- Checks if explanation already loaded from match data
    |-- If not:
    |   api.explainCandidateFit(projectId, jobId, employeeId)
    |       |-- POST /projects/{project_id}/jobs/{job_id}/candidates/{employee_id}/explain
    |       |   Response: { "explanation": "This candidate is a strong match because..." }
```

**Generate tailored CV:**
```
handleGenerateCV(employeeId, jobId)
    |-- api.generateCV(employeeId, projectId, jobId)
    |   POST /cv/generate
    |   Body: { "employee_id": "...", "project_id": "...", "job_id": "...", "language": "en" }
    |   Response: Binary .docx blob
    |
    v
Browser downloads file as "<Name>_Tailored_CV.docx"
```

---

### RH Dashboard (`/cv`) - `RHDashboard.tsx`

**On mount:**
```
api.getEmployees() -> GET /employees
```

**CV Upload:**
```
handleUploadCV(email, file)
    |-- api.uploadCV(email, file)
    |   POST /employees/upload-cv
    |   Body: FormData { email: "...", file: <PDF> }
    |   Side-effects (backend):
    |     1. AI parses PDF -> extracts name, skills, projects, education
    |     2. Creates/updates employee record in MongoDB
    |     3. Re-triggers matching for all open projects (background)
    |   Response: Employee object { id, name, email, skills, ... }
    |
    v
Reload employee list
```

**Navigate to employee profile:**
```
onClick -> navigate(`/employee/${emp.id}`)
```

---

### Employee Profile (`/employee/:id`) - `EmployeeProfile.tsx`

**On mount:**
```
Promise.all([
  api.getEmployeeById(id)            -> GET /employees/{employee_id}
  api.getProjectById(projectId)      -> GET /projects/{project_id}  (if ?projectId= query param)
])
```

**CV Generation:**
```
handleGenerateCV()
    |-- api.generateCV(employeeId, projectId)
    |   POST /cv/generate
    |   Body: { "employee_id": "...", "project_id": "...", "language": "en" }
    |   Response: Binary .docx blob
    |
    v
Browser downloads file
```

**Radar Chart Data (client-side only):**
```
Uses employee.stats: { technical, communication, leadership, problemSolving, teamwork }
Rendered via recharts RadarChart -- no API call
```

---

## API Client Architecture (`apiClient.ts`)

### Request Pipeline

```
api.someMethod(args)
    |
    v
request<T>(path, options)
    |
    |-- 1. Read JWT from localStorage
    |-- 2. Set headers:
    |       Authorization: Bearer <token>
    |       Content-Type: application/json  (unless FormData)
    |-- 3. Build URL: `${BASE_URL}${path}`
    |-- 4. fetch(url, options)
    |-- 5. Handle response:
    |       - !res.ok -> throw ApiError(detail, status)
    |       - 204 -> return undefined
    |       - application/json -> return res.json()
    |       - other -> return res.blob()  (for CV downloads)
```

### Data Normalizers

The backend uses snake_case (MongoDB), the frontend uses camelCase. Normalizers bridge the gap:

| Normalizer          | Key Mappings                                              |
|---------------------|-----------------------------------------------------------|
| `normalizeUser`     | `_id` -> `id`, `role` -> uppercase                       |
| `normalizeProject`  | `_id` -> `id`, `client_name` -> `client`, `po_id` -> `poId`, nested `jobs[].job_id` -> `jobs[].id` |
| `normalizeEmployee` | `_id` -> `id`, `is_available` -> `isAvailable`, `avatar_url` -> `avatarUrl`, `problem_solving` -> `problemSolving` |
| `normalizeMatch`    | `_id` -> `id`, `project_id` -> `projectId`, `employee_id` -> `employeeId`, `adequacy_score` -> `matchScore`, computes `scorePercentage` |

---

## Complete Endpoint Reference

| Method | Endpoint | Frontend Method | Used By | Auth |
|--------|----------|-----------------|---------|------|
| `POST` | `/auth/login` | `api.login()` | LoginPage via AuthContext | None |
| `GET` | `/auth/me` | `api.getMe()` | AuthContext (on mount + after login) | JWT |
| `GET` | `/users` | `api.getUsers()` | AdminDashboard, ManageUsers | ADMIN/RH |
| `POST` | `/users` | `api.addUser()` | ManageUsers | ADMIN |
| `DELETE` | `/users/{id}` | `api.deleteUser()` | ManageUsers | ADMIN |
| `GET` | `/projects` | `api.getProjects()` | AdminDashboard, PODashboard | JWT |
| `GET` | `/projects/{id}` | `api.getProjectById()` | POProjectDetails, EmployeeProfile | JWT |
| `POST` | `/projects` | `api.createProject()` | (available, not directly used -- ingestPDF used instead) | PO/ADMIN |
| `PATCH` | `/projects/{id}/status` | `api.updateProjectStatus()` | POProjectDetails | PO/ADMIN |
| `PATCH` | `/projects/{id}/po` | `api.reassignProjectPO()` | AdminDashboard | ADMIN |
| `POST` | `/projects/parse-pdf` | `api.parsePDF()` | PODashboard | PO/ADMIN |
| `POST` | `/projects/ingest-pdf` | `api.ingestPDF()` | PODashboard | PO/ADMIN |
| `GET` | `/employees` | `api.getEmployees()` | RHDashboard, POProjectDetails | JWT |
| `GET` | `/employees/{id}` | `api.getEmployeeById()` | EmployeeProfile | JWT |
| `POST` | `/employees/upload-cv` | `api.uploadCV()` | RHDashboard | JWT |
| `GET` | `/projects/{id}/matches` | `api.getMatchesForProject()` | POProjectDetails | JWT |
| `PATCH` | `/matches/{id}/status` | `api.acceptMatch()` | POProjectDetails | PO/ADMIN |
| `POST` | `/matches/{id}/reject-next` | `api.rejectAndSuggestNext()` | (available, not currently used) | PO/ADMIN |
| `POST` | `/matches/{id}/unassign` | `api.unassignMatch()` | POProjectDetails | PO/ADMIN |
| `POST` | `/matches/manual-swap` | `api.manualSwap()` | (available, not currently used) | PO/ADMIN |
| `GET` | `/projects/{pid}/jobs/{jid}/candidates` | `api.searchCandidates()` | POProjectDetails | JWT |
| `POST` | `/projects/{pid}/jobs/{jid}/candidates/{eid}/explain` | `api.explainCandidateFit()` | POProjectDetails | JWT |
| `POST` | `/projects/{pid}/jobs/{jid}/assign` | `api.manualAssign()` | POProjectDetails | PO/ADMIN |
| `POST` | `/assignments/{id}/reject-with-suggestion` | `api.rejectWithSuggestion()` | POProjectDetails | PO/ADMIN |
| `POST` | `/cv/generate` | `api.generateCV()` | POProjectDetails, EmployeeProfile | JWT |
| `GET` | `/graph/stats` | `api.getGraphStats()` | (available for admin tooling) | ADMIN |
| `POST` | `/graph/refresh` | `api.refreshGraphCache()` | (available for admin tooling) | ADMIN |

---

## Key Integration Patterns

### 1. Optimistic Reload Pattern
Every mutation (accept, reject, assign, unassign, status change) follows:
```
try { await api.mutateEndpoint(...) } catch (e) { alert(e.message) }
await loadData();  // always reload full state from backend
```

### 2. Background Matching Cascade
When a match is accepted, the backend automatically:
- Marks the employee unavailable
- Cancels their pending matches in OTHER projects
- Re-triggers matching for those projects
The frontend simply reloads and sees the updated state.

### 3. Reject + Auto-Replace Flow
```
Reject current candidate
    -> Backend suggests next best (via SearchService or DB pool)
    -> Frontend auto-assigns the suggestion
    -> Reload shows the new candidate in place
```

### 4. Two-Step PDF Ingestion
```
Parse (preview) -> Ingest (create + match)
```
This gives the PO a chance to see what was extracted before committing.

### 5. Score Normalization
- Backend stores `adequacy_score` as float 0.0-1.0
- `_assignment_to_match()` backend helper computes `scorePercentage` (0-100)
- Frontend `normalizeMatch()` reads `scorePercentage` directly, with fallback to `matchScore * 100`
- Candidate search results include both `matching_score` (0-1) and `score_percentage` (0-100)

### 6. Multi-Slot Jobs (Headcount)
- Each job has a `headcount` field (default 1) representing how many positions need to be filled
- The frontend `POProjectDetails` renders a slot grid per job: one card per position
- Slots are filled in order: accepted matches first, then best pending, then empty
- Each empty slot has its own "Search Candidates" button
- The grid layout adapts: 1 col for 1 position, 2 cols for 2, 3 cols for 3+
- `ProjectJobIn` backend model accepts `headcount` (validated 1-50)
- `normalizeProject` reads `j.headcount || 1` from the job doc

### 7. Reject with Real Score (no 0%)
- `rejectMatch()` calls `PATCH /matches/{id}/status` with `REJECTED`
- Backend (`nw_main2`) auto-suggests next candidate with real score computed via SearchService
- Returns `{ rejected, suggestion, message }` — suggestion includes `scorePercentage`, `explanation`
- `manual-swap` endpoint now also computes real score via SearchService (patched from returning 0%)
- Frontend never shows "Manually swapped" with 0% — always shows the actual match score