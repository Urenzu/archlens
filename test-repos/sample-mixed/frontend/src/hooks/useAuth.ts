import { useState, useEffect, useCallback } from "react";

interface Session {
  token: string;
  email: string;
  role: string;
}

export function useAuth() {
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    const stored = loadSession();
    if (stored) setSession(stored);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const token = await requestToken(email, password);
    const s = buildSession(token, email);
    saveSession(s);
    setSession(s);
    return s;
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
  }, []);

  return { session, login, logout };
}

async function requestToken(email: string, password: string): Promise<string> {
  const res = await fetch("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await res.json();
  return data.token;
}

function buildSession(token: string, email: string): Session {
  return { token, email, role: parseRole(token) };
}

function parseRole(token: string): string {
  try {
    const payload = JSON.parse(atob(token));
    return payload.role ?? "user";
  } catch {
    return "user";
  }
}

function saveSession(session: Session) {
  localStorage.setItem("session", JSON.stringify(session));
}

function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem("session");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function clearSession() {
  localStorage.removeItem("session");
}
