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

import {
  fetchDashboardOverview, fetchEbitda, fetchPeoplePerformance,
  type DeptAvg, type EbitdaMonth, type PerformerItem,
} from '@/api/dashboard';

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

      <PeoplePerformanceCard />

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

      <EbitdaCard />


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

// ─── EBITDA Card (TSK-151) ────────────────────────────────────────

function EbitdaCard() {
  const q = useQuery({
    queryKey: ['dashboard', 'ebitda'],
    queryFn: () => fetchEbitda(12),
    refetchInterval: 5 * 60_000,
  });

  if (q.isLoading) return <Card title="EBITDA — 12 month trend" style={{ borderRadius: 10 }}><Spin /></Card>;
  if (!q.data || q.data.months.length === 0) {
    return (
      <Card title="EBITDA — 12 month trend" style={{ borderRadius: 10 }}>
        <Empty description="Belum ada data untuk EBITDA" />
      </Card>
    );
  }

  const months = q.data.months;
  const summary = q.data.summary;
  const maxRev = Math.max(...months.map((m: EbitdaMonth) => Math.max(m.revenue, m.cost)), 1);

  return (
    <Card
      title="EBITDA — 12 month trend"
      extra={
        <Space size={16}>
          <Text type="secondary" style={{ fontSize: 11 }}>Avg Margin</Text>
          <Text strong style={{ color: summary.avg_margin_pct >= 0 ? '#34C759' : '#FF3B30' }}>
            {summary.avg_margin_pct}%
          </Text>
        </Space>
      }
      style={{ borderRadius: 10 }}
    >
      {/* Summary strip */}
      <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
        <Col xs={12} sm={8}>
          <Text type="secondary" style={{ fontSize: 11 }}>Total Revenue</Text>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#0071E3' }}>
            {fmtIDR(summary.total_revenue)}
          </div>
        </Col>
        <Col xs={12} sm={8}>
          <Text type="secondary" style={{ fontSize: 11 }}>Total Cost</Text>
          <div style={{ fontSize: 16, fontWeight: 700, color: '#FF9500' }}>
            {fmtIDR(summary.total_cost)}
          </div>
        </Col>
        <Col xs={12} sm={8}>
          <Text type="secondary" style={{ fontSize: 11 }}>Total EBITDA</Text>
          <div style={{
            fontSize: 18, fontWeight: 800,
            color: summary.total_ebitda >= 0 ? '#34C759' : '#FF3B30',
          }}>
            {fmtIDR(summary.total_ebitda)}
          </div>
        </Col>
      </Row>

      {/* Bar chart — SVG-based */}
      <div style={{ overflowX: 'auto', paddingBottom: 8 }}>
        <svg width={Math.max(months.length * 60, 600)} height={220} style={{ minWidth: '100%' }}>
          {months.map((m: EbitdaMonth, i: number) => {
            const x = i * 60 + 30;
            const revHeight = (m.revenue / maxRev) * 150;
            const costHeight = (m.cost / maxRev) * 150;
            const ebitdaY = 180 - (m.ebitda / maxRev) * 150;
            return (
              <g key={`${m.year}-${m.month}`}>
                {/* Revenue bar */}
                <rect
                  x={x} y={180 - revHeight} width={20} height={revHeight}
                  fill="#0071E3" opacity={0.75} rx={2}
                />
                {/* Cost bar */}
                <rect
                  x={x + 22} y={180 - costHeight} width={20} height={costHeight}
                  fill="#FF9500" opacity={0.75} rx={2}
                />
                {/* EBITDA line marker */}
                <circle cx={x + 21} cy={ebitdaY} r={4}
                  fill={m.ebitda >= 0 ? '#34C759' : '#FF3B30'} />
                {/* Month label */}
                <text x={x + 21} y={200} fontSize={9} textAnchor="middle"
                  fill="#86868B" fontFamily="-apple-system, sans-serif">
                  {m.label.split(' ')[0]}
                </text>
                {/* Margin % */}
                <text x={x + 21} y={213} fontSize={8} textAnchor="middle"
                  fill={m.margin_pct >= 0 ? '#34C759' : '#FF3B30'} fontWeight={600}>
                  {m.margin_pct}%
                </text>
              </g>
            );
          })}
          {/* Connect EBITDA dots with polyline */}
          <polyline
            fill="none"
            stroke="#34C759"
            strokeWidth={1.5}
            strokeDasharray="3 3"
            points={months.map((m: EbitdaMonth, i: number) =>
              `${i * 60 + 51},${180 - (m.ebitda / maxRev) * 150}`
            ).join(' ')}
          />
        </svg>
      </div>

      {/* Legend */}
      <Space size={20} style={{ marginTop: 8, fontSize: 11 }}>
        <Space size={4}>
          <span style={{ width: 10, height: 10, background: '#0071E3', display: 'inline-block', borderRadius: 2 }} />
          <Text type="secondary">Revenue (Invoice + Outsource)</Text>
        </Space>
        <Space size={4}>
          <span style={{ width: 10, height: 10, background: '#FF9500', display: 'inline-block', borderRadius: 2 }} />
          <Text type="secondary">Cost (Payroll + Reimburse + Procurement)</Text>
        </Space>
        <Space size={4}>
          <span style={{ width: 10, height: 10, background: '#34C759', display: 'inline-block', borderRadius: '50%' }} />
          <Text type="secondary">EBITDA</Text>
        </Space>
      </Space>
    </Card>
  );
}

// ─── People Performance Card (TSK-152) ────────────────────────────

const PERF_COLOR: Record<string, string> = {
  GREEN: '#34C759',
  YELLOW: '#FFD60A',
  ORANGE: '#FF9500',
  RED: '#FF3B30',
};

function PerformerRow({ p, rank, isBottom }: { p: PerformerItem; rank: number; isBottom?: boolean }) {
  const color = p.final_score >= 70 ? '#34C759' :
                p.final_score >= 60 ? '#FFD60A' :
                p.final_score >= 50 ? '#FF9500' : '#FF3B30';
  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '8px 10px', borderRadius: 6,
      background: isBottom ? 'rgba(255,59,48,0.04)' : 'rgba(52,199,89,0.04)',
      marginBottom: 4,
    }}>
      <Space>
        <span style={{
          width: 22, height: 22, borderRadius: '50%',
          background: isBottom ? '#FF3B30' : '#34C759',
          color: 'white', fontSize: 11, fontWeight: 700,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>{rank}</span>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{p.name}</div>
          <div style={{ fontSize: 10, color: 'var(--ide-ink3, #6e6e73)' }}>
            {p.nik} {p.dept_code && `· ${p.dept_code}`}
          </div>
        </div>
      </Space>
      <span style={{
        fontFamily: 'ui-monospace, Menlo, monospace',
        fontSize: 14, fontWeight: 700, color,
      }}>{p.final_score.toFixed(1)}</span>
    </div>
  );
}

function PeoplePerformanceCard() {
  const q = useQuery({
    queryKey: ['dashboard', 'people-performance'],
    queryFn: fetchPeoplePerformance,
    refetchInterval: 5 * 60_000,
  });

  if (q.isLoading) {
    return <Card title="People Performance" style={{ borderRadius: 10 }}><Spin /></Card>;
  }
  if (!q.data || !q.data.period) {
    return (
      <Card title="People Performance" style={{ borderRadius: 10 }}>
        <Empty description="Belum ada periode penilaian. Setup di Performance page." />
      </Card>
    );
  }

  const d = q.data;
  const dist = d.distribution;
  const total = dist.GREEN + dist.YELLOW + dist.ORANGE + dist.RED;
  const summary = d.summary;
  const periodLabel = d.period?.label;

  // Bell curve buckets — group scores into 10-point bins for visualization
  // Use distribution counts as approximation
  const bins = [
    { label: '<50', count: dist.RED, color: '#FF3B30' },
    { label: '50-59', count: dist.ORANGE, color: '#FF9500' },
    { label: '60-69', count: dist.YELLOW, color: '#FFD60A' },
    { label: '70-79', count: Math.round(dist.GREEN * 0.4), color: '#34C759' },
    { label: '80-89', count: Math.round(dist.GREEN * 0.4), color: '#34C759' },
    { label: '90+', count: dist.GREEN - Math.round(dist.GREEN * 0.8), color: '#22a049' },
  ];
  const maxBinCount = Math.max(...bins.map((b) => b.count), 1);

  return (
    <Card
      title={
        <Space>
          📊 <span>People Performance — {periodLabel}</span>
        </Space>
      }
      extra={
        <Space size={16}>
          <span>
            <Text type="secondary" style={{ fontSize: 11 }}>Avg </Text>
            <Text strong style={{ color: PERF_COLOR[summary.avg_score >= 70 ? 'GREEN' : summary.avg_score >= 60 ? 'YELLOW' : summary.avg_score >= 50 ? 'ORANGE' : 'RED'] }}>
              {summary.avg_score.toFixed(1)}
            </Text>
          </span>
          <Text type="secondary" style={{ fontSize: 11 }}>
            σ {summary.std_dev.toFixed(1)} · {total} dinilai
          </Text>
        </Space>
      }
      style={{ borderRadius: 10 }}
    >
      <Row gutter={[16, 16]}>
        {/* Bell curve SVG */}
        <Col xs={24} lg={14}>
          <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
            Distribution (Bell Curve)
          </Text>
          <svg width="100%" height={180} viewBox="0 0 600 180">
            {/* X-axis */}
            <line x1={30} y1={150} x2={580} y2={150} stroke="#E8E8ED" strokeWidth={1} />
            {bins.map((b, i) => {
              const barW = 80;
              const x = 50 + i * 90;
              const h = (b.count / maxBinCount) * 120;
              const y = 150 - h;
              return (
                <g key={b.label}>
                  <rect x={x} y={y} width={barW} height={h} fill={b.color} opacity={0.8} rx={4} />
                  <text x={x + barW / 2} y={y - 5} textAnchor="middle"
                    fontSize={11} fontWeight={700} fill={b.color}>
                    {b.count}
                  </text>
                  <text x={x + barW / 2} y={167} textAnchor="middle"
                    fontSize={10} fill="#86868B">{b.label}</text>
                </g>
              );
            })}
            {/* Curve overlay — bezier through bar tops to suggest bell shape */}
            <path
              d={bins.map((b, i) => {
                const x = 50 + i * 90 + 40;
                const y = 150 - (b.count / maxBinCount) * 120;
                return i === 0 ? `M ${x} ${y}` : `L ${x} ${y}`;
              }).join(' ')}
              fill="none" stroke="#0071E3" strokeWidth={2} strokeDasharray="4 2" opacity={0.6}
            />
          </svg>
        </Col>

        {/* Dept ranking */}
        <Col xs={24} lg={10}>
          <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
            Department Average ({d.dept_avg.length})
          </Text>
          <Space direction="vertical" size={4} style={{ width: '100%' }}>
            {d.dept_avg.slice(0, 6).map((dept: DeptAvg) => (
              <div key={dept.code} style={{
                display: 'flex', justifyContent: 'space-between',
                padding: '6px 10px', borderRadius: 6,
                background: 'rgba(0,0,0,0.02)',
              }}>
                <div>
                  <Text strong style={{ fontSize: 12 }}>{dept.code}</Text>
                  <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
                    {dept.employee_count} org
                  </Text>
                </div>
                <Text strong style={{
                  fontFamily: 'ui-monospace, Menlo, monospace',
                  fontSize: 13, color: PERF_COLOR[dept.color],
                }}>
                  {dept.avg_score.toFixed(1)}
                </Text>
              </div>
            ))}
          </Space>
        </Col>

        {/* Top performers */}
        <Col xs={24} lg={12}>
          <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8, color: '#34C759' }}>
            🏆 Top Performers
          </Text>
          {d.top_performers.length === 0 ? (
            <Empty description="Belum ada data" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : d.top_performers.map((p: PerformerItem, i: number) =>
            <PerformerRow key={p.employee_id} p={p} rank={i + 1} />
          )}
        </Col>

        {/* Bottom performers */}
        <Col xs={24} lg={12}>
          <Text strong style={{ fontSize: 12, display: 'block', marginBottom: 8, color: '#FF3B30' }}>
            ⚠️ At Risk (Score &lt; 70)
          </Text>
          {d.bottom_performers.length === 0 ? (
            <Empty description="Semua di atas threshold 70" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : d.bottom_performers.map((p: PerformerItem, i: number) =>
            <PerformerRow key={p.employee_id} p={p} rank={i + 1} isBottom />
          )}
        </Col>
      </Row>

      <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 10 }}>
        Range: {summary.min_score?.toFixed(1)} – {summary.max_score?.toFixed(1)} ·
        Median: {summary.median_score.toFixed(1)} · Std Dev: {summary.std_dev.toFixed(1)}
      </Text>
    </Card>
  );
}
