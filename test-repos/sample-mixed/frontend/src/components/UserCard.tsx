import React from "react";

interface User {
  id: string;
  email: string;
  role: string;
}

interface Props {
  user: User;
  onDelete?: (id: string) => void;
}

export function UserCard({ user, onDelete }: Props) {
  function handleDelete() {
    if (confirmDelete(user.email)) {
      onDelete?.(user.id);
    }
  }

  function confirmDelete(email: string): boolean {
    return window.confirm(`Delete ${email}?`);
  }

  function formatRole(role: string): string {
    return role.charAt(0).toUpperCase() + role.slice(1);
  }

  return (
    <div className="user-card">
      <span className="email">{user.email}</span>
      <span className="role">{formatRole(user.role)}</span>
      {onDelete && (
        <button onClick={handleDelete} className="delete-btn">
          Remove
        </button>
      )}
    </div>
  );
}
