import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';

const baseURL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export const apiClient: AxiosInstance = axios.create({
  baseURL: baseURL.replace(/\/api\/v1$/, ''), // strip /api/v1 for root endpoint testing
  timeout: 10_000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor — inject JWT token (Sprint 1+)
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('idea_access_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor — handle 401 → redirect to login (Sprint 1+)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // TODO Sprint 1: implement refresh token flow
      // localStorage.removeItem('idea_access_token');
      // window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);
