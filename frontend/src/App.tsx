import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Space, Spin, Typography } from 'antd';

import { apiClient } from './api/client';
import { useAuthStore } from './store/auth';

const { Title, Paragraph, Text } = Typography;

interface HealthResponse {
  status: string;
}

interface RootResponse {
  name: string;
  version: string;
  env: string;
  docs: string;
}

function App() {
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  const { data: health, isLoading, error } = useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: async () => {
      const response = await apiClient.get<HealthResponse>('/health');
      return response.data;
    },
  });

  const { data: root } = useQuery<RootResponse>({
    queryKey: ['root'],
    queryFn: async () => {
      const response = await apiClient.get<RootResponse>('/');
      return response.data;
    },
  });

  return (
    <div style={{ padding: '40px', maxWidth: 720, margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={1} style={{ margin: 0 }}>🚀 IDEA Portal</Title>
          {user && (
            <Space>
              <Text>
                Hi, <strong>{user.nik}</strong> ({user.roles[0]?.name ?? '—'})
              </Text>
              <Button
                onClick={async () => {
                  const { logout } = await import('./api/auth');
                  const { broadcastLogout } = await import('./lib/sessionBroadcast');
                  const refreshToken = useAuthStore.getState().refreshToken;
                  if (refreshToken) {
                    try {
                      await logout(refreshToken);
                    } catch {
                      // Best-effort — backend mungkin gak reachable
                    }
                  }
                  clearAuth();
                  broadcastLogout('user');
                  window.location.href = '/login';
                }}
              >
                Logout
              </Button>
            </Space>
          )}
        </div>
        <Paragraph>
          Sprint 1 — TSK-001 Login Portal Setup ✓<br />
          Anda berhasil login. Selamat datang di IDEA Portal.
        </Paragraph>

        <Card title="Backend Health Check">
          {isLoading && <Spin tip="Checking backend..." />}
          {error && (
            <Alert
              type="error"
              message="Backend tidak tersedia"
              description={
                <Text code>
                  {error instanceof Error ? error.message : 'Unknown error'}
                </Text>
              }
            />
          )}
          {health && (
            <Alert
              type="success"
              message={`Backend OK: ${health.status}`}
              description={
                root && (
                  <Space direction="vertical">
                    <Text>
                      <strong>App:</strong> {root.name} v{root.version}
                    </Text>
                    <Text>
                      <strong>Env:</strong> {root.env}
                    </Text>
                    <Text>
                      <strong>API Docs:</strong>{' '}
                      <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">
                        Swagger UI
                      </a>
                    </Text>
                  </Space>
                )
              }
            />
          )}
        </Card>

        <Card title="Quick Links">
          <Space direction="vertical">
            <Text>
              <a href="/settings">⚙️ Pengaturan</a>{' '}
              <Text type="secondary" style={{ fontSize: 11 }}>(Theme, font, password)</Text>
            </Text>
            <Text>
              <a href="/admin/permissions">🔐 Permission Matrix</a>{' '}
              <Text type="secondary" style={{ fontSize: 11 }}>(Executive only)</Text>
            </Text>
            <Text>
              <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer">📖 API Docs (Swagger)</a>
            </Text>
          </Space>
        </Card>

        <Card title="Sprint Progress">
          <Paragraph>
            <ol>
              <li>Sprint 0 (1–7 Jun 2026): infra running, hello-world working ✅</li>
              <li>Sprint 1 (8 Jun – 5 Jul): EP-01 Auth &amp; RBAC — JWT login, level 1–6, Wakil Direktur ✅</li>
              <li>Sprint 2+: see <Text code>IDEA_Development_Roadmap.md</Text></li>
            </ol>
          </Paragraph>
        </Card>
      </Space>
    </div>
  );
}

export default App;
