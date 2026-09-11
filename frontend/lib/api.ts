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
  by_scope: { scope: number; emissions_tco2e: number }[];
  by_category: { scope: number; category: string; emissions_tco2e: number }[];
  by_facility: {
    facility_id: number;
    facility_name: string;
    scope: number;
    emissions_tco2e: number;
  }[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `请求失败 (${res.status})`);
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

  listRecords: () => request<EnergyRecord[]>("/api/records"),
  createRecord: (data: {
    facility_id: number;
    energy_type: string;
    period: string;
    consumption: number;
    remark?: string;
  }) =>
    request<EnergyRecord>("/api/records", { method: "POST", body: JSON.stringify(data) }),
  deleteRecord: (id: number) =>
    fetch(`${API_BASE}/api/records/${id}`, { method: "DELETE" }),

  summary: () => request<ReportSummary>("/api/reports/summary"),
};
