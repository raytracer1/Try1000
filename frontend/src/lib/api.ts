// API client — JWT sent via HttpOnly cookie automatically.

// Next.js rewrites proxy /api/* → backend. No CORS, cookies work natively.
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...options,
    credentials: "include",  // sends HttpOnly cookie
    headers: {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Auth
  googleAuth: (code: string) =>
    request<{ ok: boolean }>("/auth/google", { method: "POST", body: JSON.stringify({ code, redirect_uri: window.location.origin }) }),
  logout: () =>
    request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  getMe: () => request<{ id: number; email: string; username: string; llm_provider: string | null; llm_model: string | null; has_llm_key: boolean }>("/auth/me"),
  saveLLMSettings: (data: { llm_provider: string; llm_api_key: string; llm_model: string }) =>
    request<{ ok: boolean }>("/auth/settings", { method: "PUT", body: JSON.stringify(data) }),

  // Simulation
  simulate: (data: any) =>
    request<{ job_id: string }>("/simulate", { method: "POST", body: JSON.stringify(data) }),
  getJobs: () => request<any[]>("/simulation/jobs"),
  getJob: (id: string) => request<any>(`/simulation/jobs/${id}`),
  getReplay: (jobId: string, matchIndex: number) =>
    request<any>(`/simulation/jobs/${jobId}/replay/${matchIndex}`),

  // Analytics
  getJobAnalytics: (jobId: number) => request<any>(`/analytics/job/${jobId}`),

  // Agent
  analyzeTactic: (tacticId: number) =>
    request<any>("/agent/tactics/analyze", { method: "POST", body: JSON.stringify({ tactic_id: tacticId }) }),
  generateReport: (jobId: number) =>
    request<any>("/agent/match/report", { method: "POST", body: JSON.stringify({ job_id: jobId }) }),
  optimizeTactic: (tacticId: number, jobId: number) =>
    request<any>("/agent/tactics/optimize", { method: "POST", body: JSON.stringify({ tactic_id: tacticId, job_id: jobId }) }),
  getAgentResults: () => request<any[]>("/agent/results"),
};
