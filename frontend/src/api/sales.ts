/**
 * Sales API client — TSK-024.
 */

import { apiClient } from './client';

export type LeadStage =
  | 'PROSPECT'
  | 'QUALIFIED'
  | 'PROPOSAL'
  | 'NEGOTIATION'
  | 'CLOSED_WON'
  | 'CLOSED_LOST';

export interface LeadListItem {
  id: string;
  company_name: string;
  pic_name: string | null;
  stage: LeadStage;
  estimated_value: string | null;
  currency: string;
  assigned_to_nik: string | null;
  is_direktur_driven: boolean;
  days_in_stage: number | null;
  created_at: string;
}

export interface Lead {
  id: string;
  company_name: string;
  pic_name: string | null;
  pic_email: string | null;
  pic_phone: string | null;
  services: string | null;
  stage: LeadStage;
  estimated_value: string | null;
  currency: string;
  source: string | null;
  assigned_to_user_id: string | null;
  referred_by_user_id: string | null;
  is_direktur_driven: boolean;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
  assigned_to_nik: string | null;
  days_in_stage: number | null;
  activity_count: number;
  proposal_count: number;
}

export interface PipelineStageBucket {
  stage: LeadStage;
  label: string;
  count: number;
  total_value: string;
  leads: LeadListItem[];
}

export interface PipelineResponse {
  stages: PipelineStageBucket[];
  total_leads: number;
  total_pipeline_value: string;
  closed_won_value_ytd: string;
}

export interface Commission {
  id: string;
  lead_id: string;
  sales_user_id: string;
  commission_pct: string;
  commission_amount: string;
  target_payroll_period_id: string | null;
  status: string;
  created_at: string;
  sales_nik: string | null;
  lead_company: string | null;
}

export interface Target {
  id: string;
  user_id: string | null;
  department_id: string | null;
  year: number;
  month: number | null;
  target_amount: string;
  currency: string;
  user_nik: string | null;
  department_name: string | null;
  achieved_amount: string;
  achievement_pct: string;
}

// ─── API ────────────────────────────────────────────────────────

export async function listLeads(params: { stage?: LeadStage } = {}): Promise<LeadListItem[]> {
  const r = await apiClient.get<LeadListItem[]>('/api/v1/leads', { params });
  return r.data;
}

export async function getLead(id: string): Promise<Lead> {
  const r = await apiClient.get<Lead>(`/api/v1/leads/${id}`);
  return r.data;
}

export async function createLead(data: {
  company_name: string;
  pic_name?: string;
  pic_email?: string;
  pic_phone?: string;
  services?: string;
  estimated_value?: number;
  source?: string;
  assigned_to_user_id?: string;
  is_direktur_driven?: boolean;
}): Promise<Lead> {
  const r = await apiClient.post<Lead>('/api/v1/leads', data);
  return r.data;
}

export async function transitionLead(
  id: string,
  data: { new_stage: LeadStage; commission_pct?: number; notes?: string },
): Promise<Lead> {
  const r = await apiClient.post<Lead>(`/api/v1/leads/${id}/transition`, data);
  return r.data;
}

export async function getPipeline(): Promise<PipelineResponse> {
  const r = await apiClient.get<PipelineResponse>('/api/v1/sales-pipeline');
  return r.data;
}

export async function listCommissions(params: { sales_user_id?: string; status?: string } = {}): Promise<Commission[]> {
  const r = await apiClient.get<Commission[]>('/api/v1/sales-commissions', { params });
  return r.data;
}

export async function listTargets(year?: number): Promise<Target[]> {
  const r = await apiClient.get<Target[]>('/api/v1/sales-targets', { params: { year } });
  return r.data;
}

export async function createTarget(data: {
  user_id?: string;
  department_id?: string;
  year: number;
  month?: number;
  target_amount: number;
}): Promise<Target> {
  const r = await apiClient.post<Target>('/api/v1/sales-targets', data);
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export function stageColor(s: LeadStage): { hex: string; soft: string; label: string } {
  switch (s) {
    case 'PROSPECT':
      return { hex: 'var(--ide-ink3)', soft: 'var(--ide-bg)', label: 'Prospect' };
    case 'QUALIFIED':
      return { hex: 'var(--ide-blue)', soft: 'var(--ide-blue-soft)', label: 'Qualified' };
    case 'PROPOSAL':
      return { hex: 'var(--ide-purple)', soft: 'var(--ide-purple-soft)', label: 'Proposal' };
    case 'NEGOTIATION':
      return { hex: 'var(--ide-orange)', soft: 'var(--ide-orange-soft)', label: 'Negotiation' };
    case 'CLOSED_WON':
      return { hex: 'var(--ide-green)', soft: 'var(--ide-green-soft)', label: 'Closed Won' };
    case 'CLOSED_LOST':
      return { hex: 'var(--ide-red)', soft: 'var(--ide-red-soft)', label: 'Closed Lost' };
  }
}

export const NEXT_STAGES: Record<LeadStage, LeadStage[]> = {
  PROSPECT: ['QUALIFIED', 'CLOSED_LOST'],
  QUALIFIED: ['PROPOSAL', 'CLOSED_LOST'],
  PROPOSAL: ['NEGOTIATION', 'CLOSED_WON', 'CLOSED_LOST'],
  NEGOTIATION: ['CLOSED_WON', 'CLOSED_LOST', 'PROPOSAL'],
  CLOSED_WON: [],
  CLOSED_LOST: [],
};
