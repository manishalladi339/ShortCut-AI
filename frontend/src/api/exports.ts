import { api } from "./client";

export interface ExportArtifact {
  id: string;
  user_id: string;
  project_id: string;
  sequence_id: string;
  project_state_version: number;
  status: string;
  preset: string;
  job_id: string;
  storage_key: string | null;
  download_url: string | null;
  duration_sec: number | null;
  render_metadata: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export const exportsApi = {
  create: (
    projectId: string,
    body: { sequence_id?: string | null; preset?: "vertical_1080p" | "source" } = {},
  ) =>
    api<ExportArtifact>(`/projects/${projectId}/exports`, {
      method: "POST",
      body,
    }),
  list: (projectId: string) =>
    api<ExportArtifact[]>(`/projects/${projectId}/exports`),
  get: (projectId: string, exportId: string) =>
    api<ExportArtifact>(`/projects/${projectId}/exports/${exportId}`),
};
