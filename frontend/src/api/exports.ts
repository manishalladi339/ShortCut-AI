export interface ExportQAIssue {
  code: string;
  severity: "info" | "warning" | "error";
  category: "timeline" | "visual" | "audio" | "captions";
  message: string;
  start_sec: number | null;
  end_sec: number | null;
  evidence: Record<string, any>;
  suggested_action: string | null;
  auto_fixable: boolean;
}

export interface ExportQACheck {
  id: string;
  status: "passed" | "warning" | "failed";
  summary: string;
  details: Record<string, any>;
}

export interface ExportQAReport {
  status: "passed" | "warnings" | "failed";
  issue_count: number;
  warning_count: number;
  error_count: number;
  issues: ExportQAIssue[];
  checks: ExportQACheck[];
  generated_at: string;
}

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
  qa_status: "passed" | "warnings" | "failed" | null;
  qa_report: ExportQAReport | null;
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
