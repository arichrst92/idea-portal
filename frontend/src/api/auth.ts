/**
 * Auth API client — wrappers untuk /api/v1/auth/*
 */

import { apiClient } from './client';

export interface Role {
  id: string;
  code: string;
  name: string;
  level: number;
}

export interface User {
  id: string;
  nik: string;
  email: string | null;
  is_active: boolean;
  last_login_at: string | null;
  roles: Role[];
}

export interface LoginRequest {
  nik: string;
  password: string;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginResponse extends TokenPair {
  user: User;
}

export interface RefreshResponse extends TokenPair {}

export interface ApiError {
  code: string;
  message: string;
}

/**
 * POST /api/v1/auth/login
 * @throws AxiosError dengan response.data.detail = { code, message }
 */
export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', payload);
  return response.data;
}

/**
 * POST /api/v1/auth/refresh
 * Rotate token pair — old refresh token tetap valid sampai expiry (TSK-005 akan tambah revoke).
 */
export async function refreshAccessToken(refreshToken: string): Promise<RefreshResponse> {
  const response = await apiClient.post<RefreshResponse>('/api/v1/auth/refresh', {
    refresh_token: refreshToken,
  });
  return response.data;
}

/**
 * GET /api/v1/auth/me
 * Get current user info dari JWT. Protected endpoint.
 */
export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/api/v1/auth/me');
  return response.data;
}

/**
 * POST /api/v1/auth/logout
 * Revoke refresh token. Butuh valid access token (current user).
 */
export async function logout(refreshToken: string): Promise<{ success: boolean; revoked: boolean }> {
  const response = await apiClient.post<{ success: boolean; revoked: boolean }>(
    '/api/v1/auth/logout',
    { refresh_token: refreshToken },
  );
  return response.data;
}
