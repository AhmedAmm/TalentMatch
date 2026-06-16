# SmartStaff Backend API Documentation

**AI-Powered Talent Matching Platform**

**Version**: 1.0.0  
**Base URL**: `/api/v1`

This document describes all public endpoints available in `main.py` for frontend integration.

---

## Overview

The SmartStaff backend provides a complete set of RESTful APIs for:

- User authentication and role management
- Employee (talent) management with CV parsing
- Project and job creation via manual input or PO PDF ingestion
- AI-powered smart matching with explainable results
- CV generation (tailored Canadian-style DOCX in English/French)
- Manual overrides and assignment management

**Security Features**:
- JWT Authentication
- Cloudflare Turnstile bot protection
- Input sanitization & NoSQL injection protection
- Role-based access control (PO, RH/HR, ADMIN)
- Global Security Middleware

---

## 1. Authentication

| Method | Endpoint                  | Description                                              | Access          | Request Body / Params                          | Response |
|--------|---------------------------|----------------------------------------------------------|-----------------|------------------------------------------------|----------|
| POST   | `/auth/login`             | Authenticate user and return JWT token                   | Public          | `{ email, password }` + Turnstile header       | JWT + user info |
| POST   | `/auth/register`          | Register new user (PO, RH, ADMIN)                        | Public          | `{ email, name, password, role }`              | User object |
| POST   | `/auth/logout`            | Logout (client-side token deletion)                      | Authenticated   | -                                              | Success message |
| GET    | `/auth/me`                | Get current authenticated user profile                   | Authenticated   | -                                              | User details |

---

## 2. Users Management (Admin Only)

| Method | Endpoint                  | Description                                              | Access     | Notes |
|--------|---------------------------|----------------------------------------------------------|------------|-------|
| GET    | `/users`                  | List all system users                                    | ADMIN      | - |
| POST   | `/users`                  | Create new system user                                   | ADMIN      | - |
| DELETE | `/users/{user_id}`        | Soft-delete / deactivate user                            | ADMIN      | - |

---

## 3. Employees / Talent Pool

| Method | Endpoint                              | Description                                                      | Access            | Key Parameters / Body |
|--------|---------------------------------------|------------------------------------------------------------------|-------------------|-----------------------|
| GET    | `/employees`                          | List employees (with search and availability filter)             | Authenticated     | Query: `search`, `available` |
| GET    | `/employees/{employee_id}`            | Get detailed employee profile                                    | Authenticated     | - |
| POST   | `/employees/upload-cv`                | Upload CV PDF → AI parse → create/update profile + trigger re-matching | Authenticated     | Multipart: `file` + `email` |

---

## 4. CV Generation

| Method | Endpoint                              | Description                                                      | Access            | Key Parameters |
|--------|---------------------------------------|------------------------------------------------------------------|-------------------|----------------|
| GET    | `/employees/{employee_id}/generate-cv`| Generate tailored DOCX CV (GET version)                          | Authenticated     | Query: `project_id`, `job_id`, `language` |
| POST   | `/cv/generate`                        | Generate tailored DOCX CV (POST version - recommended)           | Authenticated     | JSON: `{ employee_id, project_id?, job_id?, language? }` |

---

## 5. Projects

| Method | Endpoint                              | Description                                                      | Access                | Key Input |
|--------|---------------------------------------|------------------------------------------------------------------|-----------------------|-----------|
| GET    | `/projects`                           | List all projects (filter by PO or status)                       | Authenticated         | Query: `po_id`, `status` |
| GET    | `/projects/{project_id}`              | Get project details + associated jobs                            | Authenticated         | - |
| POST   | `/projects`                           | Create new project manually + trigger matching                   | PO / Admin            | `CreateProjectRequest` |
| PATCH  | `/projects/{project_id}`              | Update project (status or PO reassignment)                       | PO / Admin            | `UpdateProjectRequest` |
| PATCH  | `/projects/{project_id}/status`       | Update project status only                                       | PO / Admin            | `{ status }` |
| PATCH  | `/projects/{project_id}/po`           | Reassign Product Owner (ADMIN only)                              | ADMIN                 | `{ po_id }` |

**PDF Ingestion Endpoints**:

| Method | Endpoint                    | Description                                                      | Access         | Input |
|--------|-----------------------------|------------------------------------------------------------------|----------------|-------|
| POST   | `/projects/parse-pdf`       | Parse PO PDF and return structured preview (no DB write)         | PO / Admin     | Multipart PDF |
| POST   | `/projects/ingest-pdf`      | Parse PO PDF → create project + jobs + trigger matching          | PO / Admin     | Multipart PDF + `po_id` |

---

## 6. AI Matching & Assignments

| Method | Endpoint                                           | Description                                                              | Access         | Key Input |
|--------|----------------------------------------------------|--------------------------------------------------------------------------|----------------|-----------|
| GET    | `/projects/{project_id}/matches`                   | Get all matches for a project (sorted by score)                          | Authenticated  | - |
| GET    | `/matches`                                         | Get matches with filters (project_id, job_id, status)                    | Authenticated  | Query params |
| POST   | `/projects/{project_id}/run-matching`              | **Manually trigger** the full AI matching pipeline                       | PO / Admin     | - |
| PATCH  | `/matches/{match_id}/status`                       | Accept or Reject a match (with smart cascade effects)                    | PO / Admin     | `{ status: "ACCEPTED" \| "REJECTED" }` |
| POST   | `/matches/{match_id}/reject-next`                  | Reject current + suggest next best candidate                             | PO / Admin     | - |
| POST   | `/matches/{match_id}/unassign`                     | Unassign accepted employee + find replacement                            | PO / Admin     | - |
| POST   | `/matches/manual-swap`                             | Manual swap (frontend-friendly)                                          | PO / Admin     | `ManualSwapRequest` |
| POST   | `/projects/{project_id}/jobs/{job_id}/swap`        | Legacy manual swap endpoint                                              | PO / Admin     | `SwapRequest` |

---

## 7. Health Check

| Method | Endpoint   | Description                   | Access   |
|--------|------------|-------------------------------|----------|
| GET    | `/health`  | Backend health status check   | Public   |

---

## Frontend Integration Recommendations

### Typical Workflow:

1. **Login** → `POST /api/v1/auth/login`
2. **Load Dashboard** → `GET /api/v1/projects`
3. **View Project** → `GET /api/v1/projects/{project_id}`
4. **Run Matching** → `POST /api/v1/projects/{project_id}/run-matching` (or it runs automatically after ingest)
5. **Review Matches** → `GET /api/v1/projects/{project_id}/matches`
6. **Decide** → `PATCH /api/v1/matches/{match_id}/status`
7. **Generate CV** → `POST /api/v1/cv/generate` (after acceptance)

### Important Notes:

- **Background Tasks**: Many operations (CV upload, accept/reject, ingest) trigger matching automatically via `BackgroundTasks`.
- **Cascade Effects**: Accepting a candidate automatically makes them unavailable and re-triggers matching on affected projects.
- **File Handling**: All PDF uploads are validated for security (magic bytes, size, Turnstile).
- **Response Format**: Most endpoints return serialized clean objects suitable for frontend consumption (`_serialize_employee`, `_assignment_to_match`).

---

**Generated for SmartStaff Backend**  
**Main File**: `main.py`  
**Date**: April 2026
