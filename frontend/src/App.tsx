import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Space, Spin, Typography } from 'antd';

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
    <div style={{ padding: '24px 32px', maxWidth: 1024, margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div>
          <Title level={1} style={{ margin: 0 }}>🚀 IDEA Portal</Title>
          {user && (
            <Paragraph style={{ marginTop: 8, marginBottom: 0 }}>
              Selamat datang, <strong>{user.nik}</strong>{' '}
              <Text type="secondary">({user.roles[0]?.name ?? '—'})</Text>
            </Paragraph>
          )}
        </div>
        <Paragraph>
          Sprint 1 — M1.1 Auth & RBAC sedang berjalan. Tekan{' '}
          <Text keyboard>⌘ K</Text> untuk global search atau gunakan menu di sebelah kiri.
        </Paragraph>

        <Card title="Backend Health Check">
          {isLoading && <Spin tip="Checking backend..."><div style={{ minHeight: 24 }} /></Spin>}
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
