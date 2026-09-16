import { api } from './client';
export type Clip = { id: string; asset_id: string; timeline_start: number; duration: number; source_start: number; source_duration: number; volume: number; playback_rate: number; enabled: boolean };
export type Track = { id: string; name: string; kind: 'video'|'audio'|'overlay'|'caption'; clips: Clip[]; muted: boolean; locked: boolean };
export type Caption = { id: string; start: number; duration: number; text: string };
export type Sequence = { id: string; name: string; width: number; height: number; timebase: {numerator: number; denominator: number}; tracks: Track[]; captions: Caption[] };
export type ProjectState = { project_id: string; version: number; active_sequence_id: string; sequences: Sequence[] };
export type Job = {id: string; status: string; progress: number; error_message?: string; result: Record<string, unknown>};
export type EditPlan = {id: string; status: string; project_state_version: number; narrative_summary: string; caption_suggestion: string; cta_suggestion: string; operations: {id: string; operation: string; reason: string; payload: Record<string, unknown>}[]; evaluation: Record<string, unknown>};
export type Export = {id: string; status: string; job_id: string; project_state_version: number; download_url: string|null; duration_sec: number|null; created_at: string};
export type Version = {version: number; operation: string; created_at: string};
export const editorApi = {
  pipeline: (id:string) => api<Job|null>(`/projects/${id}/pipeline`),
  startPipeline: (id:string, body:Record<string,unknown>) => api<Job>(`/projects/${id}/pipeline`,{method:'POST',body}),
  state: (id: string) => api<ProjectState>(`/projects/${id}/state`),
  edit: (id: string, expected_version: number, operation: string, payload: Record<string, unknown>) => api<ProjectState>(`/projects/${id}/operations`, {method:'POST', body:{expected_version, operation, payload}}),
  replace: (id: string, state: ProjectState) => api<ProjectState>(`/projects/${id}/state`, {method:'PUT', body:{expected_version: state.version, active_sequence_id:state.active_sequence_id, sequences:state.sequences}}),
  versions: (id:string) => api<Version[]>(`/projects/${id}/versions`),
  restore: (id:string, version:number, expected_version:number) => api<ProjectState>(`/projects/${id}/versions/${version}/restore`, {method:'POST',body:{expected_version}}),
  analyze: (id:string) => api<{job_id:string}>(`/assets/${id}/analyze`,{method:'POST',body:{}}),
  intelligence: (id:string) => api<{status:string; transcript_text:string}>(`/assets/${id}/intelligence`),
  job: (id:string) => api<Job>(`/jobs/${id}`),
  plan: (id:string, body:Record<string,unknown>) => api<EditPlan>(`/projects/${id}/ai-plans`,{method:'POST',body}),
  plans: (id:string) => api<EditPlan[]>(`/projects/${id}/ai-plans`),
  apply: (id:string, planId:string, expected_version:number, operation_ids:string[], replace_existing_video_clips:boolean) => api<ProjectState>(`/projects/${id}/ai-plans/${planId}/apply`, {method:'POST',body:{expected_version,operation_ids,replace_existing_video_clips}}),
  export: (id:string) => api<Export>(`/projects/${id}/exports`,{method:'POST',body:{preset:'source'}}),
  exports: (id:string) => api<Export[]>(`/projects/${id}/exports`),
};
