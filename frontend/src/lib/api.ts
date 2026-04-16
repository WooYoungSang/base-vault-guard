const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Vault {
  address: string;
  protocol: string;
  asset: string;
  tvl_usd: number;
  apy: number;
  utilization_rate: number;
}

export interface RiskProfile {
  utilization: number;
  tvl_change_7d: number;
  oracle_risk_score: number;
  audit_score: number;
  drawdown_max: number;
  sufficient_data: boolean;
}

export interface ScoredVault {
  vault: Vault;
  risk: RiskProfile;
  score: number;
  grade: string;
  disclaimer: string;
}

export interface VaultListResponse {
  items: ScoredVault[];
  total: number;
  page: number;
  page_size: number;
  disclaimer: string;
}

export interface GradeRecord {
  grade: string;
  score: number;
  recorded_at: string;
}

export interface VaultHistoryResponse {
  vault_address: string;
  history: GradeRecord[];
}

export interface SafeYieldResponse {
  items: ScoredVault[];
  min_grade: string;
  total: number;
  disclaimer: string;
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  listVaults: (params?: {
    protocol?: string;
    grade?: string;
    page?: number;
    page_size?: number;
  }) => {
    const q = new URLSearchParams();
    if (params?.protocol) q.set("protocol", params.protocol);
    if (params?.grade) q.set("grade", params.grade);
    if (params?.page) q.set("page", String(params.page));
    if (params?.page_size) q.set("page_size", String(params.page_size));
    const qs = q.toString() ? `?${q.toString()}` : "";
    return apiFetch<VaultListResponse>(`/vaults${qs}`);
  },

  getVault: (address: string) =>
    apiFetch<ScoredVault>(`/vaults/${address}`),

  getVaultHistory: (address: string) =>
    apiFetch<VaultHistoryResponse>(`/vaults/${address}/history`),

  safeYield: (minGrade = "B") =>
    apiFetch<SafeYieldResponse>(`/vaults/safe-yield?min_grade=${minGrade}`),
};
