/**
 * Project domain API client — TSK-022, TSK-022B, TSK-022C.
 *
 * Hierarki: Project > Phase > Epic > Task > Subtask + Comments.
 * Milestone = alias backward-compat (sama dengan Phase).
 */

import { apiClient } from './client';

export type ProjectType = 'CLIENT' | 'INTERNAL' | 'RND';
export type ProjectStatus = 'DRAFT' | 'ACTIVE' | 'ON_HOLD' | 'COMPLETED' | 'TERMINATED';
export type PhaseStatus = 'PLANNED' | 'IN_PROGRESS' | 'COMPLETED' | 'CANCELLED';
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
  phase_count: number;
  completed_phases: number;
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

export interface Phase {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  order_index: number;
  target_date: string | null;
  completed_at: string | null;
  status: PhaseStatus;
  progress_pct: string;
  is_overdue: boolean;
  epic_count: number;
}

// Backward-compat alias
export type Milestone = Phase;

export interface Epic {
  id: string;
  phase_id: string;
  project_id: string;
  name: string;
  description: string | null;
  order_index: number;
  status: string;
  color: string | null;
  task_count: number;
  completed_task_count: number;
}

export interface Task {
  id: string;
  project_id: string;
  epic_id: string | null;
  slug: string;
  title: string;
  description: string | null;
  assignee_id: string | null;
  status: TaskStatus;
  priority: TaskPriority;
  story_points: number | null;
  due_date: string | null;
  created_at: string;
  updated_at: string;
  assignee_nik: string | null;
  assignee_name: string | null;
  epic_name: string | null;
  phase_name: string | null;
  subtask_count: number;
  completed_subtask_count: number;
  comment_count: number;
}

export interface Subtask {
  id: string;
  task_id: string;
  slug: string;
  title: string;
  description: string | null;
  assignee_id: string | null;
  status: TaskStatus;
  story_points: number | null;
  due_date: string | null;
  order_index: number;
  created_at: string;
  updated_at: string;
  assignee_nik: string | null;
  assignee_name: string | null;
  comment_count: number;
}

export interface Comment {
  id: string;
  author_user_id: string;
  body: string;
  created_at: string;
  updated_at: string;
  author_nik: string | null;
  author_name: string | null;
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

// ─── Phase API (replaces Milestone) ─────────────────────────────

export async function listPhases(project_id: string): Promise<Phase[]> {
  const r = await apiClient.get<Phase[]>(`/api/v1/projects/${project_id}/phases`);
  return r.data;
}

export async function createPhase(
  project_id: string,
  data: { name: string; description?: string; target_date?: string; order_index?: number },
): Promise<Phase> {
  const r = await apiClient.post<Phase>(`/api/v1/projects/${project_id}/phases`, data);
  return r.data;
}

export async function updatePhase(
  phase_id: string,
  data: Partial<{
    name: string;
    description: string;
    target_date: string;
    order_index: number;
    status: PhaseStatus;
    progress_pct: number;
    completed_at: string;
  }>,
): Promise<Phase> {
  const r = await apiClient.patch<Phase>(`/api/v1/projects/phases/${phase_id}`, data);
  return r.data;
}

export async function deletePhase(phase_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/phases/${phase_id}`);
}

// Backward-compat aliases (deprecated)
export const listMilestones = listPhases;
export const createMilestone = createPhase;
export async function updateMilestone(
  milestone_id: string,
  data: Partial<{ name: string; target_date: string; progress_pct: number; completed_at: string }>,
): Promise<Phase> {
  return updatePhase(milestone_id, data as any);
}

// ─── Epic API ──────────────────────────────────────────────────

export async function listPhaseEpics(phase_id: string): Promise<Epic[]> {
  const r = await apiClient.get<Epic[]>(`/api/v1/projects/phases/${phase_id}/epics`);
  return r.data;
}

export async function listProjectEpics(project_id: string): Promise<Epic[]> {
  const r = await apiClient.get<Epic[]>(`/api/v1/projects/${project_id}/epics`);
  return r.data;
}

export async function createEpic(
  phase_id: string,
  data: { name: string; description?: string; color?: string; order_index?: number },
): Promise<Epic> {
  const r = await apiClient.post<Epic>(`/api/v1/projects/phases/${phase_id}/epics`, data);
  return r.data;
}

export async function updateEpic(
  epic_id: string,
  data: Partial<{ name: string; description: string; color: string; order_index: number; status: string }>,
): Promise<Epic> {
  const r = await apiClient.patch<Epic>(`/api/v1/projects/epics/${epic_id}`, data);
  return r.data;
}

export async function deleteEpic(epic_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/epics/${epic_id}`);
}

// ─── Tasks ──────────────────────────────────────────────────────

export async function listTasks(
  project_id: string,
  params: { epic_id?: string; status?: TaskStatus } = {},
): Promise<Task[]> {
  const r = await apiClient.get<Task[]>(`/api/v1/projects/${project_id}/tasks`, { params });
  return r.data;
}

export async function getTask(task_id: string): Promise<Task> {
  const r = await apiClient.get<Task>(`/api/v1/projects/tasks/${task_id}`);
  return r.data;
}

export async function createTask(
  project_id: string,
  data: {
    title: string;
    description?: string;
    epic_id?: string;
    assignee_id?: string;
    status?: TaskStatus;
    priority?: TaskPriority;
    story_points?: number;
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
    epic_id: string;
    assignee_id: string;
    status: TaskStatus;
    priority: TaskPriority;
    story_points: number;
    due_date: string;
  }>,
): Promise<Task> {
  const r = await apiClient.patch<Task>(`/api/v1/projects/tasks/${task_id}`, data);
  return r.data;
}

export async function deleteTask(task_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/tasks/${task_id}`);
}

// ─── Subtasks ──────────────────────────────────────────────────

export async function listSubtasks(task_id: string): Promise<Subtask[]> {
  const r = await apiClient.get<Subtask[]>(`/api/v1/projects/tasks/${task_id}/subtasks`);
  return r.data;
}

export async function createSubtask(
  task_id: string,
  data: {
    title: string;
    description?: string;
    assignee_id?: string;
    status?: TaskStatus;
    story_points?: number;
    due_date?: string;
    order_index?: number;
  },
): Promise<Subtask> {
  const r = await apiClient.post<Subtask>(`/api/v1/projects/tasks/${task_id}/subtasks`, data);
  return r.data;
}

export async function updateSubtask(
  subtask_id: string,
  data: Partial<{
    title: string;
    description: string;
    assignee_id: string;
    status: TaskStatus;
    story_points: number;
    due_date: string;
    order_index: number;
  }>,
): Promise<Subtask> {
  const r = await apiClient.patch<Subtask>(`/api/v1/projects/subtasks/${subtask_id}`, data);
  return r.data;
}

export async function deleteSubtask(subtask_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/subtasks/${subtask_id}`);
}

// ─── Comments (markdown) ───────────────────────────────────────

export async function listTaskComments(task_id: string): Promise<Comment[]> {
  const r = await apiClient.get<Comment[]>(`/api/v1/projects/tasks/${task_id}/comments`);
  return r.data;
}

export async function createTaskComment(task_id: string, body: string): Promise<Comment> {
  const r = await apiClient.post<Comment>(`/api/v1/projects/tasks/${task_id}/comments`, { body });
  return r.data;
}

export async function updateTaskComment(comment_id: string, body: string): Promise<Comment> {
  const r = await apiClient.patch<Comment>(`/api/v1/projects/task-comments/${comment_id}`, { body });
  return r.data;
}

export async function deleteTaskComment(comment_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/task-comments/${comment_id}`);
}

export async function listSubtaskComments(subtask_id: string): Promise<Comment[]> {
  const r = await apiClient.get<Comment[]>(`/api/v1/projects/subtasks/${subtask_id}/comments`);
  return r.data;
}

export async function createSubtaskComment(subtask_id: string, body: string): Promise<Comment> {
  const r = await apiClient.post<Comment>(`/api/v1/projects/subtasks/${subtask_id}/comments`, { body });
  return r.data;
}

export async function updateSubtaskComment(comment_id: string, body: string): Promise<Comment> {
  const r = await apiClient.patch<Comment>(`/api/v1/projects/subtask-comments/${comment_id}`, { body });
  return r.data;
}

export async function deleteSubtaskComment(comment_id: string): Promise<void> {
  await apiClient.delete(`/api/v1/projects/subtask-comments/${comment_id}`);
}

// ─── Task Deadline (TSK-075) ───────────────────────────────────

export interface DueTaskItem {
  task_id: string;
  slug: string;
  title: string;
  due_date: string;
  status: TaskStatus;
  project_id: string;
  is_overdue: boolean;
  days_until_due: number;
}

export interface MyTasksDueSummary {
  overdue_count: number;
  due_h1_count: number;
  due_h3_count: number;
  items: DueTaskItem[];
}

export async function getMyTasksDueSummary(): Promise<MyTasksDueSummary> {
  const r = await apiClient.get<MyTasksDueSummary>('/api/v1/projects/my-tasks-due-summary');
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
      return 'var(--ide-ink3, #6e6e73)';
    case 'TODO':
      return 'var(--ide-blue, #0071E3)';
    case 'IN_PROGRESS':
      return 'var(--ide-orange, #FF9500)';
    case 'IN_REVIEW':
      return 'var(--ide-purple, #AF52DE)';
    case 'DONE':
      return 'var(--ide-green, #34C759)';
    case 'BLOCKED':
      return 'var(--ide-red, #FF3B30)';
  }
}

export function priorityColor(p: TaskPriority): string {
  switch (p) {
    case 'LOW':
      return 'var(--ide-ink3, #6e6e73)';
    case 'MEDIUM':
      return 'var(--ide-blue, #0071E3)';
    case 'HIGH':
      return 'var(--ide-orange, #FF9500)';
    case 'CRITICAL':
      return 'var(--ide-red, #FF3B30)';
  }
}
