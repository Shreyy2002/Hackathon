import axios from "axios";
import type { User } from "../store/userStore";

/**
 * Axios instance for all API calls.
 * - baseURL "/api" maps to the Vite proxy → http://backend:8000/api
 * - withCredentials ensures the session cookie (X-Current-User) is sent on
 *   every request and can be set by the server via Set-Cookie.
 */
const apiClient = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// --------------------------------------------------------------------------
// Auth / Identity
// --------------------------------------------------------------------------

/**
 * Switch the active persona.
 * POST /api/auth/switch-role  →  sets X-Current-User session cookie
 */
export async function switchRole(userId: string): Promise<User> {
  const response = await apiClient.post<User>("/auth/switch-role", {
    user_id: userId,
  });
  return response.data;
}

// --------------------------------------------------------------------------
// Employee Profile
// --------------------------------------------------------------------------

export interface EmployeeProfile {
  user: User;
  goals: unknown[];
  recent_events: unknown[];
}

/**
 * Fetch an employee's profile — user record + goals + 20 most recent events.
 * GET /api/employees/{id}/profile
 */
export async function getEmployeeProfile(id: string): Promise<EmployeeProfile> {
  const response = await apiClient.get<EmployeeProfile>(
    `/employees/${id}/profile`
  );
  return response.data;
}

// --------------------------------------------------------------------------
// Timeline
// --------------------------------------------------------------------------

export interface TimelineEvent {
  id: string
  employee_id: string
  actor_id: string
  event_type: string
  payload: Record<string, unknown>
  linked_goal_id: string | null
  created_at: string
  is_evidence: boolean
}

/**
 * Fetch paginated, filterable timeline events.
 * GET /api/timeline/events
 */
export async function getTimelineEvents(params: {
  employee_id: string
  offset?: number
  limit?: number
  event_type?: string
}): Promise<TimelineEvent[]> {
  const response = await apiClient.get<TimelineEvent[]>('/timeline/events', { params })
  return response.data
}

export default apiClient;
