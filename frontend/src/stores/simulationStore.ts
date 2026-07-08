// Simulation store

import { create } from "zustand";
import { api } from "../lib/api";

interface SimState {
  jobs: any[];
  activeJob: any | null;
  isRunning: boolean;
  results: any[];
  replayData: any | null;
  startSimulation: (params: any) => Promise<number>;
  pollJob: (jobId: number) => Promise<void>;
  loadJobs: () => Promise<void>;
  loadJob: (jobId: number) => Promise<void>;
  loadReplay: (jobId: number, matchIndex: number) => Promise<void>;
  cancelPolling: () => void;
}

let _pollTimer: ReturnType<typeof setTimeout> | null = null;

export const useSimulationStore = create<SimState>((set, get) => ({
  jobs: [],
  activeJob: null,
  isRunning: false,
  results: [],
  replayData: null,

  startSimulation: async (params) => {
    const { job_id } = await api.simulate(params);
    set({ isRunning: true });
    get().pollJob(job_id);
    return job_id;
  },

  pollJob: async (jobId) => {
    try {
      const job = await api.getJob(jobId);
      if (job) {
        set({ activeJob: job, results: Array.isArray(job.results) ? job.results : [] });
      }
      if (job?.status === "completed" || job?.status === "failed") {
        set({ isRunning: false });
        return;
      }
      _pollTimer = setTimeout(() => get().pollJob(jobId), 1500);
    } catch { set({ isRunning: false }); }
  },

  loadJobs: async () => {
    try {
      const jobs = await api.getJobs();
      set({ jobs: Array.isArray(jobs) ? jobs : [] });
    } catch {}
  },

  loadJob: async (jobId) => {
    try {
      const job = await api.getJob(jobId);
      if (job) set({ activeJob: job, results: Array.isArray(job.results) ? job.results : [] });
    } catch {}
  },

  loadReplay: async (jobId, matchIndex) => {
    try {
      const data = await api.getReplay(jobId, matchIndex);
      set({ replayData: data });
    } catch {}
  },

  cancelPolling: () => {
    if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
    set({ isRunning: false });
  },
}));
