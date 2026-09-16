import { api } from "./client";
import { ProjectState } from "./projectState";

export interface HighlightCandidate {
  asset_id: string;
  intelligence_id: string;
  unit_index: number;
  start: number;
  end: number;
  text: string;
  heuristic_score: number;
  relevance_score: number;
  final_score: number;
  reasons: string[];
  narrative_role: string | null;
  speakers: string[];
  primary_speaker: string | null;
  dead_air_removed_sec: number;
  planned_duration_sec: number | null;
  visual_context: Record<string, any> | null;
}

export interface ProposedEditOperation {
  id: string | null;
  operation: string;
  payload: Record<string, any>;
  reason: string;
}

export interface StoryBeat {
  id: string;
  role: string;
  title: string;
  purpose: string;
  target_duration_sec: number;
  evidence_keys: string[];
  topic_ids: string[];
}

export interface AIEditPlan {
  id: string;
  project_id: string;
  user_id: string;
  project_state_version: number;
  status: string;
  objective: string;
  target_duration_sec: number;
  candidates: HighlightCandidate[];
  operations: ProposedEditOperation[];
  broll_recommendations: Array<Record<string, any>>;
  project_intelligence_id: string | null;
  project_intelligence_summary: string;
  project_topics: Array<Record<string, any>>;
  story_beats: StoryBeat[];
  audience_profile: Record<string, any>;
  narrative_summary: string;
  caption_suggestion: string;
  cta_suggestion: string;
  narrative_provider: string | null;
  narrative_model: string | null;
  evaluation: Record<string, any>;
  created_at: string;
  updated_at: string;
  applied_project_state_version: number | null;
  feedback_outcome: string | null;
  applied_operation_ids: string[];
  skipped_operation_ids: string[];
}

export interface CreateAIEditPlanPayload {
  objective?: string;
  target_audience?: string;
  target_duration_sec?: number;
  max_clips?: number;
  include_captions?: boolean;
  remove_dead_air?: boolean;
  rhythm_snap_broll?: boolean;
  broll_fade?: boolean;
  music_asset_id?: string | null;
  music_volume?: number;
  music_ducking?: boolean;
}

export const aiPlansApi = {
  list: (projectId: string) =>
    api<AIEditPlan[]>(`/projects/${projectId}/ai-plans`),
  get: (projectId: string, planId: string) =>
    api<AIEditPlan>(`/projects/${projectId}/ai-plans/${planId}`),
  create: (projectId: string, body: CreateAIEditPlanPayload) =>
    api<AIEditPlan>(`/projects/${projectId}/ai-plans`, {
      method: "POST",
      body,
    }),
  apply: (
    projectId: string,
    planId: string,
    body: {
      expected_version: number;
      replace_existing_video_clips?: boolean;
      operation_ids?: string[];
    },
  ) =>
    api<ProjectState>(`/projects/${projectId}/ai-plans/${planId}/apply`, {
      method: "POST",
      body,
    }),
  feedback: (
    projectId: string,
    planId: string,
    body: { outcome: "accepted" | "modified" | "rejected"; notes?: string },
  ) =>
    api(`/projects/${projectId}/ai-plans/${planId}/feedback`, {
      method: "POST",
      body,
    }),
};
