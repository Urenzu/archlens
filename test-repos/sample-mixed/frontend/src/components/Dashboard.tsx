import React, { useEffect, useState } from "react";
import { UserCard } from "./UserCard";
import { useAuth } from "../hooks/useAuth";

interface User {
  id: string;
  email: string;
  role: string;
}

export function Dashboard() {
  const { session, logout } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchUsers().then((data) => {
      setUsers(data);
      setLoading(false);
    });
  }, []);

  async function fetchUsers(): Promise<User[]> {
    const res = await fetch("/users", {
      headers: buildAuthHeader(session?.token ?? ""),
    });
    return res.json();
  }

  function buildAuthHeader(token: string): Record<string, string> {
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function handleLogout() {
    logout();
    redirectToLogin();
  }

  function redirectToLogin() {
    window.location.href = "/login";
  }

  if (loading) return <div>Loading...</div>;

  return (
    <div className="dashboard">
      <header>
        <h1>Dashboard</h1>
        <button onClick={handleLogout}>Logout</button>
      </header>
      <main>
        {users.map((u) => (
          <UserCard key={u.id} user={u} />
        ))}
      </main>
    </div>
  );
}
