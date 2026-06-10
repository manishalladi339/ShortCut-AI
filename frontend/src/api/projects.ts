import { api } from "./client";

export type ContentType =
  | "podcast" | "educational" | "business" | "travel" | "fitness"
  | "comedy" | "dance" | "vlog" | "gaming" | "food"
  | "fashion" | "real_estate" | "events" | "product_ad" | "personal_brand";

export type CreationMode = "create_for_me" | "create_with_me";
export type Style = "cinematic" | "professional" | "emotional" | "funny" | "energetic" | "inspirational" | "luxury";
export type Platform = "ig_reels" | "yt_shorts" | "fb_reels" | "linkedin" | "x";
export type ProjectStatus = "draft" | "processing" | "completed" | "archived" | "failed";

export interface Project {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  content_type: ContentType;
  creation_mode: CreationMode;
  status: ProjectStatus;
  desired_style: Style | null;
  target_platforms: Platform[];
  prompt: string | null;
  primary_asset_id: string | null;
  output_clip_ids: string[];
  output_thumbnail_ids: string[];
  current_ai_job_id: string | null;
  archived: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProjectListResp {
  items: Project[];
  next_cursor: string | null;
  has_more: boolean;
}

export interface ProjectCreatePayload {
  title: string;
  description?: string;
  content_type: ContentType;
  creation_mode: CreationMode;
  desired_style?: Style;
  target_platforms?: Platform[];
  prompt?: string;
}

export const projectsApi = {
  list: (archived = false) => api<ProjectListResp>(`/projects?archived=${archived}`),
  recent: () => api<Project[]>("/projects/recent"),
  continueEditing: () => api<Project[]>("/projects/continue-editing"),
  get: (id: string) => api<Project>(`/projects/${id}`),
  create: (body: ProjectCreatePayload) => api<Project>("/projects", { method: "POST", body }),
  update: (id: string, body: Partial<ProjectCreatePayload>) =>
    api<Project>(`/projects/${id}`, { method: "PATCH", body }),
  archive: (id: string) => api<Project>(`/projects/${id}/archive`, { method: "POST" }),
  duplicate: (id: string) => api<Project>(`/projects/${id}/duplicate`, { method: "POST" }),
  remove: (id: string) => api<{ ok: true }>(`/projects/${id}`, { method: "DELETE" }),
};
