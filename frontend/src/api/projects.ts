/**
 * Project domain API client — TSK-022.
 */

import { apiClient } from './client';

export type ProjectType = 'CLIENT' | 'INTERNAL' | 'RND';
export type ProjectStatus = 'DRAFT' | 'ACTIVE' | 'ON_HOLD' | 'COMPLETED' | 'TERMINATED';
export type TaskStatus = 'BACKLOG' | 'TODO' | 'IN_PROGRESS' | 'IN_REVIEW' | 'DONE' | 'BLOCKED';
export type TaskPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export interface ProjectListItem {
  id: string;
  code: string;
  name: string;
  type: ProjectType;
  status: ProjectStatus;
  pm_nik: string | null;
  client_name: string | null;
  start_date: string | null;
  end_date: string | null;
  contract_value: string | null;
  currency: string;
  member_count: number;
  overall_progress_pct: string | null;
}

export interface Project extends ProjectListItem {
  description: string | null;
  pm_user_id: string | null;
  client_id: string | null;
  created_at: string;
  updated_at: string;
  milestone_count: number;
  completed_milestones: number;
}

export interface ProjectListResponse {
  items: ProjectListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Member {
  id: string;
  project_id: string;
  employee_id: string;
  role: string | null;
  allocation_pct: string;
  start_date: string;
  end_date: string | null;
  employee_nik: string | null;
  employee_name: string | null;
}

export interface Milestone {
  id: string;
  project_id: string;
  name: string;
  target_date: string;
  completed_at: string | null;
  progress_pct: string;
  is_overdue: boolean;
}

export interface Task {
  id: string;
  project_id: string;
  milestone_id: string | null;
  title: string;
  description: string | null;
  assignee_id: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  created_at: string;
  assignee_nik: string | null;
  assignee_name: string | null;
  milestone_name: string | null;
}

export interface Invoice {
  id: string;
  project_id: string;
  invoice_no: string;
  termin_pct: string;
  amount: string;
  trigger_milestone_id: string | null;
  trigger_date: string | null;
  status: string;
  notified_finance_at: string | null;
  paid_amount: string;
  paid_at: string | null;
  created_at: string;
  milestone_name: string | null;
}

// ─── Projects API ────────────────────────────────────────────────

export async function listProjects(params: {
  type?: ProjectType;
  status?: ProjectStatus;
  page?: number;
  page_size?: number;
} = {}): Promise<ProjectListResponse> {
  const r = await apiClient.get<ProjectListResponse>('/api/v1/projects', { params });
  return r.data;
}

export async function getProject(id: string): Promise<Project> {
  const r = await apiClient.get<Project>(`/api/v1/projects/${id}`);
  return r.data;
}

export async function createProject(data: {
  code: string;
  name: string;
  type: ProjectType;
  description?: string;
  pm_user_id?: string;
  client_id?: string;
  start_date?: string;
  end_date?: string;
  contract_value?: string;
  currency?: string;
}): Promise<Project> {
  const r = await apiClient.post<Project>('/api/v1/projects', data);
  return r.data;
}

export async function activateProject(id: string): Promise<Project> {
  const r = await apiClient.post<Project>(`/api/v1/projects/${id}/activate`);
  return r.data;
}

export async function closeProject(
  id: string,
  new_status: 'COMPLETED' | 'TERMINATED',
  reason: string,
): Promise<Project> {
  const r = await apiClient.post<Project>(`/api/v1/projects/${id}/close`, {
    new_status,
    reason,
  });
  return r.data;
}

// ─── Members ────────────────────────────────────────────────────

export async function listMembers(project_id: string): Promise<Member[]> {
  const r = await apiClient.get<Member[]>(`/api/v1/projects/${project_id}/members`);
  return r.data;
}

export async function addMember(
  project_id: string,
  data: { employee_id: string; role?: string; allocation_pct: number; start_date: string; end_date?: string },
): Promise<Member> {
  const r = await apiClient.post<Member>(`/api/v1/projects/${project_id}/members`, data);
  return r.data;
}

export async function removeMember(member_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/members/${member_id}`);
}

// ─── Milestones ─────────────────────────────────────────────────

export async function listMilestones(project_id: string): Promise<Milestone[]> {
  const r = await apiClient.get<Milestone[]>(`/api/v1/projects/${project_id}/milestones`);
  return r.data;
}

export async function createMilestone(
  project_id: string,
  data: { name: string; target_date: string },
): Promise<Milestone> {
  const r = await apiClient.post<Milestone>(`/api/v1/projects/${project_id}/milestones`, data);
  return r.data;
}

export async function updateMilestone(
  milestone_id: string,
  data: { name?: string; target_date?: string; progress_pct?: number; completed_at?: string },
): Promise<Milestone> {
  const r = await apiClient.patch<Milestone>(`/api/v1/projects/milestones/${milestone_id}`, data);
  return r.data;
}

// ─── Tasks ──────────────────────────────────────────────────────

export async function listTasks(project_id: string, status?: TaskStatus): Promise<Task[]> {
  const r = await apiClient.get<Task[]>(`/api/v1/projects/${project_id}/tasks`, {
    params: { status },
  });
  return r.data;
}

export async function createTask(
  project_id: string,
  data: {
    title: string;
    description?: string;
    milestone_id?: string;
    assignee_id?: string;
    status?: TaskStatus;
    priority?: TaskPriority;
    due_date?: string;
  },
): Promise<Task> {
  const r = await apiClient.post<Task>(`/api/v1/projects/${project_id}/tasks`, data);
  return r.data;
}

export async function updateTask(
  task_id: string,
  data: Partial<{
    title: string;
    description: string;
    milestone_id: string;
    assignee_id: string;
    status: TaskStatus;
    priority: TaskPriority;
    due_date: string;
  }>,
): Promise<Task> {
  const r = await apiClient.patch<Task>(`/api/v1/projects/tasks/${task_id}`, data);
  return r.data;
}

// ─── Invoices ───────────────────────────────────────────────────

export async function listInvoices(project_id: string): Promise<Invoice[]> {
  const r = await apiClient.get<Invoice[]>(`/api/v1/projects/${project_id}/invoices`);
  return r.data;
}

export async function createInvoice(
  project_id: string,
  data: { invoice_no: string; termin_pct: number; amount: number; trigger_milestone_id?: string },
): Promise<Invoice> {
  const r = await apiClient.post<Invoice>(`/api/v1/projects/${project_id}/invoices`, data);
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

export function projectTypeColor(t: ProjectType): { className: string; label: string } {
  switch (t) {
    case 'CLIENT':
      return { className: 'ide-tag-green', label: 'Client' };
    case 'INTERNAL':
      return { className: 'ide-tag-blue', label: 'Internal' };
    case 'RND':
      return { className: 'ide-tag-purple', label: 'R&D' };
  }
}

export function projectStatusColor(s: ProjectStatus): { className: string; label: string } {
  switch (s) {
    case 'DRAFT':
      return { className: 'ide-tag-gray', label: 'Draft' };
    case 'ACTIVE':
      return { className: 'ide-tag-green', label: 'Active' };
    case 'ON_HOLD':
      return { className: 'ide-tag-orange', label: 'On Hold' };
    case 'COMPLETED':
      return { className: 'ide-tag-blue', label: 'Completed' };
    case 'TERMINATED':
      return { className: 'ide-tag-red', label: 'Terminated' };
  }
}

export const TASK_STATUSES: TaskStatus[] = [
  'BACKLOG',
  'TODO',
  'IN_PROGRESS',
  'IN_REVIEW',
  'DONE',
  'BLOCKED',
];

export function taskStatusColor(s: TaskStatus): string {
  switch (s) {
    case 'BACKLOG':
      return 'var(--ide-ink3)';
    case 'TODO':
      return 'var(--ide-blue)';
    case 'IN_PROGRESS':
      return 'var(--ide-orange)';
    case 'IN_REVIEW':
      return 'var(--ide-purple)';
    case 'DONE':
      return 'var(--ide-green)';
    case 'BLOCKED':
      return 'var(--ide-red)';
  }
}

export function priorityColor(p: TaskPriority): string {
  switch (p) {
    case 'LOW':
      return 'var(--ide-ink3)';
    case 'MEDIUM':
      return 'var(--ide-blue)';
    case 'HIGH':
      return 'var(--ide-orange)';
    case 'CRITICAL':
      return 'var(--ide-red)';
  }
}
