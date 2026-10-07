export type SourceStatus = "lancar" | "terlambat" | "gagal" | "belum";

export interface SourceCard {
  code: string;
  name: string;
  description: string;
  status: SourceStatus;
  last_sync_at: string | null;
  last_message: string | null;
  records_today: number;
}

export interface SyncRun {
  id: number;
  source_code: string;
  source_name?: string;
  started_at: string;
  finished_at: string | null;
  records_in: number;
  records_new: number;
  status: string;
  message: string;
}

export interface Rule {
  rule: string;
  label: string;
  severity: "tinggi" | "sedang" | "rendah";
  why: string;
  fix: string;
  count: number;
}

export interface Overview {
  hospital: { name: string; city: string; note: string };
  now: string;
  sources: SourceCard[];
  totals: {
    patients: number;
    local_records: number;
    auto_linked: number;
    pending_duplicates: number;
    unmapped_codes: number;
    open_alerts: number;
    quality_score: number;
    issues: number;
  };
  top_problems: Rule[];
  activity: SyncRun[];
  live: LiveState;
}

export interface LiveState {
  enabled: boolean;
  interval_sec: number;
}

export interface SourceDetail extends SourceCard {
  method: string;
  method_label: string;
  interval_min: number;
  last_status: string | null;
  outage: boolean;
  patients: number;
  events: number;
  runs: SyncRun[];
}

export interface Identity {
  name: string;
  sex: "L" | "P" | null;
  birth_date: string | null;
  age: number | null;
  nik: string | null;
  has_nik: boolean;
  phone: string | null;
  address: string | null;
}

export interface PatientListItem extends Identity {
  id: number;
  label: string;
  sources: string[];
  last_activity: string | null;
  pending_duplicates: number;
}

export interface LocalRecord {
  id: number;
  source: string;
  source_name: string;
  local_id: string;
  name: string;
  birth_date_raw: string | null;
  birth_date: string | null;
  sex: string | null;
  nik: string | null;
  phone: string | null;
  address: string | null;
  golden_id: number;
  golden_label: string;
  linked_by: "otomatis" | "petugas" | "baru" | null;
  events: Record<string, number>;
}

export type EventKind = "visit" | "diagnosis" | "lab" | "medication" | "charge";

export interface TimelineItem {
  id: number;
  kind: EventKind;
  kind_label: string;
  occurred_at: string;
  title: string;
  detail: string | null;
  source: string;
  source_name: string;
  local_code: string | null;
  std_code: string | null;
  std_text: string | null;
  std_system: string | null;
  value: string | null;
  unit: string | null;
  ref_range: string | null;
  flag: string | null;
  amount: number | null;
}

export interface Issue {
  rule: string;
  label: string;
  severity: Rule["severity"];
  source: string;
  source_name: string;
  ref: string;
  patient: string | null;
  detail: string;
  golden_id: number | null;
  golden_label?: string | null;
  fix?: string;
}

export interface PatientDetail {
  id: number;
  label: string;
  identity: Identity;
  records: LocalRecord[];
  name_variants: string[];
  summary: {
    visits: number;
    last_visit: string | null;
    diagnoses: { code: string | null; local_code: string; text: string; last_seen: string }[];
    latest_labs: TimelineItem[];
    medications: TimelineItem[];
    total_charges: number;
  };
  pending_duplicates: number[];
  alerts: ClinicalAlert[];
  issues: Issue[];
  timeline: TimelineItem[];
  redirect_to?: number;
}

export interface Reason {
  field: string;
  label: string;
  result: string;
  weight?: number;
  similarity?: number;
}

export interface Candidate {
  id: number;
  score: number;
  status: "pending" | "merged" | "rejected";
  decided_by: string | null;
  decided_at: string | null;
  reasons: Reason[];
  a: LocalRecord;
  b: LocalRecord;
}

export interface Mapping {
  id: number;
  system: "dx" | "lab" | "obat";
  system_label: string;
  standard: string;
  local_code: string;
  local_text: string | null;
  std_code: string | null;
  std_text: string | null;
  status: "suggested" | "unmapped" | "confirmed";
  suggested_by: string | null;
  confirmed_by: string | null;
  confirmed_at: string | null;
  usage: number;
  patients: number;
  source_names: string[];
}

export interface QualityReport {
  score: number;
  records: number;
  records_with_issues: number;
  issues: number;
  sources: {
    code: string;
    name: string;
    records: number;
    records_with_issues: number;
    score: number;
    top_rules: { rule: string; label: string; count: number }[];
  }[];
  rules: Rule[];
}

export interface AlertEvidence {
  event_id: number;
  source: string;
  source_name: string;
  kind: EventKind;
  title: string;
  detail: string | null;
  code: string | null;
  value: string | null;
  unit: string | null;
  flag: string | null;
  occurred_at: string;
}

export type AlertStatus = "open" | "handled" | "resolved";

export interface ClinicalAlert {
  id: number;
  golden_id: number;
  golden_label: string;
  patient: Identity | null;
  rule: string;
  title: string;
  severity: "tinggi" | "sedang";
  sources: string[];
  detail: string;
  evidence: AlertEvidence[];
  status: AlertStatus;
  created_at: string;
  resolved_at: string | null;
  handled_by: string | null;
  handled_at: string | null;
  note: string | null;
}

export interface AlertRule {
  code: string;
  title: string;
  description: string;
  severity: "tinggi" | "sedang";
  sources: string[];
  enabled: boolean;
  open_count: number;
}

export class ApiError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError("Server Simpul tidak bisa dihubungi. Pastikan backend sudah dijalankan.");
  }
  if (!res.ok) {
    let message = `Terjadi kesalahan (${res.status}).`;
    try {
      const body = await res.json();
      if (body?.detail) message = typeof body.detail === "string" ? body.detail : message;
    } catch {
      /* keep default message */
    }
    throw new ApiError(message);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

export interface SyncResult {
  source: string;
  status: string;
  message: string;
  records_new: number;
}

export const api = {
  overview: () => request<Overview>("/overview"),
  sources: () => request<{ sources: SourceDetail[]; live: LiveState }>("/sources"),
  syncNow: (code: string) => post<SyncResult>(`/sources/${code}/sync`),
  setOutage: (code: string, on: boolean) => post<SyncResult>(`/sources/${code}/outage`, { on }),
  uploadFarmasi: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<SyncResult>("/sources/farmasi/upload", { method: "POST", body: form });
  },
  sendLab: () => post<SyncResult & { patient: string; tests: string[] }>("/demo/lab-message"),
  setLive: (enabled: boolean) => post<LiveState>("/demo/live", { enabled }),
  resetDemo: () => post<Record<string, SyncResult>>("/demo/reset"),
  patients: (q: string) =>
    request<{ query: string; results: PatientListItem[] }>(`/patients?q=${encodeURIComponent(q)}`),
  patient: (id: number) => request<PatientDetail>(`/patients/${id}`),
  candidates: (status: "pending" | "decided") =>
    request<{ counts: { pending: number; decided: number }; items: Candidate[] }>(
      `/mpi/candidates?status=${status}`,
    ),
  merge: (id: number) =>
    post<{ golden_id: number; new_alerts: { rule: string }[] }>(`/mpi/candidates/${id}/merge`),
  reject: (id: number) => post<{ ok: boolean }>(`/mpi/candidates/${id}/reject`),
  undo: (id: number) => post<{ ok: boolean }>(`/mpi/candidates/${id}/undo`),
  mappings: (status: "todo" | "done") =>
    request<{ counts: { todo: number; done: number }; items: Mapping[] }>(`/mappings?status=${status}`),
  catalog: (system: string, q: string) =>
    request<{ items: { code: string; text: string }[] }>(
      `/mappings/catalog?system=${system}&q=${encodeURIComponent(q)}`,
    ),
  confirmMapping: (id: number, std_code: string) =>
    post<{ ok: boolean; new_alerts: number; resolved_alerts: number }>(`/mappings/${id}/confirm`, { std_code }),
  resetMapping: (id: number) => post<{ ok: boolean }>(`/mappings/${id}/reset`),
  alerts: (status: AlertStatus) =>
    request<{ counts: Record<AlertStatus, number>; items: ClinicalAlert[] }>(`/alerts?status=${status}`),
  alertRules: () => request<{ items: AlertRule[] }>("/alerts/rules"),
  toggleRule: (code: string, enabled: boolean) =>
    post<{ ok: boolean; new_alerts: number; resolved_alerts: number }>(`/alerts/rules/${code}`, { enabled }),
  handleAlert: (id: number, note: string) => post<{ ok: boolean }>(`/alerts/${id}/handle`, { note }),
  reopenAlert: (id: number) => post<{ ok: boolean }>(`/alerts/${id}/reopen`),
  quality: () => request<QualityReport>("/quality"),
  issues: (rule?: string, source?: string) => {
    const params = new URLSearchParams();
    if (rule) params.set("rule", rule);
    if (source) params.set("source", source);
    params.set("limit", "200");
    return request<{ total: number; items: Issue[] }>(`/quality/issues?${params}`);
  },
  issuesCsvUrl: (rule?: string) => `/api/quality/issues.csv${rule ? `?rule=${rule}` : ""}`,
  sampleFarmasiUrl: "/api/demo/sample-farmasi.csv",
};
