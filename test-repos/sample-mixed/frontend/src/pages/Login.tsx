import React, { useState } from "react";
import { useAuth } from "../hooks/useAuth";

export function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validateForm(email, password)) {
      setError("Email and password required");
      return;
    }
    try {
      await login(email, password);
      redirectToDashboard();
    } catch {
      setError("Login failed");
    }
  }

  function validateForm(email: string, password: string): boolean {
    return email.trim().length > 0 && password.length > 0;
  }

  function redirectToDashboard() {
    window.location.href = "/dashboard";
  }

  return (
    <form onSubmit={handleSubmit} className="login-form">
      <h1>Sign in</h1>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      {error && <p className="error">{error}</p>}
      <button type="submit">Login</button>
    </form>
  );
}
