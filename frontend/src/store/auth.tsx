/** Global auth context provider. */
import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { authApi, UserPublic } from "@/src/api/auth";
import { clearTokens, setTokens } from "@/src/api/client";
import { storage } from "@/src/utils/storage";

const REFRESH_KEY = "shortcut.refresh_token";

type AuthState = {
  user: UserPublic | null;
  loading: boolean;
};

type AuthContextValue = AuthState & {
  signin: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, name: string) => Promise<void>;
  google: (session_token: string) => Promise<void>;
  signout: () => Promise<void>;
  refreshMe: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true });

  const bootstrap = useCallback(async () => {
    try {
      const user = await authApi.me();
      setState({ user, loading: false });
    } catch {
      setState({ user: null, loading: false });
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const finishAuth = useCallback(
    async (resp: { user: UserPublic; access_token: string; refresh_token: string }) => {
      await setTokens(resp.access_token, resp.refresh_token);
      setState({ user: resp.user, loading: false });
    },
    [],
  );

  const signin: AuthContextValue["signin"] = useCallback(
    async (email, password) => {
      const r = await authApi.login(email, password);
      await finishAuth(r);
    },
    [finishAuth],
  );

  const signup: AuthContextValue["signup"] = useCallback(
    async (email, password, name) => {
      const r = await authApi.signup(email, password, name);
      await finishAuth(r);
    },
    [finishAuth],
  );

  const google: AuthContextValue["google"] = useCallback(
    async (session_token) => {
      const r = await authApi.google(session_token);
      await finishAuth(r);
    },
    [finishAuth],
  );

  const signout: AuthContextValue["signout"] = useCallback(async () => {
    try {
      const refresh = await storage.secureGet(REFRESH_KEY, null as string | null);
      if (refresh) await authApi.logout(refresh).catch(() => null);
    } catch {
      // ignore
    }
    await clearTokens();
    setState({ user: null, loading: false });
  }, []);

  const refreshMe = useCallback(async () => {
    try {
      const user = await authApi.me();
      setState((s) => ({ ...s, user }));
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ ...state, signin, signup, google, signout, refreshMe }),
    [state, signin, signup, google, signout, refreshMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
