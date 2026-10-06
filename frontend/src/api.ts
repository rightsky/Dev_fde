// API 클라이언트. 모든 화면은 이 모듈의 함수만 쓴다.
import type * as T from "./types";

const TOKEN_KEY = "fde.token";

export const auth = {
  get token(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null) {
    try {
      if (token) sessionStorage.setItem(TOKEN_KEY, token);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* 저장소를 쓸 수 없으면 메모리에만 둔다 */
    }
    listeners.forEach((fn) => fn());
  },
  onChange(fn: () => void) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  },
};
const listeners = new Set<() => void>();

/** 서버가 돌려준 오류. detail 이 객체인 경우(code·message·reasons)도 그대로 보관한다. */
export class ApiError extends Error {
  status: number;
  code?: string;
  detail?: any;
  constructor(status: number, message: string, code?: string, detail?: any) {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

function errorMessage(status: number, body: any): { message: string; code?: string } {
  const d = body?.detail;
  if (typeof d === "string") return { message: d };
  if (Array.isArray(d)) {
    // FastAPI 검증 오류
    return { message: d.map((e: any) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join(" · ") || `요청 오류 (${status})` };
  }
  if (d && typeof d === "object") return { message: d.message || `요청 오류 (${status})`, code: d.code };
  if (status === 413) return { message: "파일이 너무 큽니다" };
  if (status >= 500) return { message: "서버 오류가 발생했습니다. 잠시 후 다시 시도하세요" };
  return { message: `요청 오류 (${status})` };
}

async function request<R>(method: string, path: string, body?: unknown, params?: Record<string, unknown>): Promise<R> {
  const qs = params
    ? "?" +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const headers: Record<string, string> = {};
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}${qs === "?" ? "" : qs}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "서버에 연결할 수 없습니다");
  }
  if (res.status === 401 && path !== "/auth/login") {
    auth.set(null);
    throw new ApiError(401, "로그인이 만료되었습니다. 다시 로그인하세요");
  }
  const text = await res.text();
  let data: any = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    const { message, code } = errorMessage(res.status, data);
    throw new ApiError(res.status, message, code, data?.detail);
  }
  return data as R;
}

const get = <R>(path: string, params?: Record<string, unknown>) => request<R>("GET", path, undefined, params);
const post = <R>(path: string, body?: unknown) => request<R>("POST", path, body ?? {});
const put = <R>(path: string, body?: unknown) => request<R>("PUT", path, body ?? {});
const patch = <R>(path: string, body?: unknown) => request<R>("PATCH", path, body ?? {});
const del = <R>(path: string) => request<R>("DELETE", path);

/** 인증 헤더가 필요한 파일을 내려받아 저장한다. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(`/api${path}`, { headers: auth.token ? { Authorization: `Bearer ${auth.token}` } : {} });
  if (!res.ok) {
    let body: any = null;
    try {
      body = await res.json();
    } catch {
      /* 본문 없음 */
    }
    throw new ApiError(res.status, errorMessage(res.status, body).message);
  }
  const disp = res.headers.get("content-disposition") || "";
  const m = /filename\*=UTF-8''([^;]+)/i.exec(disp);
  const name = m ? decodeURIComponent(m[1]) : fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export const api = {
  // 인증
  login: (username: string, password: string) => post<{ access_token: string; user: T.User }>("/auth/login", { username, password }),
  me: () => get<T.User>("/auth/me"),
  changePassword: (current_password: string, new_password: string) => post<{ ok: boolean }>("/auth/password", { current_password, new_password }),

  // 참조
  reference: () => get<T.Reference>("/reference"),
  shapes: (mode: "draft" | "publish") => get<{ version: string; mode: string; turtle: string; rules: T.ShapeRule[] }>("/shapes", { mode }),
  orgs: () => get<T.Org[]>("/orgs"),
  createOrg: (body: { code?: string; label: string; note?: string }) => post<T.Org>("/orgs", body),
  updateOrg: (id: number, body: { label: string; note?: string | null; active: boolean }) => patch<T.Org>(`/orgs/${id}`, body),
  taxonomy: () => get<T.TaxAxis[]>("/taxonomy"),
  addTaxCode: (axis: string, body: { label: string; definition?: string }) => post<T.TaxAxis>(`/taxonomy/${axis}/codes`, body),
  updateTaxCode: (id: number, body: { label: string; definition?: string | null; active: boolean }) => patch<T.TaxAxis>(`/taxonomy/codes/${id}`, body),
  users: () => get<T.User[]>("/users"),
  createUser: (body: { username: string; name: string; password: string; role: T.Role; org_label?: string; email?: string }) => post<T.User>("/users", body),
  updateUser: (id: number, body: Partial<{ name: string; role: T.Role; org_label: string; email: string; active: boolean; password: string }>) =>
    patch<T.User>(`/users/${id}`, body),
  activities: (params?: { process_id?: number; limit?: number }) => get<T.Activity[]>("/activities", params),
  mintRegistry: () => get<T.MintRegistry>("/mint-registry"),
  dashboard: () => get<T.Dashboard>("/dashboard"),

  // 원천
  assets: (params?: { kind?: string; q?: string }) => get<T.Asset[]>("/assets", params),
  asset: (id: number) => get<T.Asset>(`/assets/${id}`),
  uploadAssets: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f, f.name));
    return request<{ created: T.Asset[]; rejected: { filename: string; reason: string }[] }>("POST", "/assets/upload", fd);
  },
  registerStream: (body: {
    name: string;
    description?: string;
    org_id?: number | null;
    temporal_resolution?: string;
    event_time_column?: string;
    endpoint_url?: string;
    timezone?: string;
    fields: { name: string; type: string }[];
  }) => post<T.Asset>("/assets/streams", body),
  updateAsset: (id: number, body: { name?: string; description?: string; org_id?: number | null }) => patch<T.Asset>(`/assets/${id}`, body),
  deleteAsset: (id: number) => del<{ ok: boolean }>(`/assets/${id}`),

  // 프로세스
  processes: (status?: "active" | "completed" | "trashed") => get<T.Process[]>("/processes", { status }),
  createProcess: (name?: string) => post<T.ProcessDetail>("/processes", { name }),
  process: (pid: number) => get<T.ProcessDetail>(`/processes/${pid}`),
  updateProcess: (pid: number, body: { name?: string; current_step?: number; pub_mode?: boolean }) => patch<T.ProcessDetail>(`/processes/${pid}`, body),
  completeProcess: (pid: number) => post<T.ProcessDetail>(`/processes/${pid}/complete`),
  reopenProcess: (pid: number) => post<T.ProcessDetail>(`/processes/${pid}/reopen`),
  trashProcess: (pid: number) => post<T.Process>(`/processes/${pid}/trash`),
  restoreProcess: (pid: number) => post<T.Process>(`/processes/${pid}/restore`),
  purgeProcess: (pid: number) => del<{ ok: boolean }>(`/processes/${pid}`),
  processActivities: (pid: number, limit = 30) => get<T.Activity[]>(`/processes/${pid}/activities`, { limit }),

  // STEP 1·2
  setSelection: (pid: number, asset_ids: number[]) => put<T.ProcessDetail>(`/processes/${pid}/selection`, { asset_ids }),
  suggestions: (pid: number) => get<{ suggestions: T.ComboSuggestion[]; selected: number; method: string }>(`/processes/${pid}/suggestions`),
  setCombo: (pid: number, dataset_ids: number[], source: "manual" | "suggestion" = "manual") =>
    put<T.ProcessDetail>(`/processes/${pid}/combo`, { dataset_ids, source }),
  comboWarnings: (pid: number) => get<{ warnings: T.ComboWarning[]; draft: { title: string; description: string } }>(`/processes/${pid}/combo/warnings`),
  confirmCombo: (pid: number, title: string, description?: string) => post<T.ProcessDetail>(`/processes/${pid}/combo/confirm`, { title, description }),
  unconfirmCombo: (pid: number) => post<T.ProcessDetail>(`/processes/${pid}/combo/unconfirm`),

  // STEP 3
  dataset: (did: number) => get<T.Dataset>(`/datasets/${did}`),
  patchMeta: (did: number, body: { values?: Record<string, unknown>; approve?: string[]; unapprove?: string[]; extra_classes?: string[] }) =>
    patch<T.Dataset>(`/datasets/${did}/meta`, body),
  confirmMeta: (did: number) => post<T.Dataset>(`/datasets/${did}/meta/confirm`),
  unconfirmMeta: (did: number) => post<T.Dataset>(`/datasets/${did}/meta/unconfirm`),
  preview: (did: number) => get<T.Preview>(`/datasets/${did}/preview`),

  // STEP 4
  classSuggestions: (did: number) =>
    get<{ suggestions: T.ClassSuggestion[]; method: string; thresholds: { strong: number; review: number; low: number } }>(
      `/datasets/${did}/classification/suggestions`,
    ),
  putClassification: (did: number, body: T.Classification) => put<T.Dataset>(`/datasets/${did}/classification`, body),
  confirmClassification: (did: number) => post<T.Dataset>(`/datasets/${did}/classification/confirm`),
  unconfirmClassification: (did: number) => post<T.Dataset>(`/datasets/${did}/classification/unconfirm`),

  // STEP 5
  relations: (pid: number) => get<T.RelationsPayload>(`/processes/${pid}/relations`),
  createRelation: (
    pid: number,
    body: {
      type: T.RelationType;
      source_id: number;
      target_id: number;
      key_code?: string | null;
      source_table?: string | null;
      source_column?: string | null;
      target_table?: string | null;
      target_column?: string | null;
      note?: string | null;
      confirm?: boolean;
    },
  ) => post<T.RelationsPayload>(`/processes/${pid}/relations`, body),
  updateRelation: (
    rid: number,
    body: Partial<{ key_code: string | null; source_table: string | null; source_column: string | null; target_table: string | null; target_column: string | null; note: string | null }>,
  ) => patch<T.RelationsPayload>(`/relations/${rid}`, body),
  confirmRelation: (rid: number) => post<T.RelationsPayload>(`/relations/${rid}/confirm`),
  unconfirmRelation: (rid: number) => post<T.RelationsPayload>(`/relations/${rid}/unconfirm`),
  deleteRelation: (rid: number) => del<T.RelationsPayload>(`/relations/${rid}`),
  orderRelations: (pid: number, relation_ids: number[]) => put<T.RelationsPayload>(`/processes/${pid}/relations/order`, { relation_ids }),
  graph: (pid: number, level: number) => get<T.GraphData>(`/processes/${pid}/graph`, { level }),
  setWaiver: (pid: number, reason: string) => post<T.ProcessDetail>(`/processes/${pid}/lineage-waiver`, { reason }),
  clearWaiver: (pid: number) => del<T.ProcessDetail>(`/processes/${pid}/lineage-waiver`),

  // STEP 6
  runValidation: (pid: number) => post<{ run: T.ValidationRun; state: T.ProcessState }>(`/processes/${pid}/validation-runs`),
  latestValidation: (pid: number) => get<T.ValidationLatest>(`/processes/${pid}/validation-runs/latest`),
  mint: (pid: number) => post<{ created: T.MintRegistry["records"]; detail: T.ProcessDetail }>(`/processes/${pid}/mint`),

  // STEP 7
  runSerialization: (pid: number, formats: string[]) => post<{ run: T.SerializationRun; state: T.ProcessState }>(`/processes/${pid}/serialization-runs`, { formats }),
  latestSerialization: (pid: number) => get<T.SerializationLatest>(`/processes/${pid}/serialization-runs/latest`),
  artifact: (aid: number) => get<T.ArtifactContent>(`/artifacts/${aid}`),
  publish: (pid: number) => post<{ published: T.CatalogEntry[] }>(`/processes/${pid}/publish`),

  // STEP 8
  runDiagnosis: (pid: number) => post<{ run: T.DiagRun; state: T.ProcessState }>(`/processes/${pid}/diagnosis-runs`),
  latestDiagnosis: (pid: number) => get<T.DiagLatest>(`/processes/${pid}/diagnosis-runs/latest`),
  attest: (pid: number, itemId: string, body: { status: "met" | "partial" | "unmet"; note?: string; evidence?: string }) =>
    put<{ ok: boolean }>(`/processes/${pid}/attestations/${itemId}`, body),

  // 카탈로그
  catalog: (params?: { q?: string; kind?: string; theme?: string; data_type?: string; status?: string }) => get<T.CatalogList>("/catalog", params),
  catalogEntry: (rid: string) => get<T.CatalogEntry>(`/catalog/${encodeURIComponent(rid)}`),
  withdraw: (rid: string) => post<T.CatalogEntry>(`/catalog/${encodeURIComponent(rid)}/withdraw`),
  republish: (rid: string) => post<T.CatalogEntry>(`/catalog/${encodeURIComponent(rid)}/restore`),
};

/** 내려받기 경로 모음 (downloadFile 과 함께 쓴다) */
export const downloads = {
  artifact: (aid: number) => `/artifacts/${aid}?download=true`,
  runZip: (runId: number) => `/serialization-runs/${runId}/download`,
  validationReport: (runId: number, datasetId: number) => `/validation-runs/${runId}/report?dataset_id=${datasetId}`,
  diagnosisReport: (runId: number) => `/diagnosis-runs/${runId}/report`,
  catalogRaw: (rid: string, format: "ttl" | "jsonld" | "txt" | "schema") => `/catalog/${encodeURIComponent(rid)}/raw?format=${format}`,
};
