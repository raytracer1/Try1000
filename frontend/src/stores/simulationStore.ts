// Simulation store — job management and polling.

import { create } from "zustand";
import { api } from "../lib/api";

interface SimState {
  jobs: any[];
  activeJob: any | null;
  isRunning: boolean;
  results: any[];
  replayData: any | null;

  startSimulation: (params: any) => Promise<string>;
  pollJob: (jobId: string) => Promise<void>;
  loadJobs: () => Promise<void>;
  loadJob: (jobId: string) => Promise<void>;
  loadReplay: (jobId: string, matchIndex: number) => Promise<void>;
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
      set({ activeJob: job, results: job.results || [] });

      if (job.status === "completed" || job.status === "failed") {
        set({ isRunning: false });
        _pollTimer = null;
        return;
      }

      _pollTimer = setTimeout(() => get().pollJob(jobId), 1500);
    } catch (e) {
      set({ isRunning: false });
      _pollTimer = null;
    }
  },

  loadJobs: async () => {
    const jobs = await api.getJobs();
    set({ jobs });
  },

  loadJob: async (jobId) => {
    const job = await api.getJob(jobId);
    set({ activeJob: job, results: job.results || [] });
  },

  loadReplay: async (jobId, matchIndex) => {
    const data = await api.getReplay(jobId, matchIndex);
    set({ replayData: data });
  },

  cancelPolling: () => {
    if (_pollTimer) { clearTimeout(_pollTimer); _pollTimer = null; }
    set({ isRunning: false });
  },
}));
