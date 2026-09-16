import { api } from "./client";

export interface PreferenceEvidence {
  total: number;
  kept: number;
  skipped: number;
  keep_ratio: number | null;
}

export interface CreatorMemory {
  id: string;
  user_id: string;
  evidence_count: number;
  plan_feedback_count: number;
  constrained_edit_count: number;
  plan_acceptance_rate: number | null;
  optional_operation_preferences: Record<string, PreferenceEvidence>;
  preferences: Record<string, any>;
  confidence: Record<string, number>;
  summary: string;
  created_at: string;
  updated_at: string;
}

export const creatorMemoryApi = {
  get: () => api<CreatorMemory>("/users/me/creator-memory"),
  refresh: () =>
    api<CreatorMemory>("/users/me/creator-memory/refresh", { method: "POST" }),
};
