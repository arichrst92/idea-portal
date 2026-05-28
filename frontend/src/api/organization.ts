/**
 * Organization domain API client — TSK-013 (M1.2).
 *
 * Endpoints: /api/v1/employees + /api/v1/departments + /api/v1/positions
 *
 * Per backend schemas: EmployeeListItem, EmployeeOut, DepartmentOut, PositionOut.
 */

import { apiClient } from './client';

// ─── Enums (mirror backend models) ──────────────────────────────

export type EmployeeType = 'A' | 'B' | 'C'; // A=internal, B=outsource-IDEA, C=outsource-eksternal

export type EmployeeStatus =
  | 'PROBATION'
  | 'ACTIVE'
  | 'ON_LEAVE'
  | 'RESIGNED'
  | 'TERMINATED'
  | 'ALUMNI';

// ─── Types ──────────────────────────────────────────────────────

export interface Department {
  id: string;
  code: string;
  name: string;
  description: string | null;
  head_user_id: string | null;
  created_at: string;
  employee_count: number | null;
}

export interface Position {
  id: string;
  code: string;
  name: string;
  department_id: string;
  level: number;
  salary_range_min: string | null;
  salary_range_max: string | null;
  created_at: string;
  department_name: string | null;
}

export interface EmployeeListItem {
  nik: string;
  full_name: string;
  email: string | null;
  photo_url: string | null;
  employee_type: EmployeeType;
  status: EmployeeStatus;
  department_name: string | null;
  position_name: string | null;
  supervisor_name: string | null;
  joined_date: string | null;
}

export interface EmployeeDetail {
  id: string;
  nik: string;
  email: string | null;
  full_name: string;
  photo_url: string | null;
  date_of_birth: string | null;
  gender: string | null;
  phone_number: string | null;
  address: string | null;
  emergency_contact: string | null;
  employee_type: EmployeeType;
  status: EmployeeStatus;
  department_id: string | null;
  position_id: string | null;
  supervisor_id: string | null;
  joined_date: string | null;
  probation_end_date: string | null;
  last_working_day: string | null;
  bank_name: string | null;
  bank_account: string | null;
  npwp: string | null;
  department_name: string | null;
  position_name: string | null;
  supervisor_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface EmployeeListResponse {
  items: EmployeeListItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface EmployeeFilters {
  q?: string;
  department_id?: string;
  position_id?: string;
  employee_type?: EmployeeType;
  status?: EmployeeStatus;
  supervisor_id?: string;
  page?: number;
  page_size?: number;
}

export interface EmployeeCreateRequest {
  nik: string;
  email?: string | null;
  full_name: string;
  photo_url?: string | null;
  date_of_birth?: string | null;
  gender?: string | null;
  phone_number?: string | null;
  address?: string | null;
  emergency_contact?: string | null;
  employee_type: EmployeeType;
  status?: EmployeeStatus;
  department_id?: string | null;
  position_id?: string | null;
  supervisor_id?: string | null;
  joined_date?: string | null;
  probation_end_date?: string | null;
  bank_name?: string | null;
  bank_account?: string | null;
  npwp?: string | null;
  initial_password?: string;
  role_codes?: string[];
}

export type EmployeeUpdateRequest = Partial<
  Omit<EmployeeCreateRequest, 'nik' | 'employee_type' | 'initial_password' | 'role_codes'>
>;

export interface OrgChange {
  id: string;
  employee_id: string;
  change_type: 'PROMOTION' | 'MUTATION' | string;
  effective_date: string;
  before_snapshot: Record<string, unknown> | null;
  after_snapshot: Record<string, unknown> | null;
  reason: string | null;
  initiated_by_user_id: string | null;
  approved_by_user_id: string | null;
  created_at: string;
}

// ─── Departments ────────────────────────────────────────────────

export async function listDepartments(): Promise<Department[]> {
  const r = await apiClient.get<Department[]>('/api/v1/departments');
  return r.data;
}

// ─── Positions ──────────────────────────────────────────────────

export async function listPositions(departmentId?: string): Promise<Position[]> {
  const r = await apiClient.get<Position[]>('/api/v1/positions', {
    params: departmentId ? { department_id: departmentId } : undefined,
  });
  return r.data;
}

// ─── Employees ──────────────────────────────────────────────────

export async function listEmployees(filters: EmployeeFilters = {}): Promise<EmployeeListResponse> {
  const r = await apiClient.get<EmployeeListResponse>('/api/v1/employees', {
    params: {
      q: filters.q || undefined,
      department_id: filters.department_id || undefined,
      position_id: filters.position_id || undefined,
      employee_type: filters.employee_type || undefined,
      status: filters.status || undefined,
      supervisor_id: filters.supervisor_id || undefined,
      page: filters.page ?? 1,
      page_size: filters.page_size ?? 25,
    },
  });
  return r.data;
}

export async function getEmployee(nik: string): Promise<EmployeeDetail> {
  const r = await apiClient.get<EmployeeDetail>(`/api/v1/employees/${nik}`);
  return r.data;
}

export async function createEmployee(data: EmployeeCreateRequest): Promise<EmployeeDetail> {
  const r = await apiClient.post<EmployeeDetail>('/api/v1/employees', data);
  return r.data;
}

export async function updateEmployee(
  nik: string,
  data: EmployeeUpdateRequest,
): Promise<EmployeeDetail> {
  const r = await apiClient.patch<EmployeeDetail>(`/api/v1/employees/${nik}`, data);
  return r.data;
}

export async function softDeleteEmployee(nik: string): Promise<EmployeeDetail> {
  const r = await apiClient.delete<EmployeeDetail>(`/api/v1/employees/${nik}`);
  return r.data;
}

export async function promoteEmployee(
  nik: string,
  payload: { new_position_id: string; effective_date: string; new_salary?: string; reason: string },
): Promise<OrgChange> {
  const r = await apiClient.post<OrgChange>(`/api/v1/employees/${nik}/promote`, payload);
  return r.data;
}

export async function mutateEmployee(
  nik: string,
  payload: {
    new_department_id?: string;
    new_position_id?: string;
    new_supervisor_id?: string;
    effective_date: string;
    reason: string;
  },
): Promise<OrgChange> {
  const r = await apiClient.post<OrgChange>(`/api/v1/employees/${nik}/mutate`, payload);
  return r.data;
}

export async function getEmployeeHistory(nik: string, limit = 50): Promise<OrgChange[]> {
  const r = await apiClient.get<OrgChange[]>(`/api/v1/employees/${nik}/history`, {
    params: { limit },
  });
  return r.data;
}

// ─── Helpers ────────────────────────────────────────────────────

/** Map status backend → tag color class untuk UI (tokens.css). */
export function employeeStatusColor(status: EmployeeStatus): {
  className: string;
  label: string;
} {
  switch (status) {
    case 'ACTIVE':
      return { className: 'ide-tag-green', label: 'Active' };
    case 'PROBATION':
      return { className: 'ide-tag-blue', label: 'Probation' };
    case 'ON_LEAVE':
      return { className: 'ide-tag-orange', label: 'On Leave' };
    case 'RESIGNED':
      return { className: 'ide-tag-gray', label: 'Resigned' };
    case 'TERMINATED':
      return { className: 'ide-tag-red', label: 'Terminated' };
    case 'ALUMNI':
      return { className: 'ide-tag-gray', label: 'Alumni' };
    default:
      return { className: 'ide-tag-gray', label: status };
  }
}

/** Map employee type → label + color. */
export function employeeTypeColor(t: EmployeeType): { className: string; label: string } {
  switch (t) {
    case 'A':
      return { className: 'ide-tag-blue', label: 'Internal' };
    case 'B':
      return { className: 'ide-tag-purple', label: 'Outsource-IDEA' };
    case 'C':
      return { className: 'ide-tag-orange', label: 'Outsource-Ext' };
    default:
      return { className: 'ide-tag-gray', label: t };
  }
}

/** Generate gradient color berdasarkan NIK/nama untuk avatar bg. */
export function avatarGradient(seed: string): string {
  const palette = [
    'linear-gradient(135deg,#007AFF,#5E5CE6)',
    'linear-gradient(135deg,#AF52DE,#7C3AED)',
    'linear-gradient(135deg,#30D158,#0BA956)',
    'linear-gradient(135deg,#FF9F0A,#FF6B35)',
    'linear-gradient(135deg,#FF453A,#E83632)',
    'linear-gradient(135deg,#32D2F2,#1FA9C8)',
    'linear-gradient(135deg,#BF5AF2,#9333EA)',
    'linear-gradient(135deg,#5856D6,#3B36A8)',
  ];
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) >>> 0;
  return palette[hash % palette.length];
}

/** Get initials dari full_name (max 2 chars). */
export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
