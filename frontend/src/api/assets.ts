import { api } from "./client";

export type AssetKind = "video" | "audio" | "image";
export type UploadStatus = "pending" | "uploaded" | "failed";

export interface Asset {
  id: string;
  user_id: string;
  project_id: string | null;
  filename: string;
  mime_type: string;
  kind: AssetKind;
  size_bytes: number;
  duration_sec: number | null;
  width: number | null;
  height: number | null;
  storage_type: string;
  s3_bucket: string;
  s3_key: string;
  s3_url: string | null;
  upload_status: UploadStatus;
  is_watermarked: boolean;
  language: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface PresignResp {
  asset_id: string;
  upload_url: string;
  upload_headers: Record<string, string>;
  s3_key: string;
  expires_at: string;
}

export interface AssetListResp {
  items: Asset[];
  next_cursor: string | null;
  has_more: boolean;
}

export const assetsApi = {
  presign: (body: {
    filename: string;
    mime_type: string;
    kind: AssetKind;
    size_bytes: number;
    project_id?: string;
    tags?: string[];
  }) => api<PresignResp>("/assets/presign-upload", { method: "POST", body }),
  confirm: (
    id: string,
    body: { duration_sec?: number; width?: number; height?: number } = {},
  ) => api<Asset>(`/assets/${id}/confirm`, { method: "POST", body }),
  list: (opts: { kind?: AssetKind; project_id?: string; q?: string; tag?: string } = {}) => {
    const qs = new URLSearchParams();
    if (opts.kind) qs.set("kind", opts.kind);
    if (opts.project_id) qs.set("project_id", opts.project_id);
    if (opts.q) qs.set("q", opts.q);
    if (opts.tag) qs.set("tag", opts.tag);
    const s = qs.toString();
    return api<AssetListResp>(`/assets${s ? `?${s}` : ""}`);
  },
  get: (id: string) => api<Asset>(`/assets/${id}`),
  update: (id: string, body: { filename?: string; tags?: string[] }) =>
    api<Asset>(`/assets/${id}`, { method: "PATCH", body }),
  remove: (id: string) => api<{ ok: true }>(`/assets/${id}`, { method: "DELETE" }),
};

/** Upload a blob/data to the presigned URL. Returns true on success. */
export async function uploadBinary(
  upload_url: string,
  headers: Record<string, string>,
  data: Blob | ArrayBuffer | Uint8Array,
): Promise<boolean> {
  const r = await fetch(upload_url, {
    method: "PUT",
    headers,
    // Cast: fetch supports all three runtime types.
    body: data as BodyInit,
  });
  return r.ok;
}
