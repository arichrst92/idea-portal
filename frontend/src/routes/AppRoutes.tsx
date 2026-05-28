/**
 * Router config — semua route aplikasi.
 *
 * Sprint 1 (TSK-001): /login + placeholder dashboard.
 * Sprint 1 (TSK-003): ProtectedRoute wrapper untuk RBAC enforcement.
 */

import { Navigate, Route, Routes } from 'react-router-dom';

import LoginPage from '@/features/auth/LoginPage';
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
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <App />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default AppRoutes;
