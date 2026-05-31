/**
 * Notification API client — TSK-057.
 */

import { apiClient } from './client';

export type NotificationType =
  | 'APPROVAL_PENDING'
  | 'APPROVAL_APPROVED'
  | 'APPROVAL_REJECTED'
  | 'PAYROLL_PENDING_APPROVAL'
  | 'PAYROLL_APPROVED'
  | 'PAYROLL_PUBLISHED'
  | 'LEAVE_PENDING_APPROVAL'
  | 'LEAVE_APPROVED'
  | 'LEAVE_REJECTED'
  | 'CONTRACT_EXPIRING'
  | 'CONTRACT_RENEWED'
  | 'TASK_DEADLINE'
  | 'TASK_OVERDUE'
  | 'SEPARATION_PENDING'
  | 'SEPARATION_EXECUTED'
  | 'PROCUREMENT_PENDING'
  | 'PROCUREMENT_APPROVED'
  | 'INVOICE_TRIGGER'
  | 'KPI_DEADLINE'
  | 'SP_ISSUED'
  | 'SP_O_ISSUED'
  | 'CHANGE_REQUEST_PENDING'
  | 'CHANGE_REQUEST_RESOLVED'
  | 'SYSTEM';

export type NotificationPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';

export interface Notification {
  id: string;
  type: NotificationType;
  priority: NotificationPriority;
  title: string;
  body: string | null;
  link_url: string | null;
  meta: Record<string, unknown> | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
  page: number;
  page_size: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface MarkReadResponse {
  id: string;
  read_at: string;
}

export interface MarkAllReadResponse {
  marked_count: number;
}

export async function getUnreadCount(): Promise<UnreadCountResponse> {
  const { data } = await apiClient.get('/notifications/unread-count');
  return data;
}

export async function listNotifications(params: {
  unread_only?: boolean;
  page?: number;
  page_size?: number;
}): Promise<NotificationListResponse> {
  const { data } = await apiClient.get('/notifications', {
    params: {
      unread_only: params.unread_only ?? false,
      page: params.page ?? 1,
      page_size: params.page_size ?? 20,
    },
  });
  return data;
}

export async function markNotificationRead(id: string): Promise<MarkReadResponse> {
  const { data } = await apiClient.post(`/notifications/${id}/read`);
  return data;
}

export async function markAllNotificationsRead(): Promise<MarkAllReadResponse> {
  const { data } = await apiClient.post('/notifications/read-all');
  return data;
}

/** Type metadata for UI badges/icons. */
export const NOTIFICATION_TYPE_META: Record<
  NotificationType,
  { label: string; color: string; icon: string }
> = {
  APPROVAL_PENDING: { label: 'Approval', color: '#FF9500', icon: '⏳' },
  APPROVAL_APPROVED: { label: 'Approved', color: '#34C759', icon: '✓' },
  APPROVAL_REJECTED: { label: 'Rejected', color: '#FF3B30', icon: '✗' },
  PAYROLL_PENDING_APPROVAL: { label: 'Payroll', color: '#FF9500', icon: '💰' },
  PAYROLL_APPROVED: { label: 'Payroll', color: '#34C759', icon: '💰' },
  PAYROLL_PUBLISHED: { label: 'Payroll', color: '#0071E3', icon: '💰' },
  LEAVE_PENDING_APPROVAL: { label: 'Leave', color: '#FF9500', icon: '🏖' },
  LEAVE_APPROVED: { label: 'Leave', color: '#34C759', icon: '🏖' },
  LEAVE_REJECTED: { label: 'Leave', color: '#FF3B30', icon: '🏖' },
  CONTRACT_EXPIRING: { label: 'Contract', color: '#FF9500', icon: '📋' },
  CONTRACT_RENEWED: { label: 'Contract', color: '#34C759', icon: '📋' },
  TASK_DEADLINE: { label: 'Task', color: '#FF9500', icon: '📌' },
  TASK_OVERDUE: { label: 'Task', color: '#FF3B30', icon: '📌' },
  SEPARATION_PENDING: { label: 'Separation', color: '#FF9500', icon: '👋' },
  SEPARATION_EXECUTED: { label: 'Separation', color: '#6E6E73', icon: '👋' },
  PROCUREMENT_PENDING: { label: 'Procurement', color: '#FF9500', icon: '🛒' },
  PROCUREMENT_APPROVED: { label: 'Procurement', color: '#34C759', icon: '🛒' },
  INVOICE_TRIGGER: { label: 'Invoice', color: '#0071E3', icon: '🧾' },
  KPI_DEADLINE: { label: 'KPI', color: '#FF9500', icon: '⭐' },
  SP_ISSUED: { label: 'SP', color: '#FF3B30', icon: '⚠' },
  SP_O_ISSUED: { label: 'SP-O', color: '#FF3B30', icon: '⚠' },
  CHANGE_REQUEST_PENDING: { label: 'Change Req', color: '#FF9500', icon: '🔄' },
  CHANGE_REQUEST_RESOLVED: { label: 'Change Req', color: '#34C759', icon: '🔄' },
  SYSTEM: { label: 'System', color: '#6E6E73', icon: 'ℹ' },
};
