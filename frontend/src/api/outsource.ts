/**
 * Outsource API client — TSK-100.
 */

import { apiClient } from './client';

export type BillingType = 'FLAT' | 'PER_WORKDAY';

export interface Placement {
  id: string;
  employee_id: string;
  client_id: string;
  role_at_client: string;
  start_date: string;
  end_date: string | null;
  billing_type: BillingType;
  billing_rate: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  employee_nik: string | null;
  employee_name: string | null;
  client_code: string | null;
  client_name: string | null;
  monthly_billing_estimate: string | null;
  duration_days: number | null;
  days_until_end: number | null;
}

export interface PlacementListResponse {
  items: Placement[];
  total: number;
  active_count: number;
  expiring_30d: number;
}

export interface OutsourceClient {
  id: string;
  code: string;
  name: string;
  pic_name: string | null;
  pic_email: string | null;
  pic_phone: string | null;
  address: string | null;
  is_active: boolean;
  created_at: string;
  placement_count: number;
  active_placement_count: number;
}

// ─── Placement API ──────────────────────────────────────────────

export async function listPlacements(params: {
  client_id?: string;
  employee_id?: string;
  is_active?: boolean;
} = {}): Promise<PlacementListResponse> {
  const r = await apiClient.get<PlacementListResponse>('/api/v1/outsource/placements', { params });
  return r.data;
}

export async function getPlacement(id: string): Promise<Placement> {
  const r = await apiClient.get<Placement>(`/api/v1/outsource/placements/${id}`);
  return r.data;
}

export async function createPlacement(data: {
  employee_id: string;
  client_id: string;
  role_at_client: string;
  start_date: string;
  end_date?: string;
  billing_type: BillingType;
  billing_rate: number;
}): Promise<Placement> {
  const r = await apiClient.post<Placement>('/api/v1/outsource/placements', data);
  return r.data;
}

export async function updatePlacement(
  id: string,
  data: Partial<{
    role_at_client: string;
    start_date: string;
    end_date: string;
    billing_type: BillingType;
    billing_rate: number;
    is_active: boolean;
  }>,
): Promise<Placement> {
  const r = await apiClient.patch<Placement>(`/api/v1/outsource/placements/${id}`, data);
  return r.data;
}

export async function deletePlacement(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/outsource/placements/${id}`);
}

// ─── Client API ─────────────────────────────────────────────────

export async function listOutsourceClients(): Promise<OutsourceClient[]> {
  const r = await apiClient.get<OutsourceClient[]>('/api/v1/outsource/clients');
  return r.data;
}

export async function createOutsourceClient(data: {
  code: string;
  name: string;
  pic_name?: string;
  pic_email?: string;
  pic_phone?: string;
  address?: string;
}): Promise<OutsourceClient> {
  const r = await apiClient.post<OutsourceClient>('/api/v1/outsource/clients', data);
  return r.data;
}
