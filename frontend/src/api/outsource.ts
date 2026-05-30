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

// ─── Timesheet (TSK-103+104) ────────────────────────────────────

export type TimesheetStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED';

export interface TimesheetItem {
  id: string;
  timesheet_id: string;
  work_date: string;
  is_present: boolean;
  notes: string | null;
}

export interface Timesheet {
  id: string;
  placement_id: string;
  year: number;
  month: number;
  workdays_count: number;
  status: TimesheetStatus;
  submitted_at: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  period_label: string | null;
  placement_employee_nik: string | null;
  placement_employee_name: string | null;
  placement_client_code: string | null;
  placement_client_name: string | null;
  placement_role: string | null;
  items: TimesheetItem[];
  present_count: number;
  absent_count: number;
}

export async function listTimesheets(params: {
  placement_id?: string;
  status?: TimesheetStatus;
  year?: number;
  month?: number;
} = {}): Promise<Timesheet[]> {
  const r = await apiClient.get<Timesheet[]>('/api/v1/outsource/timesheets', { params });
  return r.data;
}

export async function getTimesheet(id: string): Promise<Timesheet> {
  const r = await apiClient.get<Timesheet>(`/api/v1/outsource/timesheets/${id}`);
  return r.data;
}

export async function createTimesheet(data: {
  placement_id: string;
  year: number;
  month: number;
}): Promise<Timesheet> {
  const r = await apiClient.post<Timesheet>('/api/v1/outsource/timesheets', data);
  return r.data;
}

export async function upsertTimesheetItem(
  ts_id: string,
  data: { work_date: string; is_present: boolean; notes?: string },
): Promise<TimesheetItem> {
  const r = await apiClient.post<TimesheetItem>(`/api/v1/outsource/timesheets/${ts_id}/items`, data);
  return r.data;
}

export async function deleteTimesheetItem(item_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/outsource/timesheets/items/${item_id}`);
}

export async function submitTimesheet(id: string): Promise<Timesheet> {
  const r = await apiClient.post<Timesheet>(`/api/v1/outsource/timesheets/${id}/submit`);
  return r.data;
}

export async function approveTimesheet(id: string, notes?: string): Promise<Timesheet> {
  const r = await apiClient.post<Timesheet>(`/api/v1/outsource/timesheets/${id}/approve`, { notes });
  return r.data;
}

export async function rejectTimesheet(id: string, rejection_reason: string): Promise<Timesheet> {
  const r = await apiClient.post<Timesheet>(`/api/v1/outsource/timesheets/${id}/reject`, { rejection_reason });
  return r.data;
}

export function timesheetStatusColor(s: TimesheetStatus): { className: string; label: string } {
  switch (s) {
    case 'DRAFT': return { className: 'ide-tag-gray', label: 'Draft' };
    case 'SUBMITTED': return { className: 'ide-tag-orange', label: 'Submitted' };
    case 'APPROVED': return { className: 'ide-tag-green', label: 'Approved' };
    case 'REJECTED': return { className: 'ide-tag-red', label: 'Rejected' };
  }
}

// ─── Berita Acara (TSK-105) ──────────────────────────────────────

export interface BeritaAcara {
  id: string;
  timesheet_id: string;
  ba_no: string;
  pdf_url: string | null;
  signed_by_ide: boolean;
  signed_by_client: boolean;
  client_signed_at: string | null;
  created_at: string;
  timesheet_period_label: string | null;
  employee_name: string | null;
  client_name: string | null;
  download_url: string | null;
}

export async function generateBA(ts_id: string): Promise<BeritaAcara> {
  const r = await apiClient.post<BeritaAcara>(`/api/v1/outsource/timesheets/${ts_id}/generate-ba`);
  return r.data;
}

export async function getBAForTimesheet(ts_id: string): Promise<BeritaAcara | null> {
  try {
    const r = await apiClient.get<BeritaAcara>(`/api/v1/outsource/timesheets/${ts_id}/ba`);
    return r.data;
  } catch (e: any) {
    if (e?.response?.status === 404) return null;
    throw e;
  }
}

export async function getBADownloadUrl(ba_id: string): Promise<{ url: string }> {
  const r = await apiClient.get<{ url: string }>(`/api/v1/outsource/ba/${ba_id}/download-url`);
  return r.data;
}

export async function regenerateBA(ba_id: string): Promise<BeritaAcara> {
  const r = await apiClient.post<BeritaAcara>(`/api/v1/outsource/ba/${ba_id}/regenerate`);
  return r.data;
}

// ─── Client Complaint + SP-O (TSK-148) ──────────────────────────

export type ComplaintSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type SpoLevelType = 'SP-O1' | 'SP-O2' | 'SP-O3';

export interface ClientComplaint {
  id: string;
  placement_id: string;
  complaint_date: string;
  severity: ComplaintSeverity;
  description: string;
  logged_by_user_id: string | null;
  resolved_at: string | null;
  created_at: string;
  placement_employee_nik: string | null;
  placement_employee_name: string | null;
  placement_client_code: string | null;
  placement_client_name: string | null;
  placement_role: string | null;
  logged_by_nik: string | null;
  spo_count: number;
}

export interface SpOOutsource {
  id: string;
  placement_id: string;
  level: SpoLevelType;
  issued_date: string;
  triggered_by_complaint_id: string | null;
  reason: string;
  evaluation_end_date: string | null;
  triggers_replacement: boolean;
  created_at: string;
  placement_employee_nik: string | null;
  placement_employee_name: string | null;
  placement_client_code: string | null;
  placement_client_name: string | null;
  placement_role: string | null;
  complaint_severity: string | null;
  complaint_description: string | null;
}

export async function listComplaints(params: {
  placement_id?: string;
  resolved?: boolean;
} = {}): Promise<ClientComplaint[]> {
  const r = await apiClient.get<ClientComplaint[]>('/api/v1/outsource/complaints', { params });
  return r.data;
}

export async function createComplaint(data: {
  placement_id: string;
  complaint_date: string;
  severity: ComplaintSeverity;
  description: string;
}): Promise<ClientComplaint> {
  const r = await apiClient.post<ClientComplaint>('/api/v1/outsource/complaints', data);
  return r.data;
}

export async function resolveComplaint(id: string): Promise<ClientComplaint> {
  const r = await apiClient.post<ClientComplaint>(`/api/v1/outsource/complaints/${id}/resolve`);
  return r.data;
}

export async function listSpo(params: {
  placement_id?: string;
  complaint_id?: string;
} = {}): Promise<SpOOutsource[]> {
  const r = await apiClient.get<SpOOutsource[]>('/api/v1/outsource/spo', { params });
  return r.data;
}

export async function createSpo(data: {
  placement_id: string;
  triggered_by_complaint_id?: string;
  issued_date: string;
  reason: string;
}): Promise<SpOOutsource> {
  const r = await apiClient.post<SpOOutsource>('/api/v1/outsource/spo', data);
  return r.data;
}

export function severityColor(s: ComplaintSeverity): string {
  switch (s) {
    case 'LOW': return '#6e6e73';
    case 'MEDIUM': return '#FF9500';
    case 'HIGH': return '#FF3B30';
    case 'CRITICAL': return '#AF52DE';
  }
}

export function spoLevelColor(s: SpoLevelType): string {
  switch (s) {
    case 'SP-O1': return '#FF9500';
    case 'SP-O2': return '#FF3B30';
    case 'SP-O3': return '#AF52DE';
  }
}

// ─── Contract Alerts (TSK-106) ──────────────────────────────────

export interface ExpiringPlacementItem {
  placement_id: string;
  employee_nik: string | null;
  employee_name: string | null;
  client_code: string | null;
  role: string;
  end_date: string | null;
  days_until_end: number;
  severity: 'h7' | 'h30';
}

export interface ExpiringPlacementResponse {
  h7_count: number;
  h30_count: number;
  items: ExpiringPlacementItem[];
}

export async function getExpiringPlacements(days: number = 30): Promise<ExpiringPlacementResponse> {
  const r = await apiClient.get<ExpiringPlacementResponse>('/api/v1/outsource/placements-expiring', {
    params: { days },
  });
  return r.data;
}

// ─── Placement Amendment (TSK-107) ──────────────────────────────

export interface PlacementAmendment {
  id: string;
  placement_id: string;
  amendment_no: string;
  effective_date: string;
  old_end_date: string | null;
  old_billing_rate: string | null;
  new_end_date: string | null;
  new_billing_rate: string | null;
  document_url: string | null;
  notes: string | null;
  created_by_user_id: string | null;
  created_at: string;
  created_by_nik: string | null;
  download_url: string | null;
}

export async function renewPlacement(
  placement_id: string,
  data: {
    effective_date: string;
    new_end_date?: string;
    new_billing_rate?: number;
    document_url?: string;
    notes?: string;
  },
): Promise<PlacementAmendment> {
  const r = await apiClient.post<PlacementAmendment>(
    `/api/v1/outsource/placements/${placement_id}/renew`, data,
  );
  return r.data;
}

export async function listAmendments(placement_id: string): Promise<PlacementAmendment[]> {
  const r = await apiClient.get<PlacementAmendment[]>(
    `/api/v1/outsource/placements/${placement_id}/amendments`,
  );
  return r.data;
}
