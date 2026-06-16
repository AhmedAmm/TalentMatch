# Diapo Platform — API Integration Documentation

> **Version:** 3.0 (Live Integration)  
> **Last Updated:** April 6, 2026  
> **Backend:** SmartStaff FastAPI  
> **Frontend:** React + Tailwind CSS + React Router  
> **API Client:** `/src/app/api/apiClient.ts`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Configuration](#2-configuration)
3. [Authentication Flow](#3-authentication-flow)
4. [API Client Reference](#4-api-client-reference)
5. [Endpoint Mapping](#5-endpoint-mapping)
6. [Data Models & Normalizers](#6-data-models--normalizers)
7. [Error Handling](#7-error-handling)
8. [Role-Based Access Control](#8-role-based-access-control)
9. [File Upload Flows](#9-file-upload-flows)
10. [CV Generation](#10-cv-generation)
11. [Deployment & CORS](#11-deployment--cors)

---

## 1. Architecture Overview

```
┌────────────────────────┐         ┌──────────────────────────────────┐
│   React Frontend       │  HTTP   │   SmartStaff FastAPI Backend     │
│   (Port 5173)          │◄──────►│   (Port 8000)                    │
│                        │         │                                  │
│  apiClient.ts ─────────┼────────►│  /api/v1/auth/*                  │
│    ├─ api.login()      │         │  /api/v1/users/*                 │
│    ├─ api.getProjects()│         │  /api/v1/projects/*              │
│    ├─ api.getEmployees()│        │  /api/v1/employees/*             │
│    ├─ api.getMatches() │         │  /api/v1/matches/*               │
│    ├─ api.generateCV() │         │  /api/v1/cv/*                    │
│    ├─ api.parsePDF()   │         │  /api/v1/projects/parse-pdf      │
│    └─ api.ingestPDF()  │         │  /api/v1/projects/ingest-pdf     │
│                        │         │                                  │
│  JWT stored in         │         │  AI Agents:                      │
│  localStorage          │         │  ├─ PDF Parser                   │
│                        │         │  ├─ Matching Engine               │
│                        │         │  └─ CV Generator                  │
└────────────────────────┘         └───────────────────────────────��──┘
```

---

## 2. Configuration

### Environment Variable

Set your backend URL in `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

If not set, the client defaults to `/api/v1` (works with Vite proxy).

### Vite Proxy (Development)

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
});
```

---

## 3. Authentication Flow

1. User submits email/password on `/` (LoginPage)
2. `api.login()` calls `POST /api/v1/auth/login`
3. JWT token is stored in `localStorage` as `access_token`
4. On page reload, `AuthContext` calls `api.getMe()` → `GET /api/v1/auth/me` to restore session
5. All subsequent API calls include `Authorization: Bearer <token>` header automatically
6. Logout clears `localStorage` and resets user state

### Token Management (apiClient.ts)

```typescript
setToken(token: string)   // saves to localStorage
clearToken()              // removes from localStorage
getToken(): string | null // reads from localStorage
```

---

## 4. API Client Reference

All methods are on the `api` object exported from `/src/app/api/apiClient.ts`.

### Auth

| Method | Signature | Backend Endpoint | Description |
|--------|-----------|-----------------|-------------|
| `api.login` | `(email, password) → { user, token }` | `POST /auth/login` | Authenticate and store JWT |
| `api.getMe` | `() → User` | `GET /auth/me` | Get current user from token |
| `api.logout` | `() → void` | Client-side only | Clear stored token |

### Users (Admin)

| Method | Signature | Backend Endpoint |
|--------|-----------|-----------------|
| `api.getUsers` | `() → User[]` | `GET /users` |
| `api.addUser` | `({ name, email, role, password? }) → User` | `POST /users` |
| `api.deleteUser` | `(id) → void` | `DELETE /users/{id}` |

### Projects

| Method | Signature | Backend Endpoint |
|--------|-----------|-----------------|
| `api.getProjects` | `({ po_id?, status? }?) → Project[]` | `GET /projects` |
| `api.getProjectById` | `(id) → Project` | `GET /projects/{id}` |
| `api.createProject` | `({ name, client, description?, poId, jobs }) → Project` | `POST /projects` |
| `api.updateProjectStatus` | `(id, status) → Project` | `PATCH /projects/{id}/status` |
| `api.reassignProjectPO` | `(projectId, poId) → Project` | `PATCH /projects/{id}/po` |

### PDF Ingestion

| Method | Signature | Backend Endpoint | Description |
|--------|-----------|-----------------|-------------|
| `api.parsePDF` | `(file: File) → ParsedProjectData` | `POST /projects/parse-pdf` | Preview extraction (no DB write) |
| `api.ingestPDF` | `(file: File, poId: string) → Project` | `POST /projects/ingest-pdf` | Full pipeline: parse + create + match |

### Employees

| Method | Signature | Backend Endpoint |
|--------|-----------|-----------------|
| `api.getEmployees` | `({ search?, available? }?) → Employee[]` | `GET /employees` |
| `api.getEmployeeById` | `(id) → Employee` | `GET /employees/{id}` |
| `api.uploadCV` | `(email, file: File) → Employee` | `POST /employees/upload-cv` |

### Matches

| Method | Signature | Backend Endpoint |
|--------|-----------|-----------------|
| `api.getMatchesForProject` | `(projectId) → Match[]` | `GET /projects/{id}/matches` |
| `api.acceptMatch` | `(matchId) → void` | `PATCH /matches/{id}/status` |
| `api.rejectAndSuggestNext` | `(matchId) → void` | `POST /matches/{id}/reject-next` |
| `api.unassignMatch` | `(matchId) → void` | `POST /matches/{id}/unassign` |
| `api.manualSwap` | `(projectId, jobId, newEmployeeId, oldMatchId?) → void` | `POST /matches/manual-swap` |
| `api.runMatching` | `(projectId) → void` | `POST /projects/{id}/run-matching` |

### CV Generation

| Method | Signature | Backend Endpoint | Returns |
|--------|-----------|-----------------|---------|
| `api.generateCV` | `(employeeId, projectId?, jobId?, language?) → Blob` | `POST /cv/generate` | Binary `.docx` |

### Health

| Method | Signature | Backend Endpoint |
|--------|-----------|-----------------|
| `api.health` | `() → any` | `GET /health` |

---

## 5. Endpoint Mapping

### Complete Frontend → Backend Mapping

| Frontend Call | HTTP | Backend Path |
|---|---|---|
| `api.login(email, password)` | `POST` | `/api/v1/auth/login` |
| `api.getMe()` | `GET` | `/api/v1/auth/me` |
| `api.getUsers()` | `GET` | `/api/v1/users` |
| `api.addUser({...})` | `POST` | `/api/v1/users` |
| `api.deleteUser(id)` | `DELETE` | `/api/v1/users/{id}` |
| `api.getProjects({po_id?, status?})` | `GET` | `/api/v1/projects?po_id=&status=` |
| `api.getProjectById(id)` | `GET` | `/api/v1/projects/{id}` |
| `api.createProject({...})` | `POST` | `/api/v1/projects` |
| `api.updateProjectStatus(id, status)` | `PATCH` | `/api/v1/projects/{id}/status` |
| `api.reassignProjectPO(id, poId)` | `PATCH` | `/api/v1/projects/{id}/po` |
| `api.parsePDF(file)` | `POST` | `/api/v1/projects/parse-pdf` |
| `api.ingestPDF(file, poId)` | `POST` | `/api/v1/projects/ingest-pdf` |
| `api.getEmployees({search?, available?})` | `GET` | `/api/v1/employees?search=&available=` |
| `api.getEmployeeById(id)` | `GET` | `/api/v1/employees/{id}` |
| `api.uploadCV(email, file)` | `POST` | `/api/v1/employees/upload-cv` |
| `api.getMatchesForProject(projectId)` | `GET` | `/api/v1/projects/{id}/matches` |
| `api.acceptMatch(matchId)` | `PATCH` | `/api/v1/matches/{id}/status` |
| `api.rejectAndSuggestNext(matchId)` | `POST` | `/api/v1/matches/{id}/reject-next` |
| `api.unassignMatch(matchId)` | `POST` | `/api/v1/matches/{id}/unassign` |
| `api.manualSwap(...)` | `POST` | `/api/v1/matches/manual-swap` |
| `api.runMatching(projectId)` | `POST` | `/api/v1/projects/{id}/run-matching` |
| `api.generateCV(...)` | `POST` | `/api/v1/cv/generate` |
| `api.health()` | `GET` | `/api/v1/health` |

---

## 6. Data Models & Normalizers

The API client includes normalizer functions that convert snake_case backend responses to camelCase frontend types. This means the backend can use either convention.

### Supported Mappings

| Backend field | Frontend field |
|---|---|
| `_id` or `id` | `id` |
| `po_id` or `poId` | `poId` |
| `is_available` or `isAvailable` | `isAvailable` |
| `match_score` or `matchScore` or `score` | `matchScore` |
| `match_reason` or `matchReason` or `reason` | `matchReason` |
| `employee_id` or `employeeId` | `employeeId` |
| `project_id` or `projectId` | `projectId` |
| `job_id` or `jobId` | `jobId` |
| `avatar_url` or `avatarUrl` | `avatarUrl` |
| `problem_solving` or `problemSolving` | `problemSolving` |
| `project_name` or `name` | `name` |
| `client_name` or `client` | `client` |
| `job_title` or `title` | `title` |
| `summary` or `bio` or `about` | `about` |
| `competency_scores` or `stats` | `stats` |
| `job_titles` or `jobs` | `jobs` (in ParsedProjectData) |

### TypeScript Types

```typescript
type Role = 'ADMIN' | 'PO' | 'RH';
type ProjectStatus = 'IN_PROGRESS' | 'FINISHED' | 'CANCELED';
type MatchStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED';

interface User { id, name, email, role }
interface Project { id, name, client, status, poId, jobs[], description? }
interface ProjectJob { id, title }
interface Employee { id, name, email, about, experiences[], skills[], isAvailable, avatarUrl?, stats }
interface Experience { id, title, company, period, description }
interface Match { id, projectId, jobId, employeeId, status, matchReason, matchScore }
interface ParsedProjectData { name, client, description, jobs[] }
```

---

## 7. Error Handling

The API client throws `ApiError` with a `status` property:

```typescript
try {
  await api.getProjects();
} catch (err) {
  if (err.status === 401) { /* redirect to login */ }
  if (err.status === 403) { /* insufficient permissions */ }
  alert(err.message); // human-readable from backend `detail` field
}
```

### Auto-parsed Error Messages

The client attempts to extract `detail` or `message` from JSON error responses. Falls back to `"Request failed (status)"`.

---

## 8. Role-Based Access Control

| Endpoint Group | ADMIN | PO | RH |
|---|---|---|---|
| Auth (login, me) | Y | Y | Y |
| Users CRUD | Y | - | - |
| Projects (read) | Y | Own only | - |
| Projects (create/update) | Y | Y | - |
| PDF Ingestion | Y | Y | - |
| Project PO Reassign | Y | - | - |
| Employees (read) | - | Y | Y |
| Employee CV Upload | - | - | Y |
| Matches (read) | Y | Own projects | - |
| Matches (manage) | Y | Own projects | - |
| CV Generation | - | Y | Y |

---

## 9. File Upload Flows

### PO: Project PDF Upload (Full Pipeline)

```
User drops PDF
  │
  ├─ Step 1: api.parsePDF(file)
  │   └→ POST /projects/parse-pdf (multipart)
  │   └→ Returns: { name, client, description, jobs[] }
  │   └→ UI shows extracted preview
  │
  ├─ Step 2: api.ingestPDF(file, poId)
  │   └→ POST /projects/ingest-pdf (multipart + po_id)
  │   └→ Backend: creates project + jobs + runs matching
  │   └→ Returns: Project object with jobs
  │
  └─ Step 3: Navigate to /project/:id
      └→ View matches generated by AI
```

### RH: Employee CV Upload

```
User submits email + PDF
  │
  └─ api.uploadCV(email, file)
      └→ POST /employees/upload-cv (multipart: email + file)
      └→ Backend: AI parses CV → creates/updates employee + triggers re-matching
      └→ Returns: Employee object
```

---

## 10. CV Generation

The `api.generateCV()` method returns a `Blob` (binary `.docx` file). The frontend downloads it like this:

```typescript
const blob = await api.generateCV(employeeId, projectId, jobId, 'en');
const url = URL.createObjectURL(blob);
const link = document.createElement('a');
link.href = url;
link.download = `${employeeName}_Tailored_CV.docx`;
link.click();
URL.revokeObjectURL(url);
```

### Parameters

| Field | Required | Description |
|---|---|---|
| `employee_id` | Yes | Employee to generate CV for |
| `project_id` | No | If set, tailors CV for this project |
| `job_id` | No | If set, tailors CV for this specific role |
| `language` | No | `'en'` (default) or `'fr'` for French |

---

## 11. Deployment & CORS

### Backend CORS (FastAPI)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://your-domain.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Running

```bash
# Backend
cd backend
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
pnpm install
pnpm dev  # → http://localhost:5173
```

### Production

Set `VITE_API_BASE_URL` to your production API URL before building:

```bash
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1 pnpm build
```
