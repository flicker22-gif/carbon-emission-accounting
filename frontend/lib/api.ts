export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** 地区选项:"全国"为兜底因子,其余为省级 */
export const REGIONS = [
  "全国", "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江",
  "上海", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北",
  "湖南", "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏",
  "陕西", "甘肃", "青海", "宁夏", "新疆",
];

export interface Facility {
  id: number;
  name: string;
  code: string;
  region: string;
  location?: string | null;
  industry?: string | null;
}

export interface EmissionFactor {
  id: number;
  energy_type: string;
  name_zh: string;
  scope: number;
  category: string;
  unit: string;
  factor_value: number;
  region: string;
  year: number;
  source?: string | null;
  note?: string | null;
}

export interface EnergyType {
  energy_type: string;
  name_zh: string;
  scope: number;
  unit: string;
}

export interface EnergyRecord {
  id: number;
  facility_id: number;
  facility_name: string;
  facility_region: string;
  energy_type: string;
  period: string;
  consumption: number;
  remark?: string | null;
  created_at: string;
  batch_id?: number | null;
  matched: boolean;
  factor_id?: number | null;
  factor_name?: string | null;
  factor_value?: number | null;
  factor_region?: string | null;
  factor_year?: number | null;
  scope?: number | null;
  category?: string | null;
  unit?: string | null;
  emissions_tco2e?: number | null;
}

export interface ReportSummary {
  period_from?: string | null;
  period_to?: string | null;
  total_tco2e: number;
  unmatched_records: number;
  pending_batches: number;
  by_scope: { scope: number; emissions_tco2e: number }[];
  by_category: { scope: number; category: string; emissions_tco2e: number }[];
  by_facility: {
    facility_id: number;
    facility_name: string;
    scope: number;
    emissions_tco2e: number;
  }[];
}

export type BatchStatus = "pending" | "confirmed" | "rejected";

export interface RowFieldError {
  field: string;
  message: string;
}

export interface BatchRow {
  id: number;
  row_number: number;
  is_valid: boolean;
  facility_id?: number | null;
  facility_code: string;
  facility_name: string;
  facility_region?: string | null;
  energy_type: string;
  period: string;
  consumption?: number | null;
  remark?: string | null;
  errors: RowFieldError[];
  raw_data: Record<string, string>;
  matched: boolean;
  factor_id?: number | null;
  factor_name?: string | null;
  factor_value?: number | null;
  factor_region?: string | null;
  factor_year?: number | null;
  scope?: number | null;
  category?: string | null;
  unit?: string | null;
  emissions_tco2e?: number | null;
}

export interface Batch {
  id: number;
  filename: string;
  content_hash: string;
  status: BatchStatus;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  impact_tco2e: number;
  unmatched_valid_rows: number;
  review_note?: string | null;
  created_at: string;
  confirmed_at?: string | null;
  rejected_at?: string | null;
  rows?: BatchRow[] | null;
}

export interface BatchSummary {
  id: number;
  filename: string;
  status: BatchStatus;
  total_rows: number;
  valid_rows: number;
  error_rows: number;
  impact_tco2e: number;
  unmatched_valid_rows: number;
  created_at: string;
  confirmed_at?: string | null;
  rejected_at?: string | null;
}

/** 因子变更影响试算结果(保存前预览,不落库) */
export interface FactorImpactPreview {
  affected_records: number;
  total_before_tco2e: number;
  total_after_tco2e: number;
  delta_tco2e: number;
  by_year: {
    year: number;
    records: number;
    before_tco2e: number;
    after_tco2e: number;
    delta_tco2e: number;
  }[];
  samples: {
    record_id: number;
    facility_name: string;
    period: string;
    energy_type: string;
    consumption: number;
    before_factor?: string | null;
    before_tco2e?: number | null;
    after_factor?: string | null;
    after_tco2e?: number | null;
  }[];
}

/** 把 FastAPI 错误响应(字符串 detail 或 422 校验错误数组)拼成可读信息 */
function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      const loc = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== "body") : [];
      const msg = String(d?.msg ?? "").replace(/^Value error, /, "");
      return loc.length ? `${loc.join(".")}: ${msg}` : msg;
    }).filter(Boolean);
    if (parts.length) return parts.join(";");
  }
  return `请求失败 (${status})`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const res = await fetch(`${API_BASE}${path}`, {
    // FormData 由浏览器自动设置含 boundary 的 Content-Type,不能手动指定
    headers: isForm ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(errorMessage(body, res.status));
  }
  return res.json();
}

export const api = {
  listFacilities: () => request<Facility[]>("/api/facilities"),
  createFacility: (data: Omit<Facility, "id">) =>
    request<Facility>("/api/facilities", { method: "POST", body: JSON.stringify(data) }),

  listFactors: (params?: { energy_type?: string; region?: string }) => {
    const q = new URLSearchParams();
    if (params?.energy_type) q.set("energy_type", params.energy_type);
    if (params?.region) q.set("region", params.region);
    const qs = q.toString();
    return request<EmissionFactor[]>(`/api/factors${qs ? `?${qs}` : ""}`);
  },
  createFactor: (data: Omit<EmissionFactor, "id">) =>
    request<EmissionFactor>("/api/factors", { method: "POST", body: JSON.stringify(data) }),
  updateFactor: (id: number, data: Partial<Omit<EmissionFactor, "id">>) =>
    request<EmissionFactor>(`/api/factors/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteFactor: (id: number) =>
    fetch(`${API_BASE}/api/factors/${id}`, { method: "DELETE" }),
  listEnergyTypes: () => request<EnergyType[]>("/api/factors/energy-types"),
  /** 保存前试算:factorId 为 null 表示新增因子 */
  previewFactorImpact: (factorId: number | null, factor: Omit<EmissionFactor, "id">) =>
    request<FactorImpactPreview>("/api/factors/impact-preview", {
      method: "POST",
      body: JSON.stringify({ factor_id: factorId, factor }),
    }),

  listRecords: () => request<EnergyRecord[]>("/api/records"),
  createRecord: (data: {
    facility_id: number;
    energy_type: string;
    period: string;
    consumption: number;
    remark?: string;
  }) =>
    request<EnergyRecord>("/api/records", { method: "POST", body: JSON.stringify(data) }),
  updateRecord: (id: number, data: {
    period?: string;
    consumption?: number;
    remark?: string | null;
  }) =>
    request<EnergyRecord>(`/api/records/${id}`, { method: "PUT", body: JSON.stringify(data) }),
  deleteRecord: (id: number) =>
    fetch(`${API_BASE}/api/records/${id}`, { method: "DELETE" }),

  summary: () => request<ReportSummary>("/api/reports/summary"),

  // ---------- 批量导入批次 ----------
  listBatches: (status?: BatchStatus) => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : "";
    return request<BatchSummary[]>(`/api/batches${qs}`);
  },
  getBatch: (id: number) => request<Batch>(`/api/batches/${id}`),
  importBatch: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Batch>("/api/batches/import", { method: "POST", body: form });
  },
  confirmBatch: (id: number, reviewNote?: string) =>
    request<Batch>(`/api/batches/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ review_note: reviewNote ?? null }),
    }),
  rejectBatch: (id: number, reviewNote?: string) =>
    request<Batch>(`/api/batches/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ review_note: reviewNote ?? null }),
    }),
  returnBatch: (id: number, reviewNote?: string) =>
    request<Batch>(`/api/batches/${id}/return`, {
      method: "POST",
      body: JSON.stringify({ review_note: reviewNote ?? null }),
    }),
  templateUrl: () => `${API_BASE}/api/batches/template.csv`,
};
