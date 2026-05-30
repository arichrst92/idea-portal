/**
 * Change Request API client — TSK-070.
 */

import { apiClient } from './client';

export type CRStatus =
  | 'DRAFT' | 'PENDING_L1' | 'PENDING_L2'
  | 'APPROVED' | 'REJECTED' | 'CANCELLED';

export type CRImpact = 'SCOPE' | 'TIMELINE' | 'COST' | 'MIXED';

export interface ChangeRequest {
  id: string;
  project_id: string;
  cr_number: string;
  title: string;
  description: string | null;
  impact_category: CRImpact;
  scope_delta: string | null;
  timeline_delta_days: number;
  cost_delta: string;
  currency: string;
  requester_user_id: string;
  status: CRStatus;
  layer1_approver_id: string | null;
  layer1_approved_at: string | null;
  layer1_notes: string | null;
  layer2_approver_id: string | null;
  layer2_approved_at: string | null;
  layer2_notes: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  sales_notified_at: string | null;
  finance_notified_at: string | null;
  created_at: string;
  updated_at: string;
  requester_nik: string | null;
  layer1_approver_nik: string | null;
  layer2_approver_nik: string | null;
  project_code: string | null;
}

export async function listChangeRequests(
  project_id: string,
  status?: CRStatus,
): Promise<ChangeRequest[]> {
  const r = await apiClient.get<ChangeRequest[]>(
    `/api/v1/projects/${project_id}/change-requests`,
    { params: status ? { status } : {} },
  );
  return r.data;
}

export async function createChangeRequest(
  project_id: string,
  data: {
    title: string; description?: string;
    impact_category?: CRImpact;
    scope_delta?: string;
    timeline_delta_days?: number;
    cost_delta?: number;
    currency?: string;
  },
): Promise<ChangeRequest> {
  const r = await apiClient.post<ChangeRequest>(
    `/api/v1/projects/${project_id}/change-requests`, data,
  );
  return r.data;
}

export async function submitCR(id: string): Promise<ChangeRequest> {
  const r = await apiClient.post<ChangeRequest>(`/api/v1/projects/change-requests/${id}/submit`);
  return r.data;
}

export async function approveCRL1(id: string, notes?: string): Promise<ChangeRequest> {
  const r = await apiClient.post<ChangeRequest>(`/api/v1/projects/change-requests/${id}/approve-l1`, { notes });
  return r.data;
}

export async function approveCRL2(id: string, notes?: string): Promise<ChangeRequest> {
  const r = await apiClient.post<ChangeRequest>(`/api/v1/projects/change-requests/${id}/approve-l2`, { notes });
  return r.data;
}

export async function rejectCR(id: string, rejection_reason: string): Promise<ChangeRequest> {
  const r = await apiClient.post<ChangeRequest>(`/api/v1/projects/change-requests/${id}/reject`, { rejection_reason });
  return r.data;
}

export async function cancelCR(id: string): Promise<ChangeRequest> {
  const r = await apiClient.post<ChangeRequest>(`/api/v1/projects/change-requests/${id}/cancel`);
  return r.data;
}

export function crStatusColor(s: CRStatus): { className: string; label: string } {
  switch (s) {
    case 'DRAFT': return { className: 'ide-tag-gray', label: 'Draft' };
    case 'PENDING_L1': return { className: 'ide-tag-orange', label: 'Pending L1' };
    case 'PENDING_L2': return { className: 'ide-tag-orange', label: 'Pending L2' };
    case 'APPROVED': return { className: 'ide-tag-green', label: 'Approved' };
    case 'REJECTED': return { className: 'ide-tag-red', label: 'Rejected' };
    case 'CANCELLED': return { className: 'ide-tag-gray', label: 'Cancelled' };
  }
}
