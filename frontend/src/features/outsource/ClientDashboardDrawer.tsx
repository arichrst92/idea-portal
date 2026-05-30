/**
 * ClientDashboardDrawer — TSK-109. Aggregate view per client.
 *
 * Includes KPI request button per placement (TSK-108 integration).
 */

import { CopyOutlined, LinkOutlined, SendOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Drawer, Empty, Form, Input, Modal, Space, Spin, Tag, Tooltip,
  Typography, message,
} from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  createKpiRequest,
  getClientDashboard,
  listKpiAssessments,
  type ClientKpiAssessment,
  type Placement,
} from '@/api/outsource';

const { Text, Title } = Typography;

const fmtIDR = (val: number | string) => {
  const n = typeof val === 'string' ? Number(val) : val;
  if (Number.isNaN(n)) return '—';
  if (n >= 1_000_000_000) return `Rp ${(n / 1_000_000_000).toFixed(2)}M`;
  if (n >= 1_000_000) return `Rp ${(n / 1_000_000).toFixed(1)}jt`;
  return `Rp ${n.toLocaleString('id-ID')}`;
};

interface ClientDashboardDrawerProps {
  clientId: string | null;
  open: boolean;
  onClose: () => void;
}

export function ClientDashboardDrawer({
  clientId, open, onClose,
}: ClientDashboardDrawerProps) {
  const [kpiOpen, setKpiOpen] = useState(false);
  const [kpiPlacement, setKpiPlacement] = useState<Placement | null>(null);
  const [kpiHistoryOpen, setKpiHistoryOpen] = useState(false);

  const q = useQuery({
    queryKey: ['client-dashboard', clientId],
    queryFn: () => getClientDashboard(clientId!),
    enabled: !!clientId && open,
  });

  if (!clientId) return null;

  return (
    <Drawer
      title={q.data ? `${q.data.client.code} — ${q.data.client.name}` : 'Client Dashboard'}
      open={open} onClose={onClose} width={760}
      extra={q.data && (
        <Button type="primary" icon={<LinkOutlined />}
          onClick={() => setKpiHistoryOpen(true)}>
          KPI History
        </Button>
      )}
    >
      {q.isLoading ? <Spin /> : q.data && (
        <>
          {/* KPI Summary strip */}
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
            marginBottom: 18,
          }}>
            <Box label="Placements" value={q.data.placement_count} />
            <Box label="Active" value={q.data.active_count} color="#34C759" />
            <Box label="Expiring 30d" value={q.data.expiring_30d}
              color={q.data.expiring_30d > 0 ? '#FF9500' : undefined} />
            <Box label="Monthly Billing" value={fmtIDR(q.data.monthly_billing_estimate)} color="#0071E3" small />
          </div>

          {/* KPI average */}
          {q.data.kpi_avg_overall !== null && (
            <div style={{
              background: 'rgba(52,199,89,0.06)', padding: 12, borderRadius: 8,
              marginBottom: 18,
            }}>
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>Avg KPI Score</Text>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#34C759' }}>
                    {q.data.kpi_avg_overall.toFixed(2)} / 5.0
                  </div>
                </div>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  Dari {q.data.kpi_count} submitted assessment(s)
                </Text>
              </Space>
            </div>
          )}

          {/* Client info */}
          <Title level={5}>Contact</Title>
          <div style={{ background: 'rgba(0,0,0,0.02)', padding: 10, borderRadius: 6, marginBottom: 18, fontSize: 12 }}>
            <div>PIC: <strong>{q.data.client.pic_name ?? '—'}</strong></div>
            <div>Email: {q.data.client.pic_email ?? '—'}</div>
            <div>Phone: {q.data.client.pic_phone ?? '—'}</div>
          </div>

          <Title level={5}>Placements ({q.data.placements.length})</Title>
          {q.data.placements.length === 0 ? (
            <Empty description="Belum ada placement" />
          ) : (
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              {q.data.placements.map((p) => (
                <PlacementRow
                  key={p.id} placement={p}
                  onRequestKpi={() => { setKpiPlacement(p); setKpiOpen(true); }}
                />
              ))}
            </Space>
          )}
        </>
      )}

      <KpiRequestModal
        placement={kpiPlacement} open={kpiOpen}
        onClose={() => { setKpiOpen(false); setKpiPlacement(null); }}
      />
      <KpiHistoryDrawer
        clientId={clientId} open={kpiHistoryOpen}
        onClose={() => setKpiHistoryOpen(false)}
      />
    </Drawer>
  );
}

function Box({ label, value, color, small }: { label: string; value: any; color?: string; small?: boolean }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid rgba(0,0,0,0.06)',
      borderRadius: 8, padding: 10,
    }}>
      <Text type="secondary" style={{ fontSize: 10, textTransform: 'uppercase' }}>{label}</Text>
      <div style={{ fontSize: small ? 14 : 18, fontWeight: 700, marginTop: 2, color }}>{value}</div>
    </div>
  );
}

function PlacementRow({
  placement, onRequestKpi,
}: {
  placement: Placement; onRequestKpi: () => void;
}) {
  const daysLeft = placement.days_until_end;
  const overdue = daysLeft !== null && daysLeft <= 7;
  const dueSoon = daysLeft !== null && daysLeft > 7 && daysLeft <= 30;

  return (
    <div style={{
      background: '#fff', border: '1px solid rgba(0,0,0,0.08)',
      borderRadius: 8, padding: 10,
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Space>
          <Text strong>{placement.employee_name}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>{placement.employee_nik}</Text>
          {placement.is_active ? (
            <Tag color="green">Active</Tag>
          ) : <Tag color="default">Ended</Tag>}
        </Space>
        <div style={{ fontSize: 12, marginTop: 2 }}>
          {placement.role_at_client}{' · '}
          <Text type="secondary">
            {dayjs(placement.start_date).format('DD MMM YY')} →{' '}
            {placement.end_date ? dayjs(placement.end_date).format('DD MMM YY') : 'open-ended'}
          </Text>
          {daysLeft !== null && placement.is_active && (
            <Text style={{
              marginLeft: 8, fontSize: 11,
              color: overdue ? '#FF3B30' : dueSoon ? '#FF9500' : undefined,
              fontWeight: overdue || dueSoon ? 700 : 400,
            }}>
              ({daysLeft > 0 ? `${daysLeft} hari lagi` : `lewat ${-daysLeft}`})
            </Text>
          )}
        </div>
      </div>
      <Tooltip title="Request KPI Assessment from client">
        <Button size="small" icon={<SendOutlined />}
          disabled={!placement.is_active}
          onClick={onRequestKpi}>
          Request KPI
        </Button>
      </Tooltip>
    </div>
  );
}

function KpiRequestModal({
  placement, open, onClose,
}: {
  placement: Placement | null; open: boolean; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form] = Form.useForm();
  const [resultKpi, setResultKpi] = useState<ClientKpiAssessment | null>(null);

  const createMut = useMutation({
    mutationFn: createKpiRequest,
    onSuccess: (data) => {
      message.success('KPI request created — copy link untuk kirim ke client');
      setResultKpi(data);
      queryClient.invalidateQueries({ queryKey: ['client-dashboard'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create KPI request'),
  });

  if (!placement) return null;

  const publicUrl = resultKpi
    ? `${window.location.origin}/public/client-kpi/${resultKpi.token}`
    : '';

  const copyLink = () => {
    navigator.clipboard.writeText(publicUrl);
    message.success('Link copied to clipboard');
  };

  return (
    <Modal
      title={`KPI Request — ${placement.employee_name}`}
      open={open} onCancel={() => { setResultKpi(null); form.resetFields(); onClose(); }}
      footer={null} destroyOnClose width={560}
    >
      {!resultKpi ? (
        <Form
          form={form} layout="vertical"
          initialValues={{
            assessment_period: dayjs().format('YYYY-MM'),
            expires_in_days: 14,
          }}
          onFinish={(v) => createMut.mutate({ placement_id: placement.id, ...v })}
        >
          <div style={{
            background: 'rgba(0,113,227,0.05)', padding: 10, borderRadius: 6,
            marginBottom: 14, fontSize: 12,
          }}>
            Karyawan: <strong>{placement.employee_name}</strong>{' · '}
            Client: <strong>{placement.client_code}</strong>{' '}
            ({placement.role_at_client})
          </div>
          <Form.Item label="Assessment Period (YYYY-MM)" name="assessment_period"
            rules={[{ required: true, pattern: /^\d{4}-(0[1-9]|1[0-2])$/ }]}>
            <Input placeholder="2026-05" />
          </Form.Item>
          <Form.Item label="Token Expires In (days)" name="expires_in_days">
            <Input type="number" min={1} max={90} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Generate Link
          </Button>
        </Form>
      ) : (
        <div>
          <div style={{
            background: 'rgba(52,199,89,0.08)', padding: 12, borderRadius: 8,
            marginBottom: 14,
          }}>
            <Text strong style={{ color: '#34C759' }}>✓ Link generated</Text>
            <div style={{ fontSize: 11, color: '#6e6e73', marginTop: 4 }}>
              Expires: {dayjs(resultKpi.token_expires_at).format('DD MMM YYYY')} ·
              Period: {resultKpi.assessment_period}
            </div>
          </div>
          <Form.Item label="Public Link (kirim ke client PIC)">
            <Input.Group compact>
              <Input value={publicUrl} readOnly style={{ width: 'calc(100% - 88px)' }} />
              <Button icon={<CopyOutlined />} onClick={copyLink}>Copy</Button>
            </Input.Group>
          </Form.Item>
          <Text type="secondary" style={{ fontSize: 11 }}>
            Email/WA link ini ke <strong>{placement.client_name}</strong> PIC.
            Client buka tanpa login → submit ratings → IDE Asia terima feedback.
          </Text>
        </div>
      )}
    </Modal>
  );
}

function KpiHistoryDrawer({
  clientId, open, onClose,
}: {
  clientId: string; open: boolean; onClose: () => void;
}) {
  const q = useQuery({
    queryKey: ['client-kpi-history', clientId],
    queryFn: () => listKpiAssessments({ client_id: clientId }),
    enabled: !!clientId && open,
  });

  return (
    <Drawer title="KPI History" open={open} onClose={onClose} width={620}>
      {q.isLoading ? <Spin /> :
        (q.data ?? []).length === 0 ? <Empty description="Belum ada KPI assessment" /> : (
          <Space direction="vertical" size={10} style={{ width: '100%' }}>
            {(q.data ?? []).map((kpi: ClientKpiAssessment) => (
              <div key={kpi.id} style={{
                background: kpi.submitted_at ? 'rgba(52,199,89,0.05)' : 'rgba(255,149,0,0.05)',
                border: '1px solid ' + (kpi.submitted_at ? 'rgba(52,199,89,0.2)' : 'rgba(255,149,0,0.2)'),
                padding: 12, borderRadius: 8,
              }}>
                <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                  <div>
                    <Text strong>{kpi.placement_employee_name}</Text>
                    <Text type="secondary" style={{ fontSize: 11, marginLeft: 6 }}>
                      ({kpi.placement_role}) · {kpi.assessment_period}
                    </Text>
                  </div>
                  {kpi.submitted_at ? (
                    <Tag color="green">
                      ★ {kpi.overall_score ? Number(kpi.overall_score).toFixed(2) : '—'}
                    </Tag>
                  ) : kpi.is_expired ? (
                    <Tag color="red">Expired</Tag>
                  ) : (
                    <Tag color="orange">Pending</Tag>
                  )}
                </Space>
                <div style={{ fontSize: 11, color: '#6e6e73', marginTop: 4 }}>
                  Sent {dayjs(kpi.sent_at).format('DD MMM YY')}
                  {kpi.submitted_at && ` · Submitted ${dayjs(kpi.submitted_at).format('DD MMM YY')}`}
                  {!kpi.submitted_at && ` · Expires ${dayjs(kpi.token_expires_at).format('DD MMM YY')}`}
                </div>
                {kpi.submitted_at && kpi.overall_score && (
                  <div style={{ marginTop: 8, fontSize: 11 }}>
                    Q: {kpi.score_quality} · C: {kpi.score_communication} ·
                    A: {kpi.score_attendance} · P: {kpi.score_professionalism} ·
                    I: {kpi.score_initiative}
                  </div>
                )}
                {kpi.feedback && (
                  <div style={{ marginTop: 6, fontSize: 11, fontStyle: 'italic' }}>
                    "{kpi.feedback}"
                  </div>
                )}
              </div>
            ))}
          </Space>
        )}
    </Drawer>
  );
}
