import { api } from "./client";

export type TrackKind = "video" | "overlay" | "audio" | "caption";

export interface ProjectTrack {
  id: string;
  kind: TrackKind;
  name: string;
  locked: boolean;
  muted: boolean;
  clips: Array<Record<string, any>>;
}

export interface ProjectSequence {
  id: string;
  name: string;
  timebase: { numerator: number; denominator: number };
  tracks: ProjectTrack[];
  captions: Array<Record<string, any>>;
}

export interface ProjectState {
  project_id: string;
  user_id: string;
  version: number;
  active_sequence_id: string;
  sequences: ProjectSequence[];
  created_at: string;
  updated_at: string;
}

export const projectStateApi = {
  get: (projectId: string) => api<ProjectState>(`/projects/${projectId}/state`),
};
