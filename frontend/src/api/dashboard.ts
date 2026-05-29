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
