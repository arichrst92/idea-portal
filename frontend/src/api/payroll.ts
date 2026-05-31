/**
 * Payroll API client — TSK-046.
 */

import { apiClient } from './client';

export type PeriodStatus = 'DRAFT' | 'REVIEWING' | 'APPROVED' | 'PAID' | 'LOCKED';
export type ComponentType = 'INCOME' | 'DEDUCTION';

export interface PayrollConfig {
  id: string;
  employee_id: string;
  basic_salary: string;
  fixed_allowance: string;
  bpjs_kesehatan_pct: string;
  bpjs_ketenagakerjaan_pct: string;
  effective_date: string;
  created_at: string;
  updated_at: string;
  employee_nik: string | null;
  employee_name: string | null;
}

export interface PayrollPeriod {
  id: string;
  year: number;
  month: number;
  pay_date: string;
  status: PeriodStatus;
  locked_at: string | null;
  created_at: string;
  updated_at: string;
  slip_count: number;
  total_gross: string | null;
  total_take_home: string | null;
}

export interface PayrollComponent {
  id: string;
  slip_id: string;
  code: string;
  name: string;
  component_type: ComponentType;
  is_variable: boolean;
  amount: string;
  source_reference: string | null;
  created_at: string;
}

export interface PayrollSlip {
  id: string;
  employee_id: string;
  period_id: string;
  slip_no: string;
  gross_income: string;
  total_deductions: string;
  take_home_pay: string;
  pdf_url: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
  employee_nik: string | null;
  employee_name: string | null;
  period_label: string | null;
  components: PayrollComponent[];
}

export interface GenerateSlipsResponse {
  period_id: string;
  generated: number;
  skipped: number;
  errors: string[];
}

// ─── Config ─────────────────────────────────────────────────────

export async function listConfigs(employee_id?: string): Promise<PayrollConfig[]> {
  const r = await apiClient.get<PayrollConfig[]>('/api/v1/payroll/configs', {
    params: employee_id ? { employee_id } : {},
  });
  return r.data;
}

export async function getActiveConfig(employee_id: string): Promise<PayrollConfig> {
  const r = await apiClient.get<PayrollConfig>(`/api/v1/payroll/configs/active/${employee_id}`);
  return r.data;
}

export async function upsertConfig(data: {
  employee_id: string;
  basic_salary: number;
  fixed_allowance?: number;
  bpjs_kesehatan_pct?: number;
  bpjs_ketenagakerjaan_pct?: number;
  effective_date: string;
}): Promise<PayrollConfig> {
  const r = await apiClient.post<PayrollConfig>('/api/v1/payroll/configs', data);
  return r.data;
}

export async function updateConfig(
  config_id: string,
  data: Partial<{
    basic_salary: number;
    fixed_allowance: number;
    bpjs_kesehatan_pct: number;
    bpjs_ketenagakerjaan_pct: number;
    effective_date: string;
  }>,
): Promise<PayrollConfig> {
  const r = await apiClient.patch<PayrollConfig>(`/api/v1/payroll/configs/${config_id}`, data);
  return r.data;
}

// ─── Period ─────────────────────────────────────────────────────

export async function listPeriods(): Promise<PayrollPeriod[]> {
  const r = await apiClient.get<PayrollPeriod[]>('/api/v1/payroll/periods');
  return r.data;
}

export async function createPeriod(data: {
  year: number;
  month: number;
  pay_date: string;
}): Promise<PayrollPeriod> {
  const r = await apiClient.post<PayrollPeriod>('/api/v1/payroll/periods', data);
  return r.data;
}

export async function generateSlips(period_id: string): Promise<GenerateSlipsResponse> {
  const r = await apiClient.post<GenerateSlipsResponse>(
    `/api/v1/payroll/periods/${period_id}/generate-slips`,
  );
  return r.data;
}

export async function lockPeriod(period_id: string): Promise<PayrollPeriod> {
  const r = await apiClient.post<PayrollPeriod>(`/api/v1/payroll/periods/${period_id}/lock`);
  return r.data;
}

// ─── Slip ───────────────────────────────────────────────────────

export async function listSlips(params: {
  period_id?: string;
  employee_id?: string;
} = {}): Promise<PayrollSlip[]> {
  const r = await apiClient.get<PayrollSlip[]>('/api/v1/payroll/slips', { params });
  return r.data;
}

export async function getSlip(slip_id: string): Promise<PayrollSlip> {
  const r = await apiClient.get<PayrollSlip>(`/api/v1/payroll/slips/${slip_id}`);
  return r.data;
}

export async function addComponent(
  slip_id: string,
  data: {
    code: string;
    name: string;
    component_type: ComponentType;
    is_variable?: boolean;
    amount: number;
    source_reference?: string;
  },
): Promise<PayrollComponent> {
  const r = await apiClient.post<PayrollComponent>(
    `/api/v1/payroll/slips/${slip_id}/components`,
    data,
  );
  return r.data;
}

export async function setPph21(slip_id: string, pph21_amount: number): Promise<PayrollSlip> {
  const r = await apiClient.post<PayrollSlip>(`/api/v1/payroll/slips/${slip_id}/pph21`, {
    pph21_amount,
  });
  return r.data;
}

export async function deleteComponent(component_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/payroll/components/${component_id}`);
}

// ─── PDF (TSK-051) ──────────────────────────────────────────────

export async function generateSlipPdf(slip_id: string): Promise<PayrollSlip> {
  const r = await apiClient.post<PayrollSlip>(`/api/v1/payroll/slips/${slip_id}/generate-pdf`);
  return r.data;
}

export async function getSlipPdfUrl(
  slip_id: string,
  expires_in: number = 3600,
): Promise<{ url: string; expires_in_seconds: number }> {
  const r = await apiClient.get<{ url: string; expires_in_seconds: number }>(
    `/api/v1/payroll/slips/${slip_id}/pdf-url`, { params: { expires_in } },
  );
  return r.data;
}

// ─── PPh21 enhancements (TSK-049) ────────────────────────────────

export interface Pph21SuggestResponse {
  slip_id: string;
  monthly_gross: string;
  annual_gross: string;
  ptkp: string;
  suggested_pph21: string;
  note: string;
}

export interface Pph21BulkRow {
  slip_id: string;
  pph21_amount: number;
}

export async function suggestPph21(
  slip_id: string,
  ptkp?: number
): Promise<Pph21SuggestResponse> {
  const r = await apiClient.get<Pph21SuggestResponse>(
    `/api/v1/payroll/slips/${slip_id}/pph21-suggest`,
    { params: ptkp ? { ptkp } : {} }
  );
  return r.data;
}

export async function bulkSetPph21(
  period_id: string,
  rows: Pph21BulkRow[]
): Promise<PayrollSlip[]> {
  const r = await apiClient.post<PayrollSlip[]>(
    `/api/v1/payroll/periods/${period_id}/bulk-pph21`,
    { period_id, rows }
  );
  return r.data;
}

// ─── Payroll Calc Engine (TSK-048) ──────────────────────────────

export interface CalculatePayrollPreview {
  period_id: string;
  calendar_working_days: number;
  attendance_missing_count: number;
  attendance_missing_employee_ids: string[];
  estimated_employee_count: number;
  can_proceed: boolean;
  blockers: string[];
}

export interface CalculatePayrollResponse {
  period_id: string;
  generated: number;
  skipped: number;
  total_gross_idr: string;
  total_deductions_idr: string;
  total_take_home_idr: string;
  employee_count: number;
  anomaly_warnings: string[];
  errors: string[];
}

export async function calculatePayrollPreview(
  period_id: string
): Promise<CalculatePayrollPreview> {
  const r = await apiClient.get<CalculatePayrollPreview>(
    `/api/v1/payroll/periods/${period_id}/calculate-preview`
  );
  return r.data;
}

export async function calculatePayroll(
  period_id: string
): Promise<CalculatePayrollResponse> {
  const r = await apiClient.post<CalculatePayrollResponse>(
    `/api/v1/payroll/periods/${period_id}/calculate`
  );
  return r.data;
}

// ─── Attendance (TSK-047) ────────────────────────────────────────

export interface AttendanceRow {
  id: string;
  employee_id: string;
  period_id: string;
  days_present: number;
  days_absent_paid: number;
  days_absent_unpaid: number;
  overtime_hours: string;
  notes: string | null;
  input_by_user_id: string;
  created_at: string;
  updated_at: string;
  employee_nik: string | null;
  employee_name: string | null;
  department_name: string | null;
}

export interface AttendanceListResponse {
  period_id: string;
  period_year: number;
  period_month: number;
  period_status: string;
  calendar_working_days: number;
  total_active_employees: number;
  submitted_count: number;
  missing_count: number;
  items: AttendanceRow[];
}

export interface AttendanceCompletenessResponse {
  period_id: string;
  calendar_working_days: number;
  total_active_employees: number;
  submitted_count: number;
  missing_count: number;
  missing_employee_ids: string[];
}

export interface AttendanceUpsertRow {
  employee_id: string;
  days_present: number;
  days_absent_paid?: number;
  days_absent_unpaid?: number;
  overtime_hours?: number;
  notes?: string | null;
}

export async function listAttendance(period_id: string): Promise<AttendanceListResponse> {
  const r = await apiClient.get<AttendanceListResponse>(
    `/api/v1/payroll/periods/${period_id}/attendance`
  );
  return r.data;
}

export async function getAttendanceCompleteness(
  period_id: string
): Promise<AttendanceCompletenessResponse> {
  const r = await apiClient.get<AttendanceCompletenessResponse>(
    `/api/v1/payroll/periods/${period_id}/attendance/completeness`
  );
  return r.data;
}

export async function bulkUpsertAttendance(
  period_id: string,
  rows: AttendanceUpsertRow[]
): Promise<AttendanceRow[]> {
  const r = await apiClient.post<AttendanceRow[]>(
    `/api/v1/payroll/periods/${period_id}/attendance`,
    { period_id, rows }
  );
  return r.data;
}

export async function updateAttendance(
  att_id: string,
  data: Partial<AttendanceUpsertRow>
): Promise<AttendanceRow> {
  const r = await apiClient.patch<AttendanceRow>(
    `/api/v1/payroll/attendance/${att_id}`,
    data
  );
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export const MONTHS_ID = [
  'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
];

export function periodLabel(p: { year: number; month: number }): string {
  return `${MONTHS_ID[p.month - 1]} ${p.year}`;
}

export function periodStatusColor(s: PeriodStatus): { className: string; label: string } {
  switch (s) {
    case 'DRAFT': return { className: 'ide-tag-gray', label: 'Draft' };
    case 'REVIEWING': return { className: 'ide-tag-orange', label: 'Reviewing' };
    case 'APPROVED': return { className: 'ide-tag-blue', label: 'Approved' };
    case 'PAID': return { className: 'ide-tag-green', label: 'Paid' };
    case 'LOCKED': return { className: 'ide-tag-purple', label: 'Locked' };
  }
}
