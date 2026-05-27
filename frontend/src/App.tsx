import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Space, Spin, Typography } from 'antd';

import { apiClient } from './api/client';

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
        <Title level={1}>🚀 IDEA Portal — Frontend</Title>
        <Paragraph>
          Sprint 0 skeleton — Vite + React + TS + Ant Design + React Query + Zustand.
          <br />
          Backend connection test di bawah.
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

        <Card title="Next Steps">
          <Paragraph>
            <ol>
              <li>Sprint 0 (1–7 Jun 2026): infra running, hello-world working ✅</li>
              <li>Sprint 1 (8 Jun – 5 Jul): EP-01 Auth &amp; RBAC — JWT login, level 1–6, Wakil Direktur</li>
              <li>Sprint 2+: see <Text code>IDEA_Development_Roadmap.md</Text></li>
            </ol>
          </Paragraph>
        </Card>
      </Space>
    </div>
  );
}

export default App;
