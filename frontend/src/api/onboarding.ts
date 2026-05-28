/**
 * Onboarding domain API client — TSK-016.
 */

import { apiClient } from './client';

// ─── Enums ──────────────────────────────────────────────────────

export type TaskCategory =
  | 'HR_DOCUMENTS'
  | 'IT_SETUP'
  | 'TRAINING'
  | 'DEPT_SPECIFIC'
  | 'BUDDY_INTRO'
  | 'COMPLIANCE'
  | 'OTHER';

export type TaskAssignedRole =
  | 'HR'
  | 'IT'
  | 'MANAGER'
  | 'BUDDY'
  | 'EMPLOYEE'
  | 'FINANCE'
  | 'EXECUTIVE';

export type AssignmentStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';

export type TaskCompletionStatus = 'PENDING' | 'DONE' | 'SKIPPED' | 'BLOCKED';

// ─── Types ──────────────────────────────────────────────────────

export interface OnboardingTask {
  id: string;
  template_id: string;
  category: TaskCategory;
  title: string;
  description: string | null;
  instructions: string | null;
  order_index: number;
  default_due_offset_days: number;
  assigned_role: TaskAssignedRole;
  is_required: boolean;
  reference_url: string | null;
  created_at: string;
}

export interface OnboardingTemplate {
  id: string;
  name: string;
  description: string | null;
  target_department_id: string | null;
  target_position_level: number | null;
  estimated_duration_days: number;
  is_active: boolean;
  created_at: string;
  department_name: string | null;
  task_count: number;
  assignment_count: number;
}

export interface OnboardingTemplateDetail extends OnboardingTemplate {
  tasks: OnboardingTask[];
}

export interface TaskCompletion {
  id: string;
  assignment_id: string;
  task_id: string;
  status: TaskCompletionStatus;
  due_date: string | null;
  completed_at: string | null;
  completed_by_user_id: string | null;
  notes: string | null;
  blocker_reason: string | null;
  created_at: string;
  updated_at: string;

  task_title: string | null;
  task_category: TaskCategory | null;
  task_assigned_role: TaskAssignedRole | null;
  task_is_required: boolean | null;
  task_instructions: string | null;
  task_reference_url: string | null;
}

export interface AssignmentListItem {
  id: string;
  employee_id: string;
  template_id: string;
  status: AssignmentStatus;
  started_at: string;
  target_completion_date: string | null;
  completed_at: string | null;
  employee_nik: string | null;
  employee_name: string | null;
  employee_department: string | null;
  template_name: string | null;
  total_tasks: number;
  completed_tasks: number;
  progress_percent: number;
}

export interface AssignmentDetail extends AssignmentListItem {
  assigned_by_user_id: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  completions_by_category: Record<string, TaskCompletion[]>;
}

export interface AssignmentListResponse {
  items: AssignmentListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AssignmentCreateRequest {
  employee_id: string;
  template_id: string;
  started_at?: string;
  target_completion_date?: string;
  notes?: string;
}

export interface TaskCompletionUpdateRequest {
  status: TaskCompletionStatus;
  notes?: string;
  blocker_reason?: string;
}

// ─── Template API ───────────────────────────────────────────────

export async function listTemplates(params: {
  department_id?: string;
  is_active?: boolean;
} = {}): Promise<OnboardingTemplate[]> {
  const r = await apiClient.get<OnboardingTemplate[]>('/api/v1/onboarding/templates', {
    params,
  });
  return r.data;
}

export async function getTemplate(id: string): Promise<OnboardingTemplateDetail> {
  const r = await apiClient.get<OnboardingTemplateDetail>(`/api/v1/onboarding/templates/${id}`);
  return r.data;
}

// ─── Assignment API ─────────────────────────────────────────────

export async function listAssignments(params: {
  employee_id?: string;
  status?: AssignmentStatus;
  page?: number;
  page_size?: number;
} = {}): Promise<AssignmentListResponse> {
  const r = await apiClient.get<AssignmentListResponse>('/api/v1/onboarding/assignments', {
    params: {
      employee_id: params.employee_id || undefined,
      status: params.status || undefined,
      page: params.page ?? 1,
      page_size: params.page_size ?? 50,
    },
  });
  return r.data;
}

export async function getAssignment(id: string): Promise<AssignmentDetail> {
  const r = await apiClient.get<AssignmentDetail>(`/api/v1/onboarding/assignments/${id}`);
  return r.data;
}

export async function createAssignment(data: AssignmentCreateRequest): Promise<AssignmentDetail> {
  const r = await apiClient.post<AssignmentDetail>('/api/v1/onboarding/assignments', data);
  return r.data;
}

// ─── Task completion ────────────────────────────────────────────

export async function updateCompletion(
  id: string,
  data: TaskCompletionUpdateRequest,
): Promise<TaskCompletion> {
  const r = await apiClient.patch<TaskCompletion>(`/api/v1/onboarding/completions/${id}`, data);
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export const CATEGORY_META: Record<TaskCategory, { label: string; icon: string; color: string }> = {
  HR_DOCUMENTS: { label: 'HR Documents', icon: '📋', color: 'var(--ide-blue)' },
  IT_SETUP: { label: 'IT Setup', icon: '💻', color: 'var(--ide-purple)' },
  TRAINING: { label: 'Training & Orientation', icon: '🎓', color: 'var(--ide-orange)' },
  DEPT_SPECIFIC: { label: 'Department Specific', icon: '⚙️', color: 'var(--ide-teal)' },
  BUDDY_INTRO: { label: 'Buddy & Team Intro', icon: '🤝', color: 'var(--ide-green)' },
  COMPLIANCE: { label: 'Compliance', icon: '📜', color: 'var(--ide-red)' },
  OTHER: { label: 'Other', icon: '📌', color: 'var(--ide-ink3)' },
};

export const ROLE_LABELS: Record<TaskAssignedRole, string> = {
  HR: 'HR',
  IT: 'IT',
  MANAGER: 'Manager',
  BUDDY: 'Buddy',
  EMPLOYEE: 'Employee',
  FINANCE: 'Finance',
  EXECUTIVE: 'Executive',
};

export function assignmentStatusColor(s: AssignmentStatus): { className: string; label: string } {
  switch (s) {
    case 'NOT_STARTED':
      return { className: 'ide-tag-gray', label: 'Not Started' };
    case 'IN_PROGRESS':
      return { className: 'ide-tag-blue', label: 'In Progress' };
    case 'COMPLETED':
      return { className: 'ide-tag-green', label: 'Completed' };
    case 'CANCELLED':
      return { className: 'ide-tag-red', label: 'Cancelled' };
  }
}
