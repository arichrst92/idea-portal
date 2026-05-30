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
