import { api } from "./client";

export type JobStatus = "queued" | "running" | "succeeded" | "failed";

export interface AnalyzeAssetOut {
  job_id: string;
  intelligence_id: string;
  status: string;
}

export interface MediaIntelligence {
  id: string;
  asset_id: string;
  project_id: string | null;
  status: string;
  transcript_text: string;
  speakers: string[];
  diarized: boolean;
  scenes: Array<Record<string, any>>;
  semantic_units: Array<Record<string, any>>;
  visual_observations: Array<Record<string, any>>;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  project_id: string | null;
  asset_id: string | null;
  type: "media_probe" | "render_export" | "media_intelligence";
  status: JobStatus;
  progress: number;
  error_code: string | null;
  error_message: string | null;
  result: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export const intelligenceApi = {
  analyze: (assetId: string) =>
    api<AnalyzeAssetOut>(`/assets/${assetId}/analyze`, { method: "POST" }),
  get: (assetId: string) =>
    api<MediaIntelligence>(`/assets/${assetId}/intelligence`),
};

export const jobsApi = {
  get: (jobId: string) => api<Job>(`/jobs/${jobId}`),
};
