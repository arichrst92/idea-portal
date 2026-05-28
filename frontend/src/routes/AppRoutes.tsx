/**
 * Router config — semua route aplikasi.
 *
 * Sprint 1 (TSK-001): /login + placeholder dashboard.
 * Sprint 1 (TSK-003): ProtectedRoute wrapper untuk RBAC enforcement.
 */

import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from '@/components/AppShell';
import { GlobalSearch } from '@/components/GlobalSearch';
import PermissionMatrixPage from '@/features/admin/PermissionMatrixPage';
import ForgotPasswordPage from '@/features/auth/ForgotPasswordPage';
import LoginPage from '@/features/auth/LoginPage';
import ResetPasswordPage from '@/features/auth/ResetPasswordPage';
import EmployeeCreatePage from '@/features/employees/EmployeeCreatePage';
import EmployeeDetailPage from '@/features/employees/EmployeeDetailPage';
import EmployeeListPage from '@/features/employees/EmployeeListPage';
import SettingsPage from '@/features/settings/SettingsPage';
import { SessionManager } from '@/lib/sessionManager';
import { useAuthStore } from '@/store/auth';

import App from '../App';

/**
 * Placeholder protected route guard. TSK-003 akan tambah role-based check.
 */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <>
      <SessionManager />
      <GlobalSearch />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <AppShell><App /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/admin/permissions"
          element={
            <RequireAuth>
              <AppShell><PermissionMatrixPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <AppShell><SettingsPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/employees"
          element={
            <RequireAuth>
              <AppShell><EmployeeListPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/employees/new"
          element={
            <RequireAuth>
              <AppShell><EmployeeCreatePage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/employees/:nik"
          element={
            <RequireAuth>
              <AppShell><EmployeeDetailPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default AppRoutes;
