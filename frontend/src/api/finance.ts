/**
 * Finance API client — TSK-023 (Reimbursement + Procurement + Vendor).
 */

import { apiClient } from './client';

export type ReimbStatus =
  | 'PENDING_L1'
  | 'PENDING_L2'
  | 'APPROVED'
  | 'TRANSFERRED'
  | 'REJECTED'
  | 'CANCELLED';

export type ProcStatus =
  | 'PENDING_L1'
  | 'PENDING_L2'
  | 'APPROVED'
  | 'ORDERED'
  | 'DELIVERED'
  | 'REJECTED'
  | 'CANCELLED';

export const REIMB_CATEGORIES = [
  'MEDICAL',
  'TRANSPORT',
  'MEAL',
  'BUSINESS_TRIP',
  'COMMUNICATION',
  'ENTERTAINMENT',
  'OTHER',
] as const;

export const PROC_CATEGORIES = [
  'IT_EQUIPMENT',
  'OFFICE_SUPPLIES',
  'FURNITURE',
  'SOFTWARE_LICENSE',
  'MARKETING',
  'OTHER',
] as const;

// ─── Types ──────────────────────────────────────────────────────

export interface Vendor {
  id: string;
  code: string;
  name: string;
  contact_info: string | null;
  created_at: string;
}

export interface ReimbursementListItem {
  id: string;
  employee_id: string;
  employee_nik: string | null;
  employee_name: string | null;
  request_date: string;
  category: string;
  amount: string;
  currency: string;
  status: ReimbStatus;
  transferred_at: string | null;
  project_name: string | null;
  created_at: string;
}

export interface Reimbursement extends ReimbursementListItem {
  description: string;
  receipt_url: string | null;
  project_id: string | null;
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
  transferred_by_user_id: string | null;
  transfer_reference: string | null;
  updated_at: string;
  layer1_approver_nik: string | null;
  layer2_approver_nik: string | null;
}

export interface ProcurementListItem {
  id: string;
  requested_by_nik: string | null;
  item_description: string;
  item_category: string;
  quantity: number;
  estimated_amount: string | null;
  actual_amount: string | null;
  currency: string;
  vendor_name: string | null;
  status: ProcStatus;
  is_asset: boolean;
  expected_delivery_date: string | null;
  actual_delivery_date: string | null;
  created_at: string;
}

export interface Procurement extends ProcurementListItem {
  requested_by_user_id: string;
  request_date: string | null;
  vendor_id: string | null;
  notes: string | null;
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
  po_number: string | null;
  ordered_at: string | null;
  updated_at: string;
  vendor_code: string | null;
}

// ─── Vendor API ─────────────────────────────────────────────────

export async function listVendors(): Promise<Vendor[]> {
  const r = await apiClient.get<Vendor[]>('/api/v1/vendors');
  return r.data;
}

export async function createVendor(data: {
  code: string;
  name: string;
  contact_info?: string;
}): Promise<Vendor> {
  const r = await apiClient.post<Vendor>('/api/v1/vendors', data);
  return r.data;
}

// ─── Reimbursement API ─────────────────────────────────────────

export async function listReimbursements(params: {
  employee_id?: string;
  status?: ReimbStatus;
  category?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<{ items: ReimbursementListItem[]; total: number; total_pages: number; page: number; page_size: number }> {
  const r = await apiClient.get('/api/v1/reimbursements', { params });
  return r.data;
}

export async function createReimbursement(data: {
  employee_id: string;
  request_date: string;
  category: string;
  amount: number;
  currency?: string;
  description: string;
  receipt_url?: string;
  project_id?: string;
}): Promise<Reimbursement> {
  const r = await apiClient.post<Reimbursement>('/api/v1/reimbursements', data);
  return r.data;
}

export async function approveReimbL1(id: string, notes?: string): Promise<Reimbursement> {
  const r = await apiClient.post<Reimbursement>(`/api/v1/reimbursements/${id}/approve-l1`, { notes });
  return r.data;
}

export async function approveReimbL2(id: string, notes?: string): Promise<Reimbursement> {
  const r = await apiClient.post<Reimbursement>(`/api/v1/reimbursements/${id}/approve-l2`, { notes });
  return r.data;
}

export async function rejectReimb(id: string, rejection_reason: string): Promise<Reimbursement> {
  const r = await apiClient.post<Reimbursement>(`/api/v1/reimbursements/${id}/reject`, { rejection_reason });
  return r.data;
}

export async function cancelReimb(id: string): Promise<Reimbursement> {
  const r = await apiClient.post<Reimbursement>(`/api/v1/reimbursements/${id}/cancel`);
  return r.data;
}

export async function transferReimb(id: string, transfer_reference: string): Promise<Reimbursement> {
  const r = await apiClient.post<Reimbursement>(`/api/v1/reimbursements/${id}/transfer`, { transfer_reference });
  return r.data;
}

// ─── Procurement API ────────────────────────────────────────────

export async function listProcurements(params: {
  requested_by_user_id?: string;
  status?: ProcStatus;
  category?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<{ items: ProcurementListItem[]; total: number; total_pages: number; page: number; page_size: number }> {
  const r = await apiClient.get('/api/v1/procurements', { params });
  return r.data;
}

export async function createProcurement(data: {
  item_description: string;
  item_category: string;
  quantity: number;
  estimated_amount?: number;
  currency?: string;
  vendor_id?: string;
  is_asset?: boolean;
  expected_delivery_date?: string;
  request_date?: string;
  notes?: string;
}): Promise<Procurement> {
  const r = await apiClient.post<Procurement>('/api/v1/procurements', data);
  return r.data;
}

export async function approveProcL1(id: string, notes?: string): Promise<Procurement> {
  const r = await apiClient.post<Procurement>(`/api/v1/procurements/${id}/approve-l1`, { notes });
  return r.data;
}

export async function approveProcL2(id: string, notes?: string): Promise<Procurement> {
  const r = await apiClient.post<Procurement>(`/api/v1/procurements/${id}/approve-l2`, { notes });
  return r.data;
}

export async function rejectProc(id: string, rejection_reason: string): Promise<Procurement> {
  const r = await apiClient.post<Procurement>(`/api/v1/procurements/${id}/reject`, { rejection_reason });
  return r.data;
}

export async function cancelProc(id: string): Promise<Procurement> {
  const r = await apiClient.post<Procurement>(`/api/v1/procurements/${id}/cancel`);
  return r.data;
}

export async function orderProc(
  id: string,
  data: { po_number: string; vendor_id?: string; actual_amount?: number },
): Promise<Procurement> {
  const r = await apiClient.post<Procurement>(`/api/v1/procurements/${id}/order`, data);
  return r.data;
}

export async function deliverProc(id: string, actual_delivery_date: string): Promise<Procurement> {
  const r = await apiClient.post<Procurement>(`/api/v1/procurements/${id}/deliver`, {
    actual_delivery_date,
  });
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export function reimbStatusColor(s: ReimbStatus): { className: string; label: string } {
  switch (s) {
    case 'PENDING_L1':
    case 'PENDING_L2':
      return { className: 'ide-tag-orange', label: s.replace('_', ' ') };
    case 'APPROVED':
      return { className: 'ide-tag-blue', label: 'Approved (siap transfer)' };
    case 'TRANSFERRED':
      return { className: 'ide-tag-green', label: 'Transferred' };
    case 'REJECTED':
      return { className: 'ide-tag-red', label: 'Rejected' };
    case 'CANCELLED':
      return { className: 'ide-tag-gray', label: 'Cancelled' };
  }
}

export function procStatusColor(s: ProcStatus): { className: string; label: string } {
  switch (s) {
    case 'PENDING_L1':
    case 'PENDING_L2':
      return { className: 'ide-tag-orange', label: s.replace('_', ' ') };
    case 'APPROVED':
      return { className: 'ide-tag-blue', label: 'Approved (siap PO)' };
    case 'ORDERED':
      return { className: 'ide-tag-purple', label: 'Ordered (menunggu delivery)' };
    case 'DELIVERED':
      return { className: 'ide-tag-green', label: 'Delivered' };
    case 'REJECTED':
      return { className: 'ide-tag-red', label: 'Rejected' };
    case 'CANCELLED':
      return { className: 'ide-tag-gray', label: 'Cancelled' };
  }
}
