/**
 * Separation domain API client — TSK-017.
 */

import { apiClient } from './client';

// ─── Enums ──────────────────────────────────────────────────────

export type SeparationType =
  | 'RESIGNATION'
  | 'LAYOFF'
  | 'TERMINATION'
  | 'END_OF_CONTRACT'
  | 'RETIREMENT';

export type SeparationStatus =
  | 'DRAFT'
  | 'PENDING_APPROVAL_L1'
  | 'PENDING_APPROVAL_L2'
  | 'APPROVED'
  | 'EXECUTED'
  | 'REJECTED'
  | 'CANCELLED';

// ─── Types ──────────────────────────────────────────────────────

export interface SeparationListItem {
  id: string;
  employee_id: string;
  separation_type: SeparationType;
  status: SeparationStatus;
  effective_date: string;
  created_at: string;
  employee_nik: string | null;
  employee_name: string | null;
  employee_department: string | null;
  initiated_by_nik: string | null;
}

export interface Separation {
  id: string;
  employee_id: string;
  separation_type: SeparationType;
  status: SeparationStatus;
  reason: string;
  effective_date: string;
  notice_period_days: number;
  severance_amount: string | null;
  currency: string;
  assets_to_return: Array<{ item: string; returned: boolean }> | null;
  related_warning_letter_id: string | null;
  exit_interview_notes: string | null;
  exit_interview_completed_at: string | null;

  initiated_by_user_id: string;
  approval_l1_user_id: string | null;
  approval_l1_at: string | null;
  approval_l1_notes: string | null;
  approval_l2_user_id: string | null;
  approval_l2_at: string | null;
  approval_l2_notes: string | null;
  rejected_by_user_id: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  executed_by_user_id: string | null;
  executed_at: string | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;

  created_at: string;
  updated_at: string;

  employee_nik: string | null;
  employee_name: string | null;
  employee_department: string | null;
  initiated_by_nik: string | null;
  approval_l1_nik: string | null;
  approval_l2_nik: string | null;
}

export interface SeparationListResponse {
  items: SeparationListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface SeparationCreateRequest {
  employee_id: string;
  separation_type: SeparationType;
  reason: string;
  effective_date: string;
  notice_period_days?: number;
  severance_amount?: string;
  currency?: string;
  assets_to_return?: Array<{ item: string; returned: boolean }>;
  related_warning_letter_id?: string;
}

// ─── API ────────────────────────────────────────────────────────

export async function listSeparations(params: {
  status?: SeparationStatus;
  separation_type?: SeparationType;
  employee_id?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<SeparationListResponse> {
  const r = await apiClient.get<SeparationListResponse>('/api/v1/separations', {
    params: {
      status: params.status,
      separation_type: params.separation_type,
      employee_id: params.employee_id,
      page: params.page ?? 1,
      page_size: params.page_size ?? 50,
    },
  });
  return r.data;
}

export async function getSeparation(id: string): Promise<Separation> {
  const r = await apiClient.get<Separation>(`/api/v1/separations/${id}`);
  return r.data;
}

export async function createSeparation(data: SeparationCreateRequest): Promise<Separation> {
  const r = await apiClient.post<Separation>('/api/v1/separations', data);
  return r.data;
}

export async function approveL1(id: string, notes?: string): Promise<Separation> {
  const r = await apiClient.post<Separation>(`/api/v1/separations/${id}/approve-l1`, { notes });
  return r.data;
}

export async function approveL2(id: string, notes?: string): Promise<Separation> {
  const r = await apiClient.post<Separation>(`/api/v1/separations/${id}/approve-l2`, { notes });
  return r.data;
}

export async function rejectSeparation(id: string, rejection_reason: string): Promise<Separation> {
  const r = await apiClient.post<Separation>(`/api/v1/separations/${id}/reject`, {
    rejection_reason,
  });
  return r.data;
}

export async function cancelSeparation(id: string, cancellation_reason: string): Promise<Separation> {
  const r = await apiClient.post<Separation>(`/api/v1/separations/${id}/cancel`, {
    cancellation_reason,
  });
  return r.data;
}

export async function executeSeparation(id: string): Promise<Separation> {
  const r = await apiClient.post<Separation>(`/api/v1/separations/${id}/execute`);
  return r.data;
}

export async function recordExitInterview(id: string, notes: string): Promise<Separation> {
  const r = await apiClient.post<Separation>(`/api/v1/separations/${id}/exit-interview`, {
    notes,
  });
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export const SEPARATION_TYPE_META: Record<
  SeparationType,
  { label: string; icon: string; color: string }
> = {
  RESIGNATION: { label: 'Resignation', icon: '👋', color: 'var(--ide-blue)' },
  LAYOFF: { label: 'Layoff', icon: '📉', color: 'var(--ide-orange)' },
  TERMINATION: { label: 'Termination', icon: '⛔', color: 'var(--ide-red)' },
  END_OF_CONTRACT: { label: 'End of Contract', icon: '📄', color: 'var(--ide-purple)' },
  RETIREMENT: { label: 'Retirement', icon: '🎉', color: 'var(--ide-green)' },
};

export function separationStatusColor(
  s: SeparationStatus,
): { className: string; label: string } {
  switch (s) {
    case 'DRAFT':
      return { className: 'ide-tag-gray', label: 'Draft' };
    case 'PENDING_APPROVAL_L1':
      return { className: 'ide-tag-orange', label: 'Pending L1 Approval' };
    case 'PENDING_APPROVAL_L2':
      return { className: 'ide-tag-orange', label: 'Pending L2 Approval' };
    case 'APPROVED':
      return { className: 'ide-tag-blue', label: 'Approved' };
    case 'EXECUTED':
      return { className: 'ide-tag-green', label: 'Executed' };
    case 'REJECTED':
      return { className: 'ide-tag-red', label: 'Rejected' };
    case 'CANCELLED':
      return { className: 'ide-tag-gray', label: 'Cancelled' };
  }
}
