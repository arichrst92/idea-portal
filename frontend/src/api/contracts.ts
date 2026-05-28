/**
 * Employment Contract API client — TSK-018.
 */

import { apiClient } from './client';

export type ContractType = 'PKWT' | 'PKWTT';

export type ContractDerivedStatus =
  | 'ACTIVE'
  | 'EXPIRING_SOON_30'
  | 'EXPIRING_SOON_7'
  | 'EXPIRED'
  | 'ENDED';

export interface ContractListItem {
  id: string;
  employee_id: string;
  employee_nik: string | null;
  employee_name: string | null;
  employee_department: string | null;
  contract_type: ContractType;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  days_until_expiry: number | null;
  derived_status: ContractDerivedStatus;
}

export interface Contract extends ContractListItem {
  salary: string | null;
  document_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ContractListResponse {
  items: ContractListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ContractExpiringAlert {
  total_h30: number;
  total_h7: number;
  total_expired_unrenewed: number;
  items: ContractListItem[];
}

export interface ContractCreateRequest {
  employee_id: string;
  contract_type: ContractType;
  start_date: string;
  end_date?: string;
  salary?: string;
  document_url?: string;
}

export interface ContractRenewRequest {
  new_start_date: string;
  new_end_date?: string;
  new_contract_type: ContractType;
  new_salary?: string;
  notes: string;
}

export interface ContractTerminateRequest {
  termination_date: string;
  reason: string;
}

// ─── API ────────────────────────────────────────────────────────

export async function listContracts(params: {
  employee_id?: string;
  contract_type?: ContractType;
  is_active?: boolean;
  page?: number;
  page_size?: number;
} = {}): Promise<ContractListResponse> {
  const r = await apiClient.get<ContractListResponse>('/api/v1/contracts', {
    params: {
      employee_id: params.employee_id,
      contract_type: params.contract_type,
      is_active: params.is_active,
      page: params.page ?? 1,
      page_size: params.page_size ?? 100,
    },
  });
  return r.data;
}

export async function getExpiringAlerts(days_ahead = 30): Promise<ContractExpiringAlert> {
  const r = await apiClient.get<ContractExpiringAlert>('/api/v1/contracts/expiring', {
    params: { days_ahead },
  });
  return r.data;
}

export async function getContract(id: string): Promise<Contract> {
  const r = await apiClient.get<Contract>(`/api/v1/contracts/${id}`);
  return r.data;
}

export async function createContract(data: ContractCreateRequest): Promise<Contract> {
  const r = await apiClient.post<Contract>('/api/v1/contracts', data);
  return r.data;
}

export async function renewContract(
  id: string,
  data: ContractRenewRequest,
): Promise<Contract> {
  const r = await apiClient.post<Contract>(`/api/v1/contracts/${id}/renew`, data);
  return r.data;
}

export async function terminateContract(
  id: string,
  data: ContractTerminateRequest,
): Promise<Contract> {
  const r = await apiClient.post<Contract>(`/api/v1/contracts/${id}/terminate`, data);
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export function contractStatusBadge(s: ContractDerivedStatus): {
  className: string;
  label: string;
  color: string;
} {
  switch (s) {
    case 'ACTIVE':
      return { className: 'ide-tag-green', label: 'Active', color: 'var(--ide-green)' };
    case 'EXPIRING_SOON_30':
      return {
        className: 'ide-tag-orange',
        label: 'Expiring H-30',
        color: 'var(--ide-orange)',
      };
    case 'EXPIRING_SOON_7':
      return {
        className: 'ide-tag-red',
        label: 'CRITICAL H-7',
        color: 'var(--ide-red)',
      };
    case 'EXPIRED':
      return { className: 'ide-tag-red', label: 'Expired (no renewal)', color: 'var(--ide-red)' };
    case 'ENDED':
      return { className: 'ide-tag-gray', label: 'Ended', color: 'var(--ide-ink3)' };
  }
}

export function contractTypeLabel(t: ContractType): string {
  return t === 'PKWT' ? 'PKWT (Fixed-term)' : 'PKWTT (Permanent)';
}
