export type AgentStatus = "working" | "waiting_for_user" | "done" | "paused";

export interface Agent {
  id: number;
  name: string;
  role_title: string;
  core_task: string;
  status: AgentStatus;
  is_active: boolean;
  is_restricted: boolean;
  is_builtin: boolean;
  color_accent: string;
  created_at: string;
}

export interface Message {
  id: number;
  agent_id: number;
  role: "user" | "assistant";
  content: string;
  category_id: number | null;
  created_at: string;
}

export interface AgendaItem {
  id: number;
  title: string;
  reason: string;
  is_blocking: boolean;
  is_done: boolean;
  agent_id: number | null;
  category_id: number | null;
  created_at: string;
}

export interface Category {
  id: number;
  key: string;
  name: string;
  description: string;
  is_user_edited: boolean;
}

export type GoalLevel = "month" | "year" | "long_term";
export type GoalStatus = "active" | "achieved" | "missed";

export interface Goal {
  id: number;
  level: GoalLevel;
  title: string;
  why_important: string;
  status: GoalStatus;
  target_date: string | null;
  created_at: string;
}

export interface Achievement {
  id: number;
  title: string;
  description: string;
  time_saved_minutes: number;
  goal_id: number | null;
  achieved_at: string;
}

export interface ContactRequest {
  id: number;
  description: string;
  contact_name: string | null;
  contact_info: string | null;
  status: "open" | "in_progress" | "closed";
  created_at: string;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: options?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Fehler ${res.status}`);
  }
  return res.json();
}

export const api = {
  agents: {
    list: () => request<Agent[]>("/agents"),
    create: (data: { name: string; role_title: string; core_task: string }) =>
      request<Agent>("/agents", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<Pick<Agent, "is_active" | "status" | "core_task" | "role_title">>) =>
      request<Agent>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },
  chat: {
    history: (agentId: number, q?: string) =>
      request<Message[]>(`/agents/${agentId}/history${q ? `?q=${encodeURIComponent(q)}` : ""}`),
    send: (agentId: number, message: string) =>
      request<{ user_message: Message; assistant_message: Message }>(
        `/agents/${agentId}/chat`,
        { method: "POST", body: JSON.stringify({ message }) }
      ),
  },
  agenda: {
    list: () => request<AgendaItem[]>("/agenda"),
    create: (data: { title: string; reason: string; is_blocking?: boolean; agent_id?: number | null }) =>
      request<AgendaItem>("/agenda", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<Pick<AgendaItem, "is_done" | "category_id">>) =>
      request<AgendaItem>(`/agenda/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },
  categories: {
    list: () => request<Category[]>("/categories"),
    update: (id: number, data: { name?: string; description?: string }) =>
      request<Category>(`/categories/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  },
  goals: {
    list: () => request<Goal[]>("/goals"),
    create: (data: { level: GoalLevel; title: string; why_important: string; target_date?: string }) =>
      request<Goal>("/goals", { method: "POST", body: JSON.stringify(data) }),
    update: (id: number, data: Partial<Pick<Goal, "title" | "why_important" | "status" | "target_date">>) =>
      request<Goal>(`/goals/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    remove: (id: number) => request<{ ok: boolean }>(`/goals/${id}`, { method: "DELETE" }),
  },
  achievements: {
    list: () => request<Achievement[]>("/achievements"),
    summary: () =>
      request<{ total_achievements: number; total_time_saved_minutes: number; total_time_saved_hours: number }>(
        "/achievements/summary"
      ),
  },
  contactRequests: {
    list: () => request<ContactRequest[]>("/contact-requests"),
    create: (data: { description: string; contact_name?: string; contact_info?: string }) =>
      request<ContactRequest>("/contact-requests", { method: "POST", body: JSON.stringify(data) }),
  },
};
