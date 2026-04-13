export class ApiError extends Error {
  status: number;
  code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

type Envelope<T> = {
  ok: boolean;
  code: string;
  message: string;
  data: T;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
  });

  const envelope = (await response.json()) as Envelope<T>;
  if (!response.ok || !envelope.ok) {
    throw new ApiError(envelope.message, response.status, envelope.code);
  }
  return envelope.data;
}

export const api = {
  me: () => request<{ user: { id: string; display_name: string; email: string } }>("/api/auth/me"),
  login: (payload: { email: string; password: string }) =>
    request<{ user: { id: string; display_name: string; email: string } }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  register: (payload: { displayName: string; email: string; password: string; inviteToken: string }) =>
    request<{ user: { id: string; display_name: string; email: string } }>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({
        display_name: payload.displayName,
        email: payload.email,
        password: payload.password,
        invite_token: payload.inviteToken
      })
    }),
  verifyInvite: (invite_token: string) =>
    request<{ valid: boolean; note?: string; expires_at?: string; remaining_uses?: number }>("/api/auth/invite/verify", {
      method: "POST",
      body: JSON.stringify({ invite_token })
    }),
  logout: () => request<null>("/api/auth/logout", { method: "POST" }),
  getPortal: () =>
    request<{
      is_bound: boolean;
      portal_username?: string | null;
      last_successful_login_at?: string | null;
      last_schedule_refresh_at?: string | null;
      last_grade_check_at?: string | null;
      last_failure_message?: string | null;
      has_reusable_cookie: boolean;
    }>("/api/account/portal"),
  savePortal: (payload: { portalUsername: string; portalPassword: string }) =>
    request("/api/account/portal", {
      method: "POST",
      body: JSON.stringify({
        portal_username: payload.portalUsername,
        portal_password: payload.portalPassword
      })
    }),
  getSchedule: (term?: string) => request<SchedulePayload>(`/api/schedule${term ? `?term=${encodeURIComponent(term)}` : ""}`),
  refreshSchedule: (term?: string) =>
    request(`/api/schedule/refresh${term ? `?term=${encodeURIComponent(term)}` : ""}`, { method: "POST" }),
  getGrades: () => request<GradesPayload>("/api/grades"),
  checkGrades: () => request("/api/grades/check-now", { method: "POST" }),
  getSettings: () =>
    request<{
      email_notifications_enabled: boolean;
      notification_email: string;
      login_email: string;
      display_name: string;
    }>("/api/settings"),
  saveSettings: (payload: { emailNotificationsEnabled: boolean; notificationEmail: string }) =>
    request("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        email_notifications_enabled: payload.emailNotificationsEnabled,
        notification_email: payload.notificationEmail
      })
    })
};

export type ScheduleEntry = {
  id: string;
  course_code?: string | null;
  class_no?: string | null;
  course_name: string;
  teacher?: string | null;
  weekday: number;
  weekday_label: string;
  block_start: number;
  block_end: number;
  block_label_start: string;
  block_label_end: string;
  time_text: string;
  week_text: string;
  week_numbers: number[];
  location?: string | null;
  credit?: string | null;
  course_attribute?: string | null;
  selection_stage?: string | null;
};

export type SchedulePayload = {
  term?: string | null;
  available_terms: string[];
  last_refreshed_at?: string | null;
  total_entries: number;
  entries: ScheduleEntry[];
  weeks: Array<{
    week_number: number;
    days: Array<{
      weekday: number;
      weekday_label: string;
      items: ScheduleEntry[];
    }>;
  }>;
};

export type GradesPayload = {
  last_checked_at?: string | null;
  notification_email?: string | null;
  email_notifications_enabled: boolean;
  terms: Array<{
    term: string;
    items: Array<{
      id: string;
      term: string;
      course_code?: string | null;
      course_name: string;
      score?: string | null;
      score_numeric?: number | null;
      score_flag?: string | null;
      grade_point_text?: string | null;
      credit?: string | null;
      total_hours?: string | null;
      assessment_method?: string | null;
      course_attribute?: string | null;
      course_nature?: string | null;
      last_checked_at: string;
    }>;
  }>;
};
