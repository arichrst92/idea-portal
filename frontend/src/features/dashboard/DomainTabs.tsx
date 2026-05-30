/**
 * Domain-focused dashboard tabs — TSK-150.
 *
 * Specialized drill-down per domain area:
 *  - PeopleTab     — employees, contracts, separations, performance
 *  - TechnologyTab — projects, phases overdue, tasks at risk
 *  - SalesTab      — pipeline funnel, closed won YTD, commissions
 *  - FinanceTab    — invoices outstanding, AR aging, reimbursements
 *
 * Reuses fetchDashboardOverview data (no extra endpoint), so cards
 * are aggregate-level. Drill-down link → relevant page.
 */

import {
  AlertOutlined,
  ArrowRightOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  DollarOutlined,
  FileTextOutlined,
  FundOutlined,
  ProjectOutlined,
  TeamOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Button, Card, Col, Empty, Progress, Row, Space, Spin, Statistic, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';

import { fetchDashboardOverview } from '@/api/dashboard';

const { Text, Title } = Typography;

const fmtIDR = (val: number) => {
  if (val >= 1_000_000_000) return `Rp ${(val / 1_000_000_000).toFixed(1)}M`;
  if (val >= 1_000_000) return `Rp ${(val / 1_000_000).toFixed(1)}jt`;
  if (val >= 1_000) return `Rp ${(val / 1_000).toFixed(0)}rb`;
  return `Rp ${val.toLocaleString('id-ID')}`;
};

function StatBox({
  label, value, color, icon, hint,
}: {
  label: string; value: string | number; color?: string;
  icon?: React.ReactNode; hint?: string;
}) {
  return (
    <Card size="small" style={{ borderRadius: 10, height: '100%' }}>
      <Space direction="vertical" size={2} style={{ width: '100%' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <Text type="secondary" style={{ fontSize: 11 }}>{label}</Text>
          {icon && <span style={{ color: color ?? 'var(--ide-blue, #0071E3)' }}>{icon}</span>}
        </div>
        <Statistic
          value={value}
          valueStyle={{ fontSize: 22, fontWeight: 700, color: color ?? undefined }}
        />
        {hint && (
          <Text type="secondary" style={{ fontSize: 11 }}>{hint}</Text>
        )}
      </Space>
    </Card>
  );
}

// ─── People Tab (TSK-152 stub) ────────────────────────────────────

export function PeopleTab() {
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: fetchDashboardOverview,
  });

  if (q.isLoading) return <Spin />;
  if (!q.data) return <Empty />;
  const d = q.data;

  const perf = d.performance.latest_period;
  const total = perf?.total_assessed ?? 0;
  const pct = (v: number) => total > 0 ? Math.round((v / total) * 100) : 0;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={5} style={{ margin: 0 }}>👥 People Overview</Title>

      <Row gutter={[12, 12]}>
        <Col xs={12} sm={6}>
          <StatBox
            label="Total Karyawan" value={d.employees.total}
            icon={<TeamOutlined />} color="#0071E3"
          />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox
            label="Onboarding Aktif" value={d.onboarding.active_assignments}
            icon={<CheckCircleOutlined />} color="#34C759"
          />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox
            label="Separation Pending" value={d.separation.pending_or_approved}
            icon={<WarningOutlined />} color="#FF3B30"
          />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox
            label="SP Total" value={d.performance.warning_letters_total}
            icon={<AlertOutlined />} color="#FF9500"
          />
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="Headcount per Departemen" style={{ borderRadius: 10 }}>
            <Space direction="vertical" size={10} style={{ width: '100%' }}>
              {d.employees.by_department.slice(0, 8).map((dept) => {
                const max = Math.max(...d.employees.by_department.map((x) => x.count), 1);
                return (
                  <div key={dept.code}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontSize: 12 }}><strong>{dept.code}</strong> — {dept.name}</Text>
                      <Text strong>{dept.count}</Text>
                    </div>
                    <Progress
                      percent={Math.round((dept.count / max) * 100)}
                      showInfo={false} strokeColor="#0071E3" size="small"
                    />
                  </div>
                );
              })}
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card
            title={`Distribusi Performance — ${perf?.year ?? '—'}/${perf?.month?.toString().padStart(2, '0') ?? '—'}`}
            style={{ borderRadius: 10 }}
          >
            {!perf ? <Empty description="Belum ada periode" /> : (
              <Space direction="vertical" size={10} style={{ width: '100%' }}>
                {([
                  { label: 'GREEN — Excellent', color: '#34C759', val: perf.distribution.GREEN },
                  { label: 'YELLOW — Watch', color: '#FFD60A', val: perf.distribution.YELLOW },
                  { label: 'ORANGE — Risk', color: '#FF9500', val: perf.distribution.ORANGE },
                  { label: 'RED — Critical', color: '#FF3B30', val: perf.distribution.RED },
                ] as const).map((r) => (
                  <div key={r.label}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontSize: 12 }}>{r.label}</Text>
                      <Text strong style={{ fontSize: 12 }}>{r.val} ({pct(r.val)}%)</Text>
                    </div>
                    <Progress percent={pct(r.val)} showInfo={false} strokeColor={r.color} size="small" />
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <Card style={{ borderRadius: 10, background: 'rgba(0,113,227,0.04)' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Text>Drill down ke modul People:</Text>
          <Space>
            <Button size="small" onClick={() => navigate('/employees')}>Karyawan</Button>
            <Button size="small" onClick={() => navigate('/performance')}>Performance</Button>
            <Button size="small" onClick={() => navigate('/separations')}>Separation</Button>
          </Space>
        </Space>
      </Card>
    </Space>
  );
}

// ─── Technology Tab ───────────────────────────────────────────────

export function TechnologyTab() {
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: fetchDashboardOverview,
  });
  if (q.isLoading) return <Spin />;
  if (!q.data) return <Empty />;
  const d = q.data;

  const utilization = d.projects.total > 0
    ? Math.round((d.projects.active / d.projects.total) * 100)
    : 0;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={5} style={{ margin: 0 }}>🛠️ Technology / Projects</Title>

      <Row gutter={[12, 12]}>
        <Col xs={12} sm={6}>
          <StatBox label="Project Aktif" value={d.projects.active}
            icon={<ProjectOutlined />} color="#0071E3" hint={`dari ${d.projects.total} total`} />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Utilization" value={`${utilization}%`}
            icon={<ClockCircleOutlined />} color={utilization >= 70 ? '#34C759' : '#FF9500'} />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Total Contract Value" value={fmtIDR(d.projects.total_contract_value)}
            icon={<DollarOutlined />} color="#AF52DE" />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Documents (TSK-068)" value="—"
            icon={<FileTextOutlined />} hint="Per project" />
        </Col>
      </Row>

      <Card style={{ borderRadius: 10 }}>
        <Title level={5}>Project Health Snapshot</Title>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Buka project untuk detail Phase progress, Kanban, Gantt timeline, task at risk.
        </Text>
        <div style={{ marginTop: 12 }}>
          <Button type="primary" icon={<ArrowRightOutlined />} onClick={() => navigate('/projects')}>
            Lihat Semua Project
          </Button>
        </div>
      </Card>
    </Space>
  );
}

// ─── Sales Tab ────────────────────────────────────────────────────

export function SalesTab() {
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: fetchDashboardOverview,
  });
  if (q.isLoading) return <Spin />;
  if (!q.data) return <Empty />;
  const d = q.data;

  const winRate = d.sales.total_leads > 0
    ? Math.round((d.sales.closed_won_ytd / Math.max(d.sales.pipeline_value, 1)) * 100)
    : 0;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={5} style={{ margin: 0 }}>💼 Sales Performance</Title>

      <Row gutter={[12, 12]}>
        <Col xs={12} sm={6}>
          <StatBox label="Pipeline Value" value={fmtIDR(d.sales.pipeline_value)}
            icon={<FundOutlined />} color="#AF52DE" hint={`${d.sales.total_leads} leads`} />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Closed Won YTD" value={fmtIDR(d.sales.closed_won_ytd)}
            icon={<CheckCircleOutlined />} color="#34C759" />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Commission Pending" value={fmtIDR(d.sales.commissions_pending_amount)}
            icon={<DollarOutlined />} color="#FF9500" hint="Akan auto-payroll" />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Conversion Estimate" value={`${winRate}%`}
            icon={<ClockCircleOutlined />} color="#0071E3" hint="Won / Pipeline" />
        </Col>
      </Row>

      <Card style={{ borderRadius: 10, background: 'rgba(175,82,222,0.04)' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Text>
            <strong>Komisi otomatis:</strong> Sales CLOSED_WON akan auto-create variable
            payroll line untuk sales PIC (TSK-194). Direktur-driven deal = no commission.
          </Text>
          <Space>
            <Button size="small" onClick={() => navigate('/sales')}>Sales Pipeline</Button>
            <Button size="small" onClick={() => navigate('/payroll')}>Payroll Slips</Button>
          </Space>
        </Space>
      </Card>
    </Space>
  );
}

// ─── Finance Tab (TSK-151 stub) ───────────────────────────────────

export function FinanceTab() {
  const navigate = useNavigate();
  const q = useQuery({
    queryKey: ['dashboard', 'overview'],
    queryFn: fetchDashboardOverview,
  });
  if (q.isLoading) return <Spin />;
  if (!q.data) return <Empty />;
  const d = q.data;

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={5} style={{ margin: 0 }}>💰 Finance & AR</Title>

      <Row gutter={[12, 12]}>
        <Col xs={12} sm={6}>
          <StatBox label="Reimbursement Pending" value={d.finance.reimb_pending}
            icon={<AlertOutlined />} color="#FF9500" />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Reimburse Ready Transfer" value={d.finance.reimb_ready_to_transfer}
            icon={<CheckCircleOutlined />} color="#34C759" />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Reimburse Amount" value={fmtIDR(d.finance.reimb_total_amount)}
            icon={<DollarOutlined />} color="#0071E3" />
        </Col>
        <Col xs={12} sm={6}>
          <StatBox label="Procurement Pending" value={d.finance.proc_pending}
            icon={<FileTextOutlined />} color="#AF52DE" />
        </Col>
      </Row>

      <Card style={{ borderRadius: 10, background: 'rgba(52,199,89,0.04)' }} title="EBITDA Snapshot (TSK-151 — placeholder)">
        <Empty
          description="EBITDA calculation akan dibangun di TSK-151. Saat ini placeholder."
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      </Card>

      <Card style={{ borderRadius: 10 }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Text>
            <strong>Invoice & AR:</strong> Aging buckets dan invoice status di Finance page.
          </Text>
          <Button size="small" type="primary" icon={<ArrowRightOutlined />}
            onClick={() => navigate('/finance')}>
            Lihat Invoices / Reimburse / Procurement
          </Button>
        </Space>
      </Card>
    </Space>
  );
}

// ─── Outsource Tab (M2.3 placeholder) ─────────────────────────────

export function OutsourceTab() {
  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Title level={5} style={{ margin: 0 }}>🏢 Outsource</Title>
      <Card style={{ borderRadius: 10 }}>
        <Empty
          description={
            <span>
              Outsource module akan dibangun di M2.3 (TSK-100 s/d TSK-124).<br />
              Akan menampilkan: placement aktif, timesheet pending, BA outstanding,
              client complaint dan SP-O status.
            </span>
          }
        />
      </Card>
    </Space>
  );
}
