/**
 * Leave domain API client — TSK-019.
 */

import { apiClient } from './client';

export type LeaveRequestStatus =
  | 'PENDING_L1'
  | 'PENDING_L2'
  | 'APPROVED'
  | 'REJECTED'
  | 'CANCELLED';

export interface LeaveType {
  id: string;
  code: string;
  name: string;
  default_days_per_year: number;
  is_paid: boolean;
}

export interface LeaveBalance {
  id: string;
  employee_id: string;
  leave_type_id: string;
  year: number;
  allocated_days: number;
  used_days: number;
  carried_over_days: number;
  remaining_days: number;
  leave_type_code: string | null;
  leave_type_name: string | null;
}

export interface EmployeeBalanceSummary {
  employee_id: string;
  employee_nik: string | null;
  employee_name: string | null;
  year: number;
  balances: LeaveBalance[];
}

export interface LeaveRequestListItem {
  id: string;
  employee_id: string;
  employee_nik: string | null;
  employee_name: string | null;
  leave_type_code: string | null;
  leave_type_name: string | null;
  start_date: string;
  end_date: string;
  days_count: number;
  status: LeaveRequestStatus;
  created_at: string;
}

export interface LeaveRequest extends LeaveRequestListItem {
  leave_type_id: string;
  reason: string | null;
  layer1_approver_id: string | null;
  layer1_approved_at: string | null;
  layer1_notes: string | null;
  layer2_approver_id: string | null;
  layer2_approved_at: string | null;
  layer2_notes: string | null;
  rejected_by_user_id: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  cancelled_at: string | null;
  updated_at: string;
  layer1_approver_nik: string | null;
  layer2_approver_nik: string | null;
}

export interface LeaveRequestListResponse {
  items: LeaveRequestListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LeaveRequestCreateRequest {
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  reason?: string;
}

// ─── API ────────────────────────────────────────────────────────

export async function listLeaveTypes(): Promise<LeaveType[]> {
  const r = await apiClient.get<LeaveType[]>('/api/v1/leave-types');
  return r.data;
}

export async function getEmployeeBalances(
  employee_id: string,
  year?: number,
): Promise<EmployeeBalanceSummary> {
  const r = await apiClient.get<EmployeeBalanceSummary>('/api/v1/leave-balances', {
    params: { employee_id, year },
  });
  return r.data;
}

export async function listLeaveRequests(params: {
  employee_id?: string;
  status?: LeaveRequestStatus;
  page?: number;
  page_size?: number;
} = {}): Promise<LeaveRequestListResponse> {
  const r = await apiClient.get<LeaveRequestListResponse>('/api/v1/leave-requests', {
    params: {
      employee_id: params.employee_id,
      status: params.status,
      page: params.page ?? 1,
      page_size: params.page_size ?? 100,
    },
  });
  return r.data;
}

export async function getLeaveRequest(id: string): Promise<LeaveRequest> {
  const r = await apiClient.get<LeaveRequest>(`/api/v1/leave-requests/${id}`);
  return r.data;
}

export async function createLeaveRequest(
  data: LeaveRequestCreateRequest,
): Promise<LeaveRequest> {
  const r = await apiClient.post<LeaveRequest>('/api/v1/leave-requests', data);
  return r.data;
}

export async function approveLeaveL1(id: string, notes?: string): Promise<LeaveRequest> {
  const r = await apiClient.post<LeaveRequest>(`/api/v1/leave-requests/${id}/approve-l1`, {
    notes,
  });
  return r.data;
}

export async function approveLeaveL2(id: string, notes?: string): Promise<LeaveRequest> {
  const r = await apiClient.post<LeaveRequest>(`/api/v1/leave-requests/${id}/approve-l2`, {
    notes,
  });
  return r.data;
}

export async function rejectLeave(
  id: string,
  rejection_reason: string,
): Promise<LeaveRequest> {
  const r = await apiClient.post<LeaveRequest>(`/api/v1/leave-requests/${id}/reject`, {
    rejection_reason,
  });
  return r.data;
}

export async function cancelLeave(id: string): Promise<LeaveRequest> {
  const r = await apiClient.post<LeaveRequest>(`/api/v1/leave-requests/${id}/cancel`);
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export function leaveStatusColor(s: LeaveRequestStatus): { className: string; label: string } {
  switch (s) {
    case 'PENDING_L1':
      return { className: 'ide-tag-orange', label: 'Pending L1' };
    case 'PENDING_L2':
      return { className: 'ide-tag-orange', label: 'Pending L2' };
    case 'APPROVED':
      return { className: 'ide-tag-green', label: 'Approved' };
    case 'REJECTED':
      return { className: 'ide-tag-red', label: 'Rejected' };
    case 'CANCELLED':
      return { className: 'ide-tag-gray', label: 'Cancelled' };
  }
}

export function leaveTypeColor(code: string | null): string {
  const map: Record<string, string> = {
    ANNUAL: 'var(--ide-blue)',
    SICK: 'var(--ide-red)',
    MATERNITY: 'var(--ide-purple)',
    PATERNITY: 'var(--ide-purple)',
    MARRIAGE: 'var(--ide-green)',
    BEREAVEMENT: 'var(--ide-ink3)',
    HAJJ: 'var(--ide-teal)',
    UNPAID: 'var(--ide-orange)',
  };
  return map[code || ''] || 'var(--ide-ink3)';
}
