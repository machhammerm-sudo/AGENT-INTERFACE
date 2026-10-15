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

export interface DocCustomer {
  id: number;
  name: string;
  created_at: string;
}

export interface ExtractionFieldDef {
  id: number;
  field_key: string;
  label: string;
  synonyms: string[];
  format_regex: string | null;
  is_user_edited: boolean;
}

export interface PrivacySettings {
  customer_id: number;
  contribute_anonymized_structure_data: boolean;
  consent_given_at: string | null;
  consent_withdrawn_at: string | null;
  allow_cloud_escalation: boolean;
  escalation_consent_at: string | null;
}

export type DocumentStatus = "uploaded" | "processing" | "processed" | "reviewed" | "error";
export type FieldStatus = "green" | "yellow" | "red";

export interface PlanDocument {
  id: number;
  customer_id: number | null;
  filename: string;
  status: DocumentStatus;
  matched_pattern_id: number | null;
  error_message: string | null;
  uploaded_at: string;
  processed_at: string | null;
}

export interface FieldCandidate {
  value: string;
  assignment_confidence: number;
  ocr_confidence: number;
  match_type: string;
  label_score: number;
  rel_bbox: number[];
}

export interface DocFieldResult {
  id: number;
  field_key: string;
  label: string;
  status: FieldStatus;
  chosen_value: string | null;
  chosen_source: string | null;
  assignment_confidence: number | null;
  ocr_confidence: number | null;
  candidates: FieldCandidate[];
  reviewed: boolean;
  human_action: "confirmed" | "corrected" | null;
  corrected_value: string | null;
  reviewed_at: string | null;
}

export interface DocRegion {
  id: number;
  rel_x: number;
  rel_y: number;
  rel_w: number;
  rel_h: number;
  rotation: number;
  score: number;
  method: string;
  is_chosen: boolean;
}

export interface DocumentDetail {
  document: PlanDocument;
  regions: DocRegion[];
  fields: DocFieldResult[];
}

export interface LiveMetrics {
  overall_correct_rate: number;
  overall_n: number;
  per_field: Record<string, { correct_rate: number; n: number }>;
  per_pattern: Record<string, { correct_rate: number; n: number }>;
  estimated_undetected_error_rate: number | null;
  estimated_undetected_n: number;
}

export interface WeeklyHistoryPoint {
  week: string;
  correct_rate: number;
  n: number;
}

export interface SampleCheck {
  id: number;
  document_id: number;
  field_key: string;
  sampled_at: string;
  human_verdict: string | null;
  reviewed_at: string | null;
}

export interface BenchmarkRun {
  id: number;
  run_at: string;
  overall_hit_rate: number;
  false_green_rate: number;
  no_result_rate: number;
  plan_count: number;
  per_field: Record<string, { hit_rate: number; false_green_rate: number; no_result_rate: number; n: number }>;
  per_template: Record<string, { hit_rate: number; false_green_rate: number; no_result_rate: number; n: number }>;
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
  documents: {
    customers: {
      list: () => request<DocCustomer[]>("/documents/customers"),
      create: (name: string) =>
        request<DocCustomer>("/documents/customers", { method: "POST", body: JSON.stringify({ name }) }),
    },
    fields: {
      list: () => request<ExtractionFieldDef[]>("/documents/fields"),
      update: (id: number, data: { label?: string; synonyms?: string[]; format_regex?: string | null }) =>
        request<ExtractionFieldDef>(`/documents/fields/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    },
    privacy: {
      get: (customerId: number) => request<PrivacySettings>(`/documents/privacy/${customerId}`),
      update: (customerId: number, data: Partial<Pick<PrivacySettings, "contribute_anonymized_structure_data" | "allow_cloud_escalation">>) =>
        request<PrivacySettings>(`/documents/privacy/${customerId}`, { method: "PATCH", body: JSON.stringify(data) }),
    },
    list: (customerId?: number) =>
      request<PlanDocument[]>(`/documents${customerId ? `?customer_id=${customerId}` : ""}`),
    upload: async (file: File, customerId: number | null) => {
      const form = new FormData();
      form.append("file", file);
      const qs = customerId ? `?customer_id=${customerId}` : "";
      return request<DocumentDetail>(`/documents/upload${qs}`, { method: "POST", body: form });
    },
    get: (documentId: number) => request<DocumentDetail>(`/documents/${documentId}`),
    regionImageUrl: (documentId: number) => `/api/documents/${documentId}/region-image`,
    fieldCropUrl: (documentId: number, fieldKey: string) =>
      `/api/documents/${documentId}/fields/${fieldKey}/crop`,
    reviewField: (
      documentId: number,
      fieldKey: string,
      data: { action: "confirm" | "correct"; candidate_index?: number; corrected_value?: string }
    ) =>
      request<DocFieldResult>(`/documents/${documentId}/fields/${fieldKey}/review`, {
        method: "POST",
        body: JSON.stringify(data),
      }),
    metrics: {
      get: (customerId?: number, sinceDays?: number) => {
        const params = new URLSearchParams();
        if (customerId != null) params.set("customer_id", String(customerId));
        if (sinceDays != null) params.set("since_days", String(sinceDays));
        const qs = params.toString();
        return request<LiveMetrics>(`/documents/metrics${qs ? `?${qs}` : ""}`);
      },
      history: (customerId?: number, weeks = 12) => {
        const params = new URLSearchParams({ weeks: String(weeks) });
        if (customerId != null) params.set("customer_id", String(customerId));
        return request<WeeklyHistoryPoint[]>(`/documents/metrics/history?${params.toString()}`);
      },
    },
    sampleChecks: {
      list: (customerId?: number) =>
        request<SampleCheck[]>(`/documents/sample-checks${customerId != null ? `?customer_id=${customerId}` : ""}`),
      resolve: (id: number, verdict: "correct" | "incorrect") =>
        request<SampleCheck>(`/documents/sample-checks/${id}/resolve`, {
          method: "POST",
          body: JSON.stringify({ verdict }),
        }),
    },
    benchmark: {
      history: () => request<BenchmarkRun[]>("/documents/benchmark/history"),
      run: () => request<BenchmarkRun>("/documents/benchmark/run", { method: "POST" }),
    },
  },
};
