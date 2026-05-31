/**
 * DashboardPage — TSK-025 Executive Dashboard.
 *
 * Aggregate widget dari 9 domain:
 * - KPI cards (employees, contracts, hiring, leave, projects, sales, finance, performance)
 * - Headcount by department chart
 * - Performance distribution (GREEN/YELLOW/ORANGE/RED)
 * - Recent activity timeline (audit log)
 */

import {
  AlertOutlined,
  BarChartOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  DollarOutlined,
  FileTextOutlined,
  FundOutlined,
  ProjectOutlined,
  SolutionOutlined,
  TeamOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Card,
  Col,
  Empty,
  List,
  Progress,
  Row,
  Space,
  Spin,
  Statistic,
  Tabs,
  Tag,
  Timeline,
  Typography,
} from 'antd';

import { fetchDashboardOverview, fetchRecentActivity } from '@/api/dashboard';
import { getPersonaLabel } from '@/lib/persona';
import { useAuthStore } from '@/store/auth';

import {
  FinanceTab,
  OutsourceTab,
  PeopleTab,
  SalesTab,
  TechnologyTab,
} from './DomainTabs';

const { Title, Text, Paragraph } = Typography;

const fmtIDR = (val: number) => {
  if (val >= 1_000_000_000) return `Rp ${(val / 1_000_000_000).toFixed(1)}M`;
  if (val >= 1_000_000) return `Rp ${(val / 1_000_000).toFixed(1)}jt`;
  if (val >= 1_000) return `Rp ${(val / 1_000).toFixed(0)}rb`;
  return `Rp ${val.toLocaleString('id-ID')}`;
};

const fmtDateTime = (iso: string) => {
  const d = new Date(iso);
  return d.toLocaleString('id-ID', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const MONTH_NAMES = [
  'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
  'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des',
];

function KPICard({
  title,
  value,
  icon,
  color,
  suffix,
  precision,
  hint,
}: {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  suffix?: string;
  precision?: number;
  hint?: string;
}) {
  return (
    <Card
      size="small"
      style={{ height: '100%', borderRadius: 12 }}
      styles={{ body: { padding: 16 } }}
    >
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <Text type="secondary" style={{ fontSize: 12, fontWeight: 500 }}>
            {title}
          </Text>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: `${color}1a`,
              color,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
            }}
          >
            {icon}
          </div>
        </div>
        <Statistic
          value={value}
          suffix={suffix}
          precision={precision}
          valueStyle={{ fontSize: 22, fontWeight: 700, color: 'var(--main, #1d1d1f)' }}
        />
        {hint && (
          <Text type="secondary" style={{ fontSize: 11 }}>
            {hint}
          </Text>
        )}
      </Space>
    </Card>
  );
}

function PerformanceDistribution({
  distribution,
  total,
}: {
  distribution: { GREEN: number; YELLOW: number; ORANGE: number; RED: number };
  total: number;
}) {
  const pct = (v: number) => (total > 0 ? Math.round((v / total) * 100) : 0);
  return (
    <Space direction="vertical" size={10} style={{ width: '100%' }}>
      {(
        [
          { label: 'GREEN — Excellent (≥70)', color: '#34C759', val: distribution.GREEN },
          { label: 'YELLOW — Watch (60–69)', color: '#FFD60A', val: distribution.YELLOW },
          { label: 'ORANGE — Risk (50–59)', color: '#FF9500', val: distribution.ORANGE },
          { label: 'RED — Critical (<50)', color: '#FF3B30', val: distribution.RED },
        ] as const
      ).map((row) => (
        <div key={row.label}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              marginBottom: 4,
            }}
          >
            <Text style={{ fontSize: 12 }}>{row.label}</Text>
            <Text strong style={{ fontSize: 12 }}>
              {row.val} ({pct(row.val)}%)
            </Text>
          </div>
          <Progress
            percent={pct(row.val)}
            showInfo={false}
            strokeColor={row.color}
            size="small"
          />
        </div>
      ))}
    </Space>
  );
}

function ActionLabel({ action }: { action: string }) {
  const map: Record<string, { color: string; label: string }> = {
    LOGIN: { color: 'blue', label: 'Login' },
    LOGOUT: { color: 'default', label: 'Logout' },
    CREATE: { color: 'green', label: 'Create' },
    UPDATE: { color: 'cyan', label: 'Update' },
    DELETE: { color: 'red', label: 'Delete' },
    APPROVE: { color: 'green', label: 'Approve' },
    REJECT: { color: 'red', label: 'Reject' },
    SUBMIT: { color: 'purple', label: 'Submit' },
  };
  const key = action.toUpperCase().split('_')[0] ?? action;
  const conf = map[key] ?? { color: 'default', label: action };
  return <Tag color={conf.color}>{action}</Tag>;
}

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);

  const overviewQ = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: fetchDashboardOverview,
    refetchInterval: 60_000, // refresh tiap 1 menit
  });

  if (overviewQ.isLoading) {
    return (
      <div style={{ padding: 48, textAlign: 'center' }}>
        <Spin size="large" tip="Memuat dashboard..."><div style={{ minHeight: 24 }} /></Spin>
      </div>
    );
  }

  if (overviewQ.error) {
    return (
      <div style={{ padding: 24 }}>
        <Alert
          type="error"
          message="Gagal memuat dashboard"
          description={
            overviewQ.error instanceof Error
              ? overviewQ.error.message
              : 'Unknown error'
          }
          showIcon
        />
      </div>
    );
  }

  const data = overviewQ.data!;

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1440, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <Title level={3} style={{ margin: 0 }}>
          Dashboard Eksekutif
        </Title>
        <Paragraph style={{ margin: 0, color: 'var(--sub, #6e6e73)' }}>
          Ringkasan operasional per {new Date(data.as_of).toLocaleDateString('id-ID', { day: '2-digit', month: 'long', year: 'numeric' })}
          {user && (
            <>
              {' · '}
              <Text type="secondary">
                Selamat datang, <strong>{getPersonaLabel(user)}</strong>
              </Text>
            </>
          )}
        </Paragraph>
      </div>

      <Tabs
        defaultActiveKey="overview"
        size="large"
        items={[
          { key: 'overview', label: '🏠 Overview', children: <OverviewTabContent /> },
          { key: 'people', label: '👥 People', children: <PeopleTab /> },
          { key: 'technology', label: '🛠️ Technology', children: <TechnologyTab /> },
          { key: 'sales', label: '💼 Sales', children: <SalesTab /> },
          { key: 'finance', label: '💰 Finance', children: <FinanceTab /> },
          { key: 'outsource', label: '🏢 Outsource', children: <OutsourceTab /> },
        ]}
      />
    </div>
  );
}

// Overview tab content — original dashboard content extracted ke sub-component
function OverviewTabContent() {
  const overviewQ = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: fetchDashboardOverview,
    refetchInterval: 60_000,
  });
  const activityQ = useQuery({
    queryKey: ['dashboard', 'activity'],
    queryFn: () => fetchRecentActivity(15),
    refetchInterval: 60_000,
  });

  if (overviewQ.isLoading) return <Spin tip="Memuat..."><div style={{ minHeight: 24 }} /></Spin>;
  if (!overviewQ.data) return <Empty />;

  const data = overviewQ.data;
  const activities = activityQ.data ?? [];
  const topDept = data.employees.by_department.slice(0, 5);
  const maxDeptCount = Math.max(...topDept.map((d) => d.count), 1);

  return (
    <>
      {/* KPI Row 1 — People */}
      <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
        <Col xs={12} sm={8} md={6} lg={4}>
          <KPICard
            title="Total Karyawan"
            value={data.employees.total}
            icon={<TeamOutlined />}
            color="#0071E3"
            hint={`${Object.keys(data.employees.by_status).length} status`}
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <KPICard
            title="Kontrak Expiring (30d)"
            value={data.contracts.expiring_30d}
            icon={<FileTextOutlined />}
            color="#FF9500"
            hint={data.contracts.expired_unrenewed > 0
              ? `${data.contracts.expired_unrenewed} expired belum renew`
              : 'Tidak ada expired'}
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <KPICard
            title="Lowongan Aktif"
            value={data.hiring.openings_open}
            icon={<SolutionOutlined />}
            color="#34C759"
            hint={`${data.hiring.applications_active} pelamar aktif`}
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <KPICard
            title="Onboarding Berjalan"
            value={data.onboarding.active_assignments}
            icon={<CheckSquareOutlined />}
            color="#32ADE6"
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <KPICard
            title="Cuti Pending"
            value={data.leave.pending_approval}
            icon={<CalendarOutlined />}
            color="#AF52DE"
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={4}>
          <KPICard
            title="Separation Pending"
            value={data.separation.pending_or_approved}
            icon={<WarningOutlined />}
            color="#FF3B30"
            hint={data.performance.warning_letters_total > 0
              ? `${data.performance.warning_letters_total} SP total`
              : undefined}
          />
        </Col>
      </Row>

      {/* KPI Row 2 — Business */}
      <Row gutter={[12, 12]} style={{ marginBottom: 20 }}>
        <Col xs={12} sm={8} md={6} lg={6}>
          <KPICard
            title="Project Aktif"
            value={data.projects.active}
            icon={<ProjectOutlined />}
            color="#0071E3"
            hint={`Total kontrak ${fmtIDR(data.projects.total_contract_value)}`}
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={6}>
          <KPICard
            title="Sales Pipeline"
            value={fmtIDR(data.sales.pipeline_value)}
            icon={<FundOutlined />}
            color="#AF52DE"
            hint={`${data.sales.total_leads} leads aktif`}
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={6}>
          <KPICard
            title="Closed Won YTD"
            value={fmtIDR(data.sales.closed_won_ytd)}
            icon={<DollarOutlined />}
            color="#34C759"
            hint={data.sales.commissions_pending_amount > 0
              ? `Komisi pending ${fmtIDR(data.sales.commissions_pending_amount)}`
              : 'Belum ada komisi pending'}
          />
        </Col>
        <Col xs={12} sm={8} md={6} lg={6}>
          <KPICard
            title="Reimbursement"
            value={data.finance.reimb_pending + data.finance.reimb_ready_to_transfer}
            icon={<AlertOutlined />}
            color="#FF9500"
            hint={`${data.finance.reimb_pending} pending · ${data.finance.reimb_ready_to_transfer} siap transfer · ${data.finance.proc_pending} procurement`}
          />
        </Col>
      </Row>

      {/* Main widget grid */}
      <Row gutter={[16, 16]}>
        {/* Headcount by Department */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <TeamOutlined />
                Headcount per Departemen
              </Space>
            }
            extra={
              <Text type="secondary" style={{ fontSize: 12 }}>
                Top 5
              </Text>
            }
            style={{ borderRadius: 12, height: '100%' }}
          >
            {topDept.length === 0 ? (
              <Empty description="Belum ada data departemen" />
            ) : (
              <Space direction="vertical" size={12} style={{ width: '100%' }}>
                {topDept.map((d) => (
                  <div key={d.code}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        marginBottom: 4,
                      }}
                    >
                      <Text style={{ fontSize: 13 }}>
                        <strong>{d.code}</strong> — {d.name}
                      </Text>
                      <Text strong style={{ fontSize: 13 }}>
                        {d.count}
                      </Text>
                    </div>
                    <Progress
                      percent={Math.round((d.count / maxDeptCount) * 100)}
                      showInfo={false}
                      strokeColor="#0071E3"
                      size="small"
                    />
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>

        {/* Performance Distribution */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <BarChartOutlined />
                Distribusi Performance
              </Space>
            }
            extra={
              data.performance.latest_period && (
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {MONTH_NAMES[data.performance.latest_period.month - 1]}{' '}
                  {data.performance.latest_period.year} · {data.performance.latest_period.total_assessed} dinilai
                </Text>
              )
            }
            style={{ borderRadius: 12, height: '100%' }}
          >
            {!data.performance.latest_period ? (
              <Empty description="Belum ada periode penilaian" />
            ) : (
              <PerformanceDistribution
                distribution={data.performance.latest_period.distribution}
                total={data.performance.latest_period.total_assessed}
              />
            )}
          </Card>
        </Col>

        {/* Recent Activity (Audit Log Timeline) */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <AlertOutlined />
                Aktivitas Terbaru
              </Space>
            }
            extra={
              <Text type="secondary" style={{ fontSize: 12 }}>
                Audit log
              </Text>
            }
            style={{ borderRadius: 12, height: '100%' }}
          >
            {activityQ.isLoading ? (
              <Spin />
            ) : activities.length === 0 ? (
              <Empty description="Belum ada aktivitas" />
            ) : (
              <Timeline
                style={{ marginTop: 8 }}
                items={activities.slice(0, 8).map((a) => ({
                  color:
                    a.action.startsWith('DELETE') || a.action.startsWith('REJECT')
                      ? 'red'
                      : a.action.startsWith('APPROVE') || a.action.startsWith('CREATE')
                        ? 'green'
                        : 'blue',
                  children: (
                    <Space direction="vertical" size={2}>
                      <Space size="small" wrap>
                        <ActionLabel action={a.action} />
                        {a.resource_type && (
                          <Text type="secondary" style={{ fontSize: 12 }}>
                            {a.resource_type}
                          </Text>
                        )}
                      </Space>
                      <Text style={{ fontSize: 12 }}>
                        <strong>{a.actor_persona ?? a.actor_nik ?? 'Sistem'}</strong>{' '}
                        <Text type="secondary">· {fmtDateTime(a.timestamp)}</Text>
                      </Text>
                    </Space>
                  ),
                }))}
              />
            )}
          </Card>
        </Col>

        {/* Status & Type breakdown */}
        <Col xs={24} lg={12}>
          <Card
            title={
              <Space>
                <TeamOutlined />
                Komposisi Karyawan
              </Space>
            }
            style={{ borderRadius: 12, height: '100%' }}
          >
            <Row gutter={16}>
              <Col span={12}>
                <Text strong style={{ fontSize: 12, color: 'var(--sub, #6e6e73)' }}>
                  STATUS
                </Text>
                <List
                  size="small"
                  dataSource={Object.entries(data.employees.by_status)}
                  renderItem={([status, count]) => (
                    <List.Item style={{ padding: '6px 0' }}>
                      <Text style={{ fontSize: 12 }}>{status}</Text>
                      <Text strong style={{ fontSize: 12 }}>
                        {count}
                      </Text>
                    </List.Item>
                  )}
                  locale={{ emptyText: 'Tidak ada data' }}
                />
              </Col>
              <Col span={12}>
                <Text strong style={{ fontSize: 12, color: 'var(--sub, #6e6e73)' }}>
                  TIPE
                </Text>
                <List
                  size="small"
                  dataSource={Object.entries(data.employees.by_type)}
                  renderItem={([type, count]) => (
                    <List.Item style={{ padding: '6px 0' }}>
                      <Text style={{ fontSize: 12 }}>{type}</Text>
                      <Text strong style={{ fontSize: 12 }}>
                        {count}
                      </Text>
                    </List.Item>
                  )}
                  locale={{ emptyText: 'Tidak ada data' }}
                />
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>
    </>
  );
}
