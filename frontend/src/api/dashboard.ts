/**
 * Dashboard API client — TSK-025.
 *
 * Aggregate stats dari 9 domain untuk Executive Dashboard.
 */

import { apiClient } from './client';

export interface DashboardOverview {
  as_of: string;
  employees: {
    total: number;
    by_status: Record<string, number>;
    by_type: Record<string, number>;
    by_department: { code: string; name: string; count: number }[];
  };
  contracts: {
    expiring_30d: number;
    expired_unrenewed: number;
  };
  hiring: {
    openings_open: number;
    openings_pending_approval: number;
    applications_active: number;
  };
  onboarding: {
    active_assignments: number;
  };
  separation: {
    pending_or_approved: number;
  };
  leave: {
    pending_approval: number;
  };
  projects: {
    active: number;
    total: number;
    total_contract_value: number;
  };
  finance: {
    reimb_pending: number;
    reimb_ready_to_transfer: number;
    reimb_total_amount: number;
    proc_pending: number;
  };
  sales: {
    pipeline_value: number;
    closed_won_ytd: number;
    total_leads: number;
    commissions_pending_amount: number;
  };
  performance: {
    warning_letters_total: number;
    latest_period: {
      year: number;
      month: number;
      distribution: { GREEN: number; YELLOW: number; ORANGE: number; RED: number };
      total_assessed: number;
    } | null;
  };
}

export interface RecentActivityItem {
  id: string;
  timestamp: string;
  actor_nik: string | null;
  actor_persona: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
}

export async function fetchDashboardOverview(): Promise<DashboardOverview> {
  const res = await apiClient.get<DashboardOverview>('/api/v1/dashboard/overview');
  return res.data;
}

export async function fetchRecentActivity(limit = 20): Promise<RecentActivityItem[]> {
  const res = await apiClient.get<RecentActivityItem[]>('/api/v1/dashboard/recent-activity', {
    params: { limit },
  });
  return res.data;
}

// ─── EBITDA (TSK-151) ───────────────────────────────────────────

export interface EbitdaMonth {
  year: number;
  month: number;
  label: string;
  revenue: number;
  revenue_invoice: number;
  revenue_outsource: number;
  cost: number;
  cost_payroll: number;
  cost_reimb: number;
  cost_proc: number;
  ebitda: number;
  margin_pct: number;
}

export interface EbitdaResponse {
  months: EbitdaMonth[];
  summary: {
    total_revenue: number;
    total_cost: number;
    total_ebitda: number;
    avg_margin_pct: number;
    period_count: number;
  };
}

export async function fetchEbitda(months: number = 12): Promise<EbitdaResponse> {
  const res = await apiClient.get<EbitdaResponse>('/api/v1/dashboard/ebitda', {
    params: { months },
  });
  return res.data;
}

// ─── People Performance (TSK-152) ──────────────────────────────

export interface DeptAvg {
  code: string;
  name: string;
  avg_score: number;
  employee_count: number;
  color: 'GREEN' | 'YELLOW' | 'ORANGE' | 'RED';
}

export interface PerformerItem {
  employee_id: string;
  nik: string;
  name: string;
  final_score: number;
  dept_code: string | null;
  dept_name: string | null;
}

export interface PeoplePerformanceResponse {
  period: { id: string; year: number; month: number; label: string } | null;
  distribution: { GREEN: number; YELLOW: number; ORANGE: number; RED: number };
  dept_avg: DeptAvg[];
  top_performers: PerformerItem[];
  bottom_performers: PerformerItem[];
  summary: {
    total_assessed: number;
    avg_score: number;
    median_score: number;
    std_dev: number;
    min_score?: number;
    max_score?: number;
  };
}

export async function fetchPeoplePerformance(): Promise<PeoplePerformanceResponse> {
  const res = await apiClient.get<PeoplePerformanceResponse>('/api/v1/dashboard/people-performance');
  return res.data;
}
