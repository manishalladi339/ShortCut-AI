import { api } from "./client";

export interface UserPublic {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  role: string;
  auth_provider: "email" | "google" | "both";
  subscription_tier: "free" | "creator" | "pro" | "agency";
  onboarding_complete: boolean;
  user_type: string | null;
  niche: string[];
  created_at: string;
}

export interface AuthResponse {
  user: UserPublic;
  access_token: string;
  refresh_token: string;
}

export const authApi = {
  signup: (email: string, password: string, name: string) =>
    api<AuthResponse>("/auth/signup", { method: "POST", body: { email, password, name }, auth: false }),
  login: (email: string, password: string) =>
    api<AuthResponse>("/auth/login", { method: "POST", body: { email, password }, auth: false }),
  google: (session_token: string) =>
    api<AuthResponse>("/auth/google", { method: "POST", body: { session_token }, auth: false }),
  me: () => api<UserPublic>("/auth/me"),
  forgotPassword: (email: string) =>
    api<{ ok: true }>("/auth/forgot-password", { method: "POST", body: { email }, auth: false }),
  resetPassword: (token: string, new_password: string) =>
    api<{ ok: true }>("/auth/reset-password", {
      method: "POST",
      body: { token, new_password },
      auth: false,
    }),
  logout: (refresh_token: string) =>
    api<{ ok: true }>("/auth/logout", { method: "POST", body: { refresh_token } }),
  updateMe: (body: Partial<Pick<UserPublic, "name" | "user_type" | "niche" | "onboarding_complete" | "avatar_url">>) =>
    api<UserPublic>("/users/me", { method: "PATCH", body }),
};
