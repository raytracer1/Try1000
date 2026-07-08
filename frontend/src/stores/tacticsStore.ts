// Tactics store — current tactic being edited.

import { create } from "zustand";
import { api } from "../lib/api";
import { DEFAULT_TACTIC } from "../lib/constants";

interface TacticState {
  currentTactic: any | null;
  isDirty: boolean;
  isSaving: boolean;

  newTactic: (teamId: string) => void;
  loadTactic: (id: string) => Promise<void>;
  setFormation: (formation: string) => void;
  setParam: (key: string, value: number | string) => void;
  applyPreset: (preset: Record<string, any>) => void;
  saveTactic: (teamId: string) => Promise<string | null>;
  requestAnalysis: (tacticId: string) => Promise<void>;
}

export const useTacticsStore = create<TacticState>((set, get) => ({
  currentTactic: null,
  isDirty: false,
  isSaving: false,

  newTactic: (teamId) => {
    set({ currentTactic: { ...DEFAULT_TACTIC, team_id: teamId, name: "New Tactic", player_positions: {} }, isDirty: false });
  },

  loadTactic: async (id) => {
    const tactic = await api.getTactic(id);
    set({ currentTactic: tactic, isDirty: false });
  },

  setFormation: (formation) => {
    const state = get();
    if (!state.currentTactic) return;
    set({ currentTactic: { ...state.currentTactic, formation }, isDirty: true });
  },

  setParam: (key, value) => {
    const state = get();
    if (!state.currentTactic) return;
    set({ currentTactic: { ...state.currentTactic, [key]: value }, isDirty: true });
  },

  applyPreset: (preset) => {
    const state = get();
    if (!state.currentTactic) return;
    set({ currentTactic: { ...state.currentTactic, ...preset }, isDirty: true });
  },

  saveTactic: async (teamId) => {
    const state = get();
    if (!state.currentTactic) return null;
    set({ isSaving: true });
    try {
      const tactic = state.currentTactic;
      if (tactic.id) {
        const updated = await api.updateTactic(tactic.id, tactic);
        set({ currentTactic: updated, isDirty: false, isSaving: false });
        return updated.id;
      } else {
        const created = await api.createTactic({ ...tactic, team_id: teamId });
        set({ currentTactic: created, isDirty: false, isSaving: false });
        return created.id;
      }
    } catch (e) {
      set({ isSaving: false });
      throw e;
    }
  },

  requestAnalysis: async (tacticId) => {
    await api.analyzeTactic(tacticId);
  },
}));
