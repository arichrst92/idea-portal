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
import OrgChartPage from '@/features/employees/OrgChartPage';
import JobOpeningCreatePage from '@/features/hiring/JobOpeningCreatePage';
import JobOpeningDetailPage from '@/features/hiring/JobOpeningDetailPage';
import JobOpeningListPage from '@/features/hiring/JobOpeningListPage';
import OnboardingDetailPage from '@/features/onboarding/OnboardingDetailPage';
import OnboardingListPage from '@/features/onboarding/OnboardingListPage';
import ContractsListPage from '@/features/contracts/ContractsListPage';
import LeaveListPage from '@/features/leave/LeaveListPage';
import PerformancePage from '@/features/performance/PerformancePage';
import SeparationDetailPage from '@/features/separation/SeparationDetailPage';
import SeparationListPage from '@/features/separation/SeparationListPage';
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
        <Route
          path="/org-chart"
          element={
            <RequireAuth>
              <AppShell><OrgChartPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/hiring"
          element={
            <RequireAuth>
              <AppShell><JobOpeningListPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/hiring/new"
          element={
            <RequireAuth>
              <AppShell><JobOpeningCreatePage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/hiring/:id"
          element={
            <RequireAuth>
              <AppShell><JobOpeningDetailPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/onboarding"
          element={
            <RequireAuth>
              <AppShell><OnboardingListPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/onboarding/:id"
          element={
            <RequireAuth>
              <AppShell><OnboardingDetailPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/separations"
          element={
            <RequireAuth>
              <AppShell><SeparationListPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/separations/:id"
          element={
            <RequireAuth>
              <AppShell><SeparationDetailPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/contracts"
          element={
            <RequireAuth>
              <AppShell><ContractsListPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/leave"
          element={
            <RequireAuth>
              <AppShell><LeaveListPage /></AppShell>
            </RequireAuth>
          }
        />
        <Route
          path="/performance"
          element={
            <RequireAuth>
              <AppShell><PerformancePage /></AppShell>
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default AppRoutes;
