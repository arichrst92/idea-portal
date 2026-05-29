/**
 * Assessment domain API client — TSK-021.
 */

import { apiClient } from './client';

// ─── Types ──────────────────────────────────────────────────────

export interface Period {
  id: string;
  year: number;
  month: number;
  is_closed: boolean;
  created_at: string;
}

export interface AssessmentItem {
  id: string;
  config_id: string;
  code: string;
  name: string;
  weight_pct: string;
}

export interface AssessmentConfig {
  id: string;
  department_id: string;
  okr_weight_pct: string;
  weighted_weight_pct: string;
  effective_date: string;
  configured_by_user_id: string | null;
  created_at: string;
  department_name: string | null;
  items: AssessmentItem[];
}

export interface KeyResult {
  id: string;
  objective_id: string;
  description: string;
  target: string | null;
  achieved: string | null;
  progress_pct: string;
}

export interface Objective {
  id: string;
  employee_id: string;
  year: number;
  quarter: number;
  objective: string;
  set_by_user_id: string | null;
  created_at: string;
  employee_nik: string | null;
  employee_name: string | null;
  key_results: KeyResult[];
  avg_progress: string | null;
}

export interface Assessment {
  id: string;
  employee_id: string;
  period_id: string;
  okr_score: string | null;
  weighted_score: string | null;
  final_score: string | null;
  notes: string | null;
  submitted_by_user_id: string | null;
  created_at: string;
  employee_nik: string | null;
  employee_name: string | null;
  department_name: string | null;
  period_label: string | null;
  threshold_flag: string | null;
}

export interface ThresholdCheck {
  employee_id: string;
  employee_nik: string | null;
  employee_name: string | null;
  department_id: string | null;
  department_name: string | null;
  consecutive_low_months: number;
  threshold_score: string;
  recent_scores: Array<{ period: string; final_score: number | null; flag: string }>;
  suggested_sp_level: string | null;
  action_required: boolean;
}

export interface WarningLetter {
  id: string;
  employee_id: string;
  level: string;
  issued_date: string;
  reason: string;
  document_url: string | null;
  is_ai_drafted: boolean;
  acknowledged_at: string | null;
  approved_by_user_id: string | null;
  created_at: string;
  employee_nik: string | null;
  employee_name: string | null;
}

// ─── Period ─────────────────────────────────────────────────────

export async function listPeriods(): Promise<Period[]> {
  const r = await apiClient.get<Period[]>('/api/v1/assessment-periods');
  return r.data;
}

export async function createPeriod(year: number, month: number): Promise<Period> {
  const r = await apiClient.post<Period>('/api/v1/assessment-periods', { year, month });
  return r.data;
}

export async function closePeriod(id: string): Promise<Period> {
  const r = await apiClient.post<Period>(`/api/v1/assessment-periods/${id}/close`);
  return r.data;
}

// ─── Config ─────────────────────────────────────────────────────

export async function listConfigs(): Promise<AssessmentConfig[]> {
  const r = await apiClient.get<AssessmentConfig[]>('/api/v1/assessment-configs');
  return r.data;
}

export async function createConfig(data: {
  department_id: string;
  okr_weight_pct: number;
  weighted_weight_pct: number;
  effective_date: string;
  items: Array<{ code: string; name: string; weight_pct: number }>;
}): Promise<AssessmentConfig> {
  const r = await apiClient.post<AssessmentConfig>('/api/v1/assessment-configs', data);
  return r.data;
}

// ─── OKR ────────────────────────────────────────────────────────

export async function listObjectives(params: {
  employee_id?: string;
  year?: number;
  quarter?: number;
} = {}): Promise<Objective[]> {
  const r = await apiClient.get<Objective[]>('/api/v1/okr-objectives', { params });
  return r.data;
}

export async function createObjective(data: {
  employee_id: string;
  year: number;
  quarter: number;
  objective: string;
  key_results: Array<{ description: string; target?: string }>;
}): Promise<Objective> {
  const r = await apiClient.post<Objective>('/api/v1/okr-objectives', data);
  return r.data;
}

export async function updateKeyResult(
  id: string,
  data: { achieved?: string; progress_pct?: number },
): Promise<KeyResult> {
  const r = await apiClient.patch<KeyResult>(`/api/v1/okr-key-results/${id}`, data);
  return r.data;
}

// ─── Assessment ─────────────────────────────────────────────────

export async function listAssessments(params: {
  period_id?: string;
  employee_id?: string;
  department_id?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<{ items: Assessment[]; total: number; total_pages: number; page: number; page_size: number }> {
  const r = await apiClient.get('/api/v1/assessments', { params });
  return r.data;
}

export async function submitAssessment(data: {
  employee_id: string;
  period_id: string;
  okr_score: number;
  weighted_items: Array<{ item_code: string; score: number }>;
  notes?: string;
}): Promise<Assessment> {
  const r = await apiClient.post<Assessment>('/api/v1/assessments', data);
  return r.data;
}

// ─── SP / Threshold ────────────────────────────────────────────

export async function checkThreshold(employee_id: string): Promise<ThresholdCheck> {
  const r = await apiClient.get<ThresholdCheck>(`/api/v1/assessment-threshold-check/${employee_id}`);
  return r.data;
}

export async function listWarningLetters(employee_id?: string): Promise<WarningLetter[]> {
  const r = await apiClient.get<WarningLetter[]>('/api/v1/warning-letters', {
    params: { employee_id },
  });
  return r.data;
}

export async function issueWarningLetter(data: {
  employee_id: string;
  level: 'SP1' | 'SP2' | 'SP3';
  issued_date: string;
  reason: string;
  document_url?: string;
}): Promise<WarningLetter> {
  const r = await apiClient.post<WarningLetter>('/api/v1/warning-letters', data);
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export function thresholdColor(flag: string | null): { hex: string; soft: string; label: string } {
  switch (flag) {
    case 'GREEN':
      return { hex: 'var(--ide-green)', soft: 'var(--ide-green-soft)', label: 'Good' };
    case 'YELLOW':
      return { hex: '#FFD60A', soft: 'rgba(255, 214, 10, 0.15)', label: 'Watch' };
    case 'ORANGE':
      return { hex: 'var(--ide-orange)', soft: 'var(--ide-orange-soft)', label: 'Warning' };
    case 'RED':
      return { hex: 'var(--ide-red)', soft: 'var(--ide-red-soft)', label: 'Critical' };
    default:
      return { hex: 'var(--ide-ink3)', soft: 'var(--ide-bg)', label: 'N/A' };
  }
}

export function spLevelColor(level: string): { className: string; bg: string; color: string } {
  switch (level) {
    case 'SP1':
      return { className: 'ide-tag-orange', bg: 'var(--ide-orange-soft)', color: 'var(--ide-orange)' };
    case 'SP2':
      return { className: 'ide-tag-red', bg: 'var(--ide-red-soft)', color: 'var(--ide-red)' };
    case 'SP3':
      return { className: 'ide-tag-red', bg: 'var(--ide-red-soft)', color: 'var(--ide-red)' };
    default:
      return { className: 'ide-tag-gray', bg: 'var(--ide-bg)', color: 'var(--ide-ink3)' };
  }
}
