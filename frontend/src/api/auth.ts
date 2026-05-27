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

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ApiError {
  code: string;
  message: string;
}

/**
 * POST /api/v1/auth/login
 *
 * @throws AxiosError dengan response.data.detail = { code, message }
 */
export async function login(payload: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', payload);
  return response.data;
}
