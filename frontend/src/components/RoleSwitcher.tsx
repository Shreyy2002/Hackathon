import React, { useState } from "react";
import { switchRole } from "../api/client";
import { useUserStore } from "../store/userStore";
import type { User } from "../store/userStore";

/**
 * Hardcoded demo personas.
 * UUIDs must match the seed script (task 1.5).
 * Riya  = Manager  (11111111-…)
 * Alex  = Employee (22222222-…)
 * HR Admin           (33333333-…)
 */
const HARDCODED_USERS: Array<{ label: string; id: string; role: User["role"] }> =
  [
    {
      label: "Riya (Manager)",
      id: "11111111-1111-1111-1111-111111111111",
      role: "manager",
    },
    {
      label: "Alex (Employee)",
      id: "22222222-2222-2222-2222-222222222222",
      role: "employee",
    },
    {
      label: "HR Admin",
      id: "33333333-3333-3333-3333-333333333333",
      role: "hr",
    },
  ];

export default function RoleSwitcher() {
  const setUser = useUserStore((s) => s.setUser);
  const currentUser = useUserStore((s) => s.currentUser);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const userId = event.target.value;
    if (!userId) return;

    setLoading(true);
    setError(null);

    try {
      const user = await switchRole(userId);
      setUser(user);
    } catch (err) {
      setError("Failed to switch role. Is the backend running?");
      console.error("switchRole error:", err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-3">
      <label
        htmlFor="role-switcher"
        className="text-sm font-medium text-gray-700"
      >
        Viewing as:
      </label>

      <select
        id="role-switcher"
        onChange={handleChange}
        value={currentUser?.id ?? ""}
        disabled={loading}
        className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm shadow-sm
                   focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500
                   disabled:cursor-not-allowed disabled:opacity-50"
      >
        <option value="" disabled>
          Select persona…
        </option>
        {HARDCODED_USERS.map((u) => (
          <option key={u.id} value={u.id}>
            {u.label}
          </option>
        ))}
      </select>

      {loading && (
        <span className="text-xs text-gray-500" aria-live="polite">
          Switching…
        </span>
      )}

      {error && (
        <span className="text-xs text-red-600" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
