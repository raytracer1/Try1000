// API client for Try1000 backend.

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Auth
  register: (data: { email: string; username: string; password: string }) =>
    request<{ access_token: string }>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  login: (data: { email: string; password: string }) =>
    request<{ access_token: string }>("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  getMe: () => request<{ id: string; email: string; username: string }>("/auth/me"),

  // Teams
  getTeams: () => request<any[]>("/teams"),
  createTeam: (data: { name: string }) =>
    request<any>("/teams", { method: "POST", body: JSON.stringify(data) }),
  getTeam: (id: string) => request<any>(`/teams/${id}`),
  deleteTeam: (id: string) => request<any>(`/teams/${id}`, { method: "DELETE" }),
  addPlayer: (teamId: string, data: any) =>
    request<any>(`/teams/${teamId}/players`, { method: "POST", body: JSON.stringify(data) }),
  deletePlayer: (id: string) => request<any>(`/teams/players/${id}`, { method: "DELETE" }),

  // Tactics
  getTactics: () => request<any[]>("/tactics"),
  createTactic: (data: any) =>
    request<any>("/tactics", { method: "POST", body: JSON.stringify(data) }),
  getTactic: (id: string) => request<any>(`/tactics/${id}`),
  updateTactic: (id: string, data: any) =>
    request<any>(`/tactics/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteTactic: (id: string) => request<any>(`/tactics/${id}`, { method: "DELETE" }),

  // Simulation
  simulate: (data: any) =>
    request<{ job_id: string }>("/simulate", { method: "POST", body: JSON.stringify(data) }),
  getJobs: () => request<any[]>("/simulation/jobs"),
  getJob: (id: string) => request<any>(`/simulation/jobs/${id}`),
  getReplay: (jobId: string, matchIndex: number) =>
    request<any>(`/simulation/jobs/${jobId}/replay/${matchIndex}`),

  // Analytics
  getJobAnalytics: (jobId: string) => request<any>(`/analytics/job/${jobId}`),
  getMatchAnalytics: (jobId: string, matchIndex: number) =>
    request<any>(`/analytics/job/${jobId}/match/${matchIndex}`),

  // Agent
  analyzeTactic: (tacticId: string) =>
    request<any>("/agent/tactics/analyze", { method: "POST", body: JSON.stringify({ tactic_id: tacticId }) }),
  generateReport: (jobId: string) =>
    request<any>("/agent/match/report", { method: "POST", body: JSON.stringify({ job_id: jobId }) }),
  optimizeTactic: (tacticId: string, jobId: string) =>
    request<any>("/agent/tactics/optimize", { method: "POST", body: JSON.stringify({ tactic_id: tacticId, job_id: jobId }) }),
};
