// =============================================================================
// Diapo API Client — connects to SmartStaff FastAPI backend
// Base URL is configured via VITE_API_BASE_URL env variable.
// Default: http://localhost:8000/api/v1
// =============================================================================

const BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || '/api/v1';

// ── Types ────────────────────────────────────────────────────────────────────

export type Role = 'ADMIN' | 'PO' | 'RH';
export type ProjectStatus = 'IN_PROGRESS' | 'FINISHED' | 'CANCELED';
export type MatchStatus = 'PENDING' | 'ACCEPTED' | 'REJECTED';

export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
}

export interface ProjectJob {
  id: string;
  title: string;
  headcount: number;
}

export interface Project {
  id: string;
  name: string;
  client: string;
  status: ProjectStatus;
  poId: string;
  jobs: ProjectJob[];
  description?: string;
}

export interface Experience {
  id: string;
  title: string;
  company: string;
  period: string;
  description: string;
}

export interface Employee {
  id: string;
  name: string;
  email: string;
  about: string;
  experiences: Experience[];
  skills: string[];
  isAvailable: boolean;
  avatarUrl?: string;
  stats: {
    technical: number;
    communication: number;
    leadership: number;
    problemSolving: number;
    teamwork: number;
  };
}

export interface Match {
  id: string;
  projectId: string;
  jobId: string;
  employeeId: string;
  status: MatchStatus;
  matchReason: string;
  matchScore: number;
  scorePercentage: number;
  explanation?: string;
  employee?: EmployeeSummary;
}

/** Lightweight employee data embedded in matches (from /projects/{id}/details) */
export interface EmployeeSummary {
  id: string;
  name: string;
  email: string;
  about: string;
  skills: string[];
  avatarUrl?: string;
  stats: {
    technical: number;
    communication: number;
    leadership: number;
    problemSolving: number;
    teamwork: number;
  };
}

export interface Candidate {
  employee_id: string;
  name: string;
  matching_score: number;
  score_percentage: number;
  rank?: number;
  matched_skills: { skill: string; level?: string }[];
  missing_skills: { skill: string; level?: string }[];
  explanation?: string;
}

export interface ParsedProjectData {
  name: string;
  client: string;
  description: string;
  jobs: string[];
}

// ── Token helpers ────────────────────────────────────────────────────────────

function getToken(): string | null {
  return localStorage.getItem('access_token');
}

export function setToken(token: string) {
  localStorage.setItem('access_token', token);
}

export function clearToken() {
  localStorage.removeItem('access_token');
}

// ── Core request helper ─────────────────────────────────────────────────────

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  // Only set Content-Type for JSON bodies (not FormData or URLSearchParams)
  if (!(options.body instanceof FormData) && !(options.body instanceof URLSearchParams)) {
    if (!headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }
  }

  const url = `${BASE_URL}${path}`;
  console.log('[API]', options.method || 'GET', url, 'headers:', headers, 'body:', options.body);

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const err = await res.json();
      msg = err.detail || err.message || msg;
    } catch { /* ignore parse error */ }
    throw new ApiError(msg, res.status);
  }

  // Handle 204 No Content
  if (res.status === 204) return undefined as T;

  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return res.json();
  }
  // For binary responses (CV download)
  return res.blob() as any;
}

// ── Normalizers ──────────────────────────────────────────────────────────────
// The backend may use snake_case. These functions normalize to our frontend types.

function normalizeUser(raw: any): User {
  return {
    id: raw.id || raw._id || '',
    name: raw.name || '',
    email: raw.email || '',
    role: (raw.role || 'PO').toUpperCase() as Role,
  };
}

function normalizeProject(raw: any): Project {
  return {
    id: raw.id || raw._id || '',
    name: raw.name || raw.project_name || '',
    client: raw.client || raw.client_name || '',
    status: (raw.status || 'IN_PROGRESS').toUpperCase() as ProjectStatus,
    poId: raw.poId || raw.po_id || '',
    description: raw.description || '',
    jobs: (raw.jobs || []).map((j: any) => ({
      id: j.id || j._id || j.job_id || '',
      title: j.title || j.job_title || '',
      headcount: j.headcount || 1,
    })),
  };
}

function normalizeEmployee(raw: any): Employee {
  const stats = raw.stats || raw.competency_scores || {};
  return {
    id: raw.id || raw._id || '',
    name: raw.name || '',
    email: raw.email || '',
    about: raw.about || raw.summary || raw.bio || '',
    skills: raw.skills || [],
    isAvailable: raw.isAvailable ?? raw.is_available ?? true,
    avatarUrl: raw.avatarUrl || raw.avatar_url || undefined,
    experiences: (raw.experiences || []).map((e: any) => ({
      id: e.id || e._id || '',
      title: e.title || '',
      company: e.company || '',
      period: e.period || '',
      description: e.description || '',
    })),
    stats: {
      technical: stats.technical ?? 0,
      communication: stats.communication ?? 0,
      leadership: stats.leadership ?? 0,
      problemSolving: stats.problemSolving ?? stats.problem_solving ?? 0,
      teamwork: stats.teamwork ?? 0,
    },
  };
}

function normalizeMatch(raw: any): Match {
  const rawScore = raw.matchScore ?? raw.match_score ?? raw.adequacy_score ?? raw.score ?? 0;
  const scorePct = raw.scorePercentage ?? raw.score_percentage ?? Math.round(rawScore * 100);
  return {
    id: raw.id || raw._id || '',
    projectId: raw.projectId || raw.project_id || '',
    jobId: raw.jobId || raw.job_id || '',
    employeeId: raw.employeeId || raw.employee_id || '',
    status: (raw.status || 'PENDING').toUpperCase() as MatchStatus,
    matchReason: raw.matchReason || raw.match_reason || raw.notes || '',
    matchScore: rawScore,
    scorePercentage: scorePct,
    explanation: raw.explanation || undefined,
    employee: raw.employee ? normalizeEmployeeSummary(raw.employee) : undefined,
  };
}

function normalizeEmployeeSummary(raw: any): EmployeeSummary {
  const stats = raw.stats || raw.competency_scores || {};
  return {
    id: raw.id || raw._id || '',
    name: raw.name || '',
    email: raw.email || '',
    about: raw.about || raw.summary || raw.bio || '',
    skills: raw.skills || [],
    avatarUrl: raw.avatarUrl || raw.avatar_url || undefined,
    stats: {
      technical: stats.technical ?? 0,
      communication: stats.communication ?? 0,
      leadership: stats.leadership ?? 0,
      problemSolving: stats.problemSolving ?? stats.problem_solving ?? 0,
      teamwork: stats.teamwork ?? 0,
    },
  };
}

// ── API methods ─────────────────────────────────────────────────────────────

export const api = {
  // ── Auth ────────────────────────────────────────────────────────────────
  login: async (email: string, password: string): Promise<{ user: User; token: string }> => {
    const data = await request<any>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    const token = data.access_token || data.token || '';
    setToken(token);
    // Backend login may not return full user object — fetch via /auth/me
    let user: User;
    if (data.user && data.user.email) {
      user = normalizeUser(data.user);
    } else {
      user = await api.getMe();
    }
    return { user, token };
  },

  getMe: async (): Promise<User> => {
    const data = await request<any>('/auth/me');
    return normalizeUser(data);
  },

  logout: () => {
    clearToken();
  },

  // ── Users (Admin) ────────────────────────────────────────────────────────
  getUsers: async (): Promise<User[]> => {
    const data = await request<any[]>('/users');
    return (data || []).map(normalizeUser);
  },

  addUser: async (user: { name: string; email: string; role: Role; password?: string }): Promise<User> => {
    const data = await request<any>('/users', {
      method: 'POST',
      body: JSON.stringify({
        name: user.name,
        email: user.email,
        role: user.role,
        password: user.password || 'defaultPass123!',
      }),
    });
    return normalizeUser(data);
  },

  deleteUser: async (id: string): Promise<void> => {
    await request<void>(`/users/${id}`, { method: 'DELETE' });
  },

  // ── Projects ─────────────────────────────────────────────────────────────
  getProjects: async (params?: { po_id?: string; status?: string }): Promise<Project[]> => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString() : '';
    const data = await request<any[]>(`/projects${qs}`);
    return (data || []).map(normalizeProject);
  },

  getProjectById: async (id: string): Promise<Project> => {
    const data = await request<any>(`/projects/${id}`);
    return normalizeProject(data);
  },

  /**
   * Composite endpoint: project + jobs + matches with embedded employees.
   * Falls back to 3 separate calls if /details endpoint is not available.
   */
  getProjectDetails: async (id: string): Promise<{ project: Project; matches: Match[] }> => {
    try {
      const data = await request<any>(`/projects/${id}/details`);
      const project = normalizeProject(data);
      const matches = (data.matches || []).map(normalizeMatch);
      return { project, matches };
    } catch (e: any) {
      // Fallback for backends that don't have /details yet
      if (e.status === 404 || e.status === 405) {
        const [proj, m, allEmployees] = await Promise.all([
          api.getProjectById(id),
          api.getMatchesForProject(id),
          api.getEmployees(),
        ]);
        const matches = m.map(match => ({
          ...match,
          employee: (() => {
            const emp = allEmployees.find(e => e.id === match.employeeId);
            if (!emp) return undefined;
            return { id: emp.id, name: emp.name, email: emp.email, about: emp.about, skills: emp.skills, avatarUrl: emp.avatarUrl, stats: emp.stats };
          })(),
        }));
        return { project: proj, matches };
      }
      throw e;
    }
  },

  createProject: async (project: { name: string; client: string; description?: string; poId: string; jobs: { title: string }[] }): Promise<Project> => {
    const data = await request<any>('/projects', {
      method: 'POST',
      body: JSON.stringify({
        name: project.name,
        client: project.client,
        description: project.description,
        poId: project.poId,
        status: 'IN_PROGRESS',
        jobs: project.jobs,
      }),
    });
    return normalizeProject(data);
  },

  updateProjectStatus: async (id: string, status: ProjectStatus): Promise<Project> => {
    const data = await request<any>(`/projects/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    });
    return normalizeProject(data);
  },

  reassignProjectPO: async (projectId: string, poId: string): Promise<Project> => {
    const data = await request<any>(`/projects/${projectId}/po`, {
      method: 'PATCH',
      body: JSON.stringify({ po_id: poId }),
    });
    return normalizeProject(data);
  },

  // ── PDF Ingestion ────────────────────────────────────────────────────────
  parsePDF: async (file: File): Promise<ParsedProjectData> => {
    const formData = new FormData();
    formData.append('file', file);
    const data = await request<any>('/projects/parse-pdf', {
      method: 'POST',
      body: formData,
    });
    return {
      name: data.name || data.project_name || '',
      client: data.client || data.client_name || '',
      description: data.description || '',
      jobs: data.jobs || data.job_titles || [],
    };
  },

  ingestPDF: async (file: File, poId: string): Promise<Project> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('po_id', poId);
    const data = await request<any>('/projects/ingest-pdf', {
      method: 'POST',
      body: formData,
    });
    return normalizeProject(data);
  },

  // ── Employees ────────────────────────────────────────────────────────────
  getEmployees: async (params?: { search?: string; available?: string }): Promise<Employee[]> => {
    const qs = params ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v) as [string, string][]).toString() : '';
    const data = await request<any[]>(`/employees${qs}`);
    return (data || []).map(normalizeEmployee);
  },

  getEmployeeById: async (id: string): Promise<Employee> => {
    const data = await request<any>(`/employees/${id}`);
    return normalizeEmployee(data);
  },

  uploadCV: async (email: string, file: File): Promise<Employee> => {
    const formData = new FormData();
    formData.append('email', email);
    formData.append('file', file);
    const data = await request<any>('/employees/upload-cv', {
      method: 'POST',
      body: formData,
    });
    return normalizeEmployee(data);
  },

  // ── Matches ─────────────────────────────────────────────────────────────
  getMatchesForProject: async (projectId: string): Promise<Match[]> => {
    const data = await request<any[]>(`/projects/${projectId}/matches`);
    return (data || []).map(normalizeMatch);
  },

  /** Accept match. If backend returns updated matches[], return them. */
  acceptMatch: async (matchId: string): Promise<Match[] | null> => {
    const data = await request<any>(`/matches/${matchId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'ACCEPTED' }),
    });
    // New backend returns { action, matches[] }; old returns single match
    if (data?.matches && Array.isArray(data.matches)) {
      return data.matches.map(normalizeMatch);
    }
    return null; // signal caller to reload
  },

  /** Reject match. Returns suggestion + optionally updated matches[]. */
  rejectMatch: async (matchId: string): Promise<{ rejected: Match; suggestion: any | null; message: string; matches: Match[] | null }> => {
    const data = await request<any>(`/matches/${matchId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status: 'REJECTED' }),
    });
    return {
      rejected: data.rejected ? normalizeMatch(data.rejected) : normalizeMatch(data),
      suggestion: data.suggestion || null,
      message: data.message || '',
      matches: data.matches ? data.matches.map(normalizeMatch) : null,
    };
  },

  rejectAndSuggestNext: async (matchId: string): Promise<void> => {
    await request(`/matches/${matchId}/reject-next`, { method: 'POST' });
  },

  /** Unassign. If backend returns updated matches[], return them. */
  unassignMatch: async (matchId: string): Promise<Match[] | null> => {
    const data = await request<any>(`/matches/${matchId}/unassign`, { method: 'POST' });
    if (data?.matches && Array.isArray(data.matches)) {
      return data.matches.map(normalizeMatch);
    }
    return null;
  },

  manualSwap: async (projectId: string, jobId: string, newEmployeeId: string, oldMatchId?: string): Promise<Match[] | null> => {
    const data = await request<any>('/matches/manual-swap', {
      method: 'POST',
      body: JSON.stringify({
        project_id: projectId,
        job_id: jobId,
        new_employee_id: newEmployeeId,
        old_match_id: oldMatchId,
      }),
    });
    if (data?.matches && Array.isArray(data.matches)) {
      return data.matches.map(normalizeMatch);
    }
    return null;
  },

  runMatching: async (projectId: string): Promise<void> => {
    await request(`/projects/${projectId}/run-matching`, { method: 'POST' });
  },

  // ── Candidates & Explainability ──────────────────────────────────────────
  searchCandidates: async (projectId: string, jobId: string, limit = 50): Promise<Candidate[]> => {
    const data = await request<any>(`/projects/${projectId}/jobs/${jobId}/candidates?limit=${limit}`);
    // Backend returns { job_id, job_title, candidates: [...] }
    const candidates = data.candidates || data || [];
    return Array.isArray(candidates) ? candidates : [];
  },

  explainCandidateFit: async (projectId: string, jobId: string, employeeId: string): Promise<string> => {
    const data = await request<any>(`/projects/${projectId}/jobs/${jobId}/candidates/${employeeId}/explain`, {
      method: 'POST',
    });
    return data.explanation || '';
  },

  /** Manual assign. If backend returns updated matches[], return them. */
  manualAssign: async (projectId: string, jobId: string, employeeId: string, replaceMatchId?: string): Promise<{ match: Match; matches: Match[] | null }> => {
    const data = await request<any>(`/projects/${projectId}/jobs/${jobId}/assign`, {
      method: 'POST',
      body: JSON.stringify({
        employee_id: employeeId,
        replace_match_id: replaceMatchId || undefined,
      }),
    });
    // New backend wraps in { action, match, matches[] }; old returns raw match
    const match = data.match ? normalizeMatch(data.match) : normalizeMatch(data);
    const matches = data.matches ? data.matches.map(normalizeMatch) : null;
    return { match, matches };
  },

  rejectWithSuggestion: async (assignmentId: string): Promise<{ suggestion: Candidate | null; message: string }> => {
    const data = await request<any>(`/assignments/${assignmentId}/reject-with-suggestion`, {
      method: 'POST',
    });
    return {
      suggestion: data.suggestion || null,
      message: data.message || '',
    };
  },

  // ── CV Generation ────────────────────────────────────────────────────────
  generateCV: async (employeeId: string, projectId?: string, jobId?: string, language?: string): Promise<Blob> => {
    const blob = await request<Blob>('/cv/generate', {
      method: 'POST',
      body: JSON.stringify({
        employee_id: employeeId,
        project_id: projectId || undefined,
        job_id: jobId || undefined,
        language: language || 'en',
      }),
    });
    return blob;
  },

  // ── Health ───────────────────────────────────────────────────────────────
  health: async (): Promise<any> => {
    return request('/health');
  },

  // ── Graph Cache (Admin) ────────────────────────────────────────────────
  getGraphStats: async (): Promise<any> => {
    return request('/graph/stats');
  },

  refreshGraphCache: async (): Promise<any> => {
    return request('/graph/refresh', { method: 'POST' });
  },
};