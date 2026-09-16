import { api } from "./client";

export type TrackKind = "video" | "overlay" | "audio" | "caption";

export interface TransformKeyframe {
  at: number;
  scale: number;
  position_x: number;
  position_y: number;
  easing: "linear" | "ease_in" | "ease_out" | "ease_in_out";
}

export interface ClipTransform {
  scale: number;
  position_x: number;
  position_y: number;
  rotation_deg: number;
  opacity: number;
  keyframes: TransformKeyframe[];
}

export interface ProjectClip {
  id: string;
  asset_id: string;
  timeline_start: number;
  duration: number;
  source_start: number;
  source_duration: number;
  playback_rate: number;
  volume: number;
  enabled?: boolean;
  transform?: ClipTransform;
  transition_in?: Record<string, any> | null;
  transition_out?: Record<string, any> | null;
  ducking?: Record<string, any> | null;
  metadata: Record<string, any>;
}

export interface ProjectCaptionCue {
  id: string;
  start: number;
  duration: number;
  text: string;
  style: Record<string, any>;
}

export interface ProjectTrack {
  id: string;
  kind: TrackKind;
  name: string;
  locked: boolean;
  muted: boolean;
  clips: ProjectClip[];
}

export interface ProjectSequence {
  id: string;
  name: string;
  width: number;
  height: number;
  timebase: { numerator: number; denominator: number };
  tracks: ProjectTrack[];
  captions: ProjectCaptionCue[];
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
