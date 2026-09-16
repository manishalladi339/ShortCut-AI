import { api } from "./client";
import { ProjectState } from "./projectState";

export type ConstrainedComponent = "story" | "broll" | "music" | "captions";

export interface ConstrainedEditOperation {
  id: string;
  operation:
    | "remove_clip"
    | "set_clip_properties"
    | "update_caption"
    | "remove_caption"
    | "remove_speaker_ripple"
    | "replace_broll"
    | "retime_scope"
    | "repair_caption";
  component: ConstrainedComponent;
  payload: Record<string, any>;
  reason: string;
}

export interface ConstrainedEditProposal {
  id: string;
  project_id: string;
  user_id: string;
  project_state_version: number;
  status: "proposed" | "applied" | "rejected";
  instruction: string;
  interpreted_intents: string[];
  scope_start_sec: number;
  scope_end_sec: number;
  preserve_rules: string[];
  summary: string;
  operations: ConstrainedEditOperation[];
  created_at: string;
  updated_at: string;
  applied_project_state_version: number | null;
  applied_operation_ids: string[];
  skipped_operation_ids: string[];
}

export interface CreateConstrainedEditPayload {
  instruction: string;
  scope_start_sec?: number;
  scope_end_sec?: number;
}

export const constrainedEditsApi = {
  create: (projectId: string, body: CreateConstrainedEditPayload) =>
    api<ConstrainedEditProposal>(`/projects/${projectId}/constrained-edits`, {
      method: "POST",
      body,
    }),
  list: (projectId: string) =>
    api<ConstrainedEditProposal[]>(`/projects/${projectId}/constrained-edits`),
  createQaFixProposal: (projectId: string, exportId: string) =>
    api<ConstrainedEditProposal>(
      `/projects/${projectId}/exports/${exportId}/qa-fix-proposal`,
      { method: "POST" },
    ),
  apply: (
    projectId: string,
    proposalId: string,
    body: { expected_version: number; operation_ids?: string[] },
  ) =>
    api<ProjectState>(
      `/projects/${projectId}/constrained-edits/${proposalId}/apply`,
      { method: "POST", body },
    ),
};
