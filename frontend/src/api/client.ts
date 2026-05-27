/**
 * Axios HTTP client dengan auto JWT attach + auto-refresh on 401.
 *
 * TSK-001: dummy interceptor.
 * TSK-002: real JWT integration dengan Zustand store + refresh flow.
 * TSK-005: tambah idle session timer + logout broadcast (future).
 */

import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';

import { refreshAccessToken } from './auth';
import { useAuthStore } from '@/store/auth';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const apiClient: AxiosInstance = axios.create({
  baseURL: baseURL.replace(/\/api\/v1$/, ''),
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Request interceptor: auto-attach JWT dari Zustand store ──────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const accessToken = useAuthStore.getState().accessToken;
  if (accessToken && config.headers) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// ─── Response interceptor: handle 401 → attempt refresh → retry ───
//
// State machine:
// 1. Original request fails dengan 401
// 2. Cek apakah ini retry attempt → kalau iya, langsung redirect login
// 3. Coba refresh token via /auth/refresh
// 4. Berhasil → update store, retry original request dengan token baru
// 5. Gagal → clear store + redirect login
//
// Concurrent 401 handling: queue semua request lain selama refresh in-flight,
// retry semua sekaligus setelah refresh selesai.

let isRefreshing = false;
let pendingQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null = null) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (token) resolve(token);
    else reject(error);
  });
  pendingQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as AxiosRequestConfig & { _retry?: boolean };

    // Skip refresh untuk request ke /auth/login dan /auth/refresh sendiri
    const skipPaths = ['/api/v1/auth/login', '/api/v1/auth/refresh'];
    const requestPath = originalRequest?.url ?? '';
    if (skipPaths.some((p) => requestPath.endsWith(p))) {
      return Promise.reject(error);
    }

    // Bukan 401, atau sudah retry — propagate error
    if (error.response?.status !== 401 || originalRequest._retry) {
      // Hard fail: clear auth + redirect (tapi hanya jika 401 di second attempt)
      if (error.response?.status === 401 && originalRequest._retry) {
        useAuthStore.getState().clearAuth();
        if (window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
      }
      return Promise.reject(error);
    }

    // Jika refresh sedang in-flight, queue request ini
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      })
        .then((newToken) => {
          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
          }
          return apiClient.request(originalRequest);
        })
        .catch((err) => Promise.reject(err));
    }

    // Start refresh flow
    originalRequest._retry = true;
    isRefreshing = true;

    const refreshToken = useAuthStore.getState().refreshToken;
    if (!refreshToken) {
      isRefreshing = false;
      useAuthStore.getState().clearAuth();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }

    try {
      const newTokens = await refreshAccessToken(refreshToken);
      useAuthStore.getState().setTokens(newTokens.access_token, newTokens.refresh_token);
      processQueue(null, newTokens.access_token);

      // Retry original request dengan token baru
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${newTokens.access_token}`;
      }
      return apiClient.request(originalRequest);
    } catch (refreshError) {
      processQueue(refreshError, null);
      useAuthStore.getState().clearAuth();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
      return Promise.reject(refreshError);
    } finally {
      isRefreshing = false;
    }
  },
);
