"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getApiBase } from "./api";
import { extractApiErrorMessage, parseResponseBodyLoose } from "./api-error";
import { apiFetch } from "./apiClient";
import type { AuthUser } from "@/types/api";

const TOKEN_KEY = "advise_workbench_token";
const REFRESH_KEY = "advise_workbench_refresh";
const EMAIL_KEY = "advise_workbench_email";

type AuthContextValue = {
  token: string | null;
  email: string | null;
  user: AuthUser | null;
  setUser: (user: AuthUser | null) => void;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithMicrosoftCode: (code: string) => Promise<string>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  api: (path: string, init?: RequestInit) => Promise<Response>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    // We intentionally hydrate auth state from localStorage after mount.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setToken(localStorage.getItem(TOKEN_KEY));
    setEmail(localStorage.getItem(EMAIL_KEY));
    setReady(true);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(EMAIL_KEY);
    setToken(null);
    setEmail(null);
    setUser(null);
  }, []);

  const refreshAccessToken = useCallback(async (): Promise<string | null> => {
    const rt = typeof window !== "undefined" ? localStorage.getItem(REFRESH_KEY) : null;
    if (!rt) return null;
    const base = getApiBase();
    const res = await apiFetch(`${base}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return null;
    const { data: parsed } = await parseResponseBodyLoose(res);
    const data = (parsed && typeof parsed === "object" ? parsed : {}) as { access_token?: string; refresh_token?: string };
    if (!data.access_token) return null;
    localStorage.setItem(TOKEN_KEY, data.access_token);
    if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
    setToken(data.access_token);
    return data.access_token;
  }, []);

  const login = useCallback(async (userEmail: string, password: string) => {
    const base = getApiBase();
    const res = await apiFetch(`${base}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: userEmail, password }),
    });
    const { data: parsed, rawText } = await parseResponseBodyLoose(res);
    const data = (parsed && typeof parsed === "object" ? parsed : {}) as {
      access_token?: string;
      refresh_token?: string;
      detail?: string;
    };
    if (!res.ok) {
      throw new Error(extractApiErrorMessage(data, rawText || `Login failed (${res.status})`));
    }
    if (!data.access_token) throw new Error("No access token");
    localStorage.setItem(TOKEN_KEY, data.access_token);
    if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
    localStorage.setItem(EMAIL_KEY, userEmail);
    setToken(data.access_token);
    setEmail(userEmail);
  }, []);

  const loginWithMicrosoftCode = useCallback(async (code: string) => {
    const res = await apiFetch(`${getApiBase()}/api/auth/microsoft/exchange`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const { data: parsed, rawText } = await parseResponseBodyLoose(res);
    const data = (parsed && typeof parsed === "object" ? parsed : {}) as {
      access_token?: string;
      refresh_token?: string;
      email?: string;
      next?: string;
      detail?: string;
    };
    if (!res.ok) {
      throw new Error(extractApiErrorMessage(data, rawText || `Microsoft sign-in failed (${res.status})`));
    }
    if (!data.access_token || !data.email) throw new Error("Microsoft sign-in did not return a valid session");
    localStorage.setItem(TOKEN_KEY, data.access_token);
    if (data.refresh_token) localStorage.setItem(REFRESH_KEY, data.refresh_token);
    localStorage.setItem(EMAIL_KEY, data.email);
    setToken(data.access_token);
    setEmail(data.email);
    return data.next || "/engagements";
  }, []);

  const register = useCallback(
    async (
      userEmail: string,
      password: string,
      fullName: string,
    ) => {
      await login(userEmail, password);
      const accessToken = localStorage.getItem(TOKEN_KEY);
      if (!accessToken) throw new Error("Account created, but the session could not be started.");

      const res = await apiFetch(`${getApiBase()}/api/auth/me`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ full_name: fullName }),
      });
      const { data: parsed, rawText } = await parseResponseBodyLoose(res);
      if (!res.ok) {
        throw new Error(extractApiErrorMessage(parsed, rawText || "Unable to save your profile."));
      }
      setUser((parsed && typeof parsed === "object" ? parsed : null) as AuthUser | null);
    },
    [login]
  );

  const api = useCallback(
    async (path: string, init?: RequestInit) => {
      const base = getApiBase();
      const doFetch = (access: string | null) => {
        const headers = new Headers(init?.headers);
        if (access) headers.set("Authorization", `Bearer ${access}`);
        const isFormData =
          typeof FormData !== "undefined" && init?.body instanceof FormData;
        if (!headers.has("Content-Type") && init?.body && !isFormData) {
          headers.set("Content-Type", "application/json");
        }
        return apiFetch(`${base}${path.startsWith("/") ? path : `/${path}`}`, { ...init, headers });
      };
      let res = await doFetch(token);
      if (res.status === 401) {
        const newAccess = await refreshAccessToken();
        if (newAccess) res = await doFetch(newAccess);
      }
      return res;
    },
    [token, refreshAccessToken]
  );

  // Load the signed-in user's profile (name, title, admin flag) whenever the session changes.
  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    void api("/api/auth/me")
      .then(async (res) => (res.ok ? ((await res.json()) as AuthUser) : null))
      .then((profile) => {
        if (!cancelled) setUser(profile);
      })
      .catch(() => {
        if (!cancelled) setUser(null);
      });
    return () => {
      cancelled = true;
    };
    // `api` changes identity with the token; the token is the real dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const value = useMemo(
    () => ({ token, email, user, setUser, ready, login, loginWithMicrosoftCode, register, logout, api }),
    [token, email, user, ready, login, loginWithMicrosoftCode, register, logout, api]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
