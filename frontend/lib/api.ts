export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Facility {
  id: number;
  name: string;
  code: string;
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
  source?: string | null;
  note?: string | null;
}

export interface EnergyRecord {
  id: number;
  facility_id: number;
  facility_name: string;
  factor_id: number;
  energy_type: string;
  factor_name: string;
  scope: number;
  category: string;
  unit: string;
  period: string;
  consumption: number;
  emissions_tco2e: number;
  remark?: string | null;
  created_at: string;
}

export interface ReportSummary {
  period_from?: string | null;
  period_to?: string | null;
  total_tco2e: number;
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
  listFactors: () => request<EmissionFactor[]>("/api/factors"),
  listRecords: () => request<EnergyRecord[]>("/api/records"),
  createRecord: (data: {
    facility_id: number;
    factor_id: number;
    period: string;
    consumption: number;
    remark?: string;
  }) =>
    request<EnergyRecord>("/api/records", { method: "POST", body: JSON.stringify(data) }),
  deleteRecord: (id: number) =>
    fetch(`${API_BASE}/api/records/${id}`, { method: "DELETE" }),
  summary: () => request<ReportSummary>("/api/reports/summary"),
};
