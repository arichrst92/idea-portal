/**
 * Admin API client — endpoint untuk Executive Portal (Direktur/Wakil only).
 */

import { apiClient } from './client';

export interface PermissionItem {
  id: string;
  code: string;
  resource: string;
  action: string;
  description: string | null;
}

export interface RoleItem {
  id: string;
  code: string;
  name: string;
  level: number;
  is_executive: boolean;
  description: string | null;
  permission_ids: string[];
}

export interface PermissionMatrix {
  permissions: PermissionItem[];
  roles: RoleItem[];
}

export async function getPermissionMatrix(): Promise<PermissionMatrix> {
  const response = await apiClient.get<PermissionMatrix>('/api/v1/admin/permissions/matrix');
  return response.data;
}

export async function toggleRolePermission(
  roleId: string,
  permissionCode: string,
  grant: boolean,
): Promise<{ message: string; action: string }> {
  const response = await apiClient.patch<{ message: string; action: string }>(
    `/api/v1/admin/roles/${roleId}/permissions`,
    { permission_code: permissionCode, grant },
  );
  return response.data;
}

export async function unlockUserAccount(nik: string): Promise<{ success: boolean; message: string; was_locked: boolean }> {
  const response = await apiClient.post<{ success: boolean; message: string; was_locked: boolean }>(
    `/api/v1/admin/users/${encodeURIComponent(nik)}/unlock`,
  );
  return response.data;
}
