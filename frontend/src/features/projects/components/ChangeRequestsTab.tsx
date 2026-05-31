/**
 * ChangeRequestsTab — TSK-070.
 *
 * Per-project CR module: list + create + approval flow (L1 → L2 → APPROVED/REJECTED).
 * Auto-notify Finance kalau cost_delta != 0 + Sales kalau project type CLIENT.
 */

import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  PlusOutlined,
  SendOutlined,
  StopOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Drawer, Empty, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Spin, Table, Tag, Tooltip, Typography} from 'antd';
import { message } from '@/lib/notify';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  approveCRL1,
  approveCRL2,
  cancelCR,
  createChangeRequest,
  crStatusColor,
  listChangeRequests,
  rejectCR,
  submitCR,
  type ChangeRequest,
  type CRImpact,
} from '@/api/changeRequests';
import { useAuthStore } from '@/store/auth';

const { Text, Title } = Typography;

const IMPACTS: CRImpact[] = ['SCOPE', 'TIMELINE', 'COST', 'MIXED'];

const fmtIDR = (val: string | number) => {
  const n = typeof val === 'string' ? Number(val) : val;
  if (Number.isNaN(n) || n === 0) return '—';
  return `Rp ${n.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
};

interface ChangeRequestsTabProps {
  projectId: string;
}

export function ChangeRequestsTab({ projectId }: ChangeRequestsTabProps) {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailCR, setDetailCR] = useState<ChangeRequest | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [rejectForm] = Form.useForm();
  const [rejectOpen, setRejectOpen] = useState(false);

  const query = useQuery({
    queryKey: ['change-requests', projectId],
    queryFn: () => listChangeRequests(projectId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['change-requests', projectId] });
  };

  const createMut = useMutation({
    mutationFn: (d: any) => createChangeRequest(projectId, d),
    onSuccess: () => {
      message.success('Change Request dibuat'); invalidate();
      setCreateOpen(false); createForm.resetFields();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal create'),
  });

  const submitMut = useMutation({
    mutationFn: (id: string) => submitCR(id),
    onSuccess: () => { message.success('CR di-submit untuk approval'); invalidate(); },
  });
  const approveL1Mut = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => approveCRL1(id, notes),
    onSuccess: () => { message.success('Approved Layer 1'); invalidate(); },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal approve L1'),
  });
  const approveL2Mut = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes?: string }) => approveCRL2(id, notes),
    onSuccess: () => {
      message.success('Approved Layer 2 — Finance & Sales notified');
      invalidate(); setDetailOpen(false);
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal approve L2'),
  });
  const rejectMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => rejectCR(id, reason),
    onSuccess: () => { message.success('CR rejected'); invalidate(); setRejectOpen(false); rejectForm.resetFields(); },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal reject'),
  });
  const cancelMut = useMutation({
    mutationFn: (id: string) => cancelCR(id),
    onSuccess: () => { message.success('CR cancelled'); invalidate(); },
  });

  const items = query.data ?? [];

  const isRequester = (cr: ChangeRequest) => cr.requester_user_id === currentUser?.id;
  const canApproveL1 = (cr: ChangeRequest) =>
    cr.status === 'PENDING_L1' && cr.requester_user_id !== currentUser?.id;
  const canApproveL2 = (cr: ChangeRequest) =>
    cr.status === 'PENDING_L2' &&
    cr.requester_user_id !== currentUser?.id &&
    cr.layer1_approver_id !== currentUser?.id;

  const columns: ColumnsType<ChangeRequest> = [
    {
      title: 'CR No', dataIndex: 'cr_number', key: 'no', width: 130,
      render: (v: string) => (
        <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontWeight: 700, color: 'var(--ide-blue, #0071E3)' }}>
          {v}
        </Text>
      ),
    },
    {
      title: 'Title', key: 'title',
      render: (_, r) => (
        <div>
          <div style={{ fontWeight: 600 }}>{r.title}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>
            by {r.requester_nik ?? '—'} · {dayjs(r.created_at).format('DD MMM YY')}
          </Text>
        </div>
      ),
    },
    {
      title: 'Impact', dataIndex: 'impact_category', key: 'impact', width: 100,
      render: (v: CRImpact) => <Tag>{v}</Tag>,
    },
    {
      title: 'Timeline Δ', dataIndex: 'timeline_delta_days', key: 'tl', width: 100, align: 'right',
      render: (v: number) => v === 0 ? '—' : (
        <Text style={{ color: v > 0 ? 'var(--ide-orange, #FF9500)' : 'var(--ide-green, #34C759)' }}>
          {v > 0 ? '+' : ''}{v}d
        </Text>
      ),
    },
    {
      title: 'Cost Δ', dataIndex: 'cost_delta', key: 'cost', width: 130, align: 'right',
      render: (v: string) => fmtIDR(v),
    },
    {
      title: 'Status', dataIndex: 'status', key: 'status', width: 130,
      render: (s: any) => {
        const c = crStatusColor(s);
        return <Tag className={c.className}>{c.label}</Tag>;
      },
    },
    {
      title: 'Notif', key: 'notif', width: 100,
      render: (_, r) => (
        <Space size={2} style={{ fontSize: 10 }}>
          {r.finance_notified_at && <Tag color="blue">FIN</Tag>}
          {r.sales_notified_at && <Tag color="purple">SAL</Tag>}
        </Space>
      ),
    },
    {
      title: 'Actions', key: 'act', width: 200, align: 'center',
      render: (_, r) => (
        <Space size={4}>
          {r.status === 'DRAFT' && isRequester(r) && (
            <Tooltip title="Submit untuk approval">
              <Button size="small" type="primary" icon={<SendOutlined />}
                onClick={() => submitMut.mutate(r.id)} />
            </Tooltip>
          )}
          {canApproveL1(r) && (
            <Tooltip title="Approve L1">
              <Button size="small" icon={<CheckCircleOutlined />} style={{ color: '#34C759' }}
                onClick={() => approveL1Mut.mutate({ id: r.id })} />
            </Tooltip>
          )}
          {canApproveL2(r) && (
            <Tooltip title="Approve L2 (Final)">
              <Button size="small" type="primary" icon={<CheckCircleOutlined />}
                onClick={() => approveL2Mut.mutate({ id: r.id })} />
            </Tooltip>
          )}
          {(r.status === 'PENDING_L1' || r.status === 'PENDING_L2') && !isRequester(r) && (
            <Tooltip title="Reject">
              <Button size="small" danger icon={<CloseCircleOutlined />}
                onClick={() => { setDetailCR(r); setRejectOpen(true); }} />
            </Tooltip>
          )}
          {(r.status === 'DRAFT' || r.status === 'PENDING_L1') && isRequester(r) && (
            <Popconfirm title="Cancel CR?" onConfirm={() => cancelMut.mutate(r.id)}>
              <Button size="small" icon={<StopOutlined />} />
            </Popconfirm>
          )}
          <Button size="small" onClick={() => { setDetailCR(r); setDetailOpen(true); }}>
            Detail
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Change Request per project — 2-layer approval. L2 approve auto-notify Finance (kalau ada cost impact) + Sales (kalau project CLIENT).
        </Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          New CR
        </Button>
      </div>

      {query.isLoading ? <Spin /> :
        items.length === 0 ? <Empty description="Belum ada Change Request" /> :
          <Table rowKey="id" columns={columns} dataSource={items} size="small" pagination={{ pageSize: 15 }} />}

      <Modal
        title="New Change Request" open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        footer={null} destroyOnHidden width={620}
      >
        <Form
          form={createForm} layout="vertical"
          initialValues={{ impact_category: 'MIXED', currency: 'IDR', timeline_delta_days: 0, cost_delta: 0 }}
          onFinish={(v) => createMut.mutate(v)}
        >
          <Form.Item label="Title" name="title" rules={[{ required: true }]}>
            <Input placeholder="Tambah modul reporting baru" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <Form.Item label="Impact" name="impact_category">
              <Select options={IMPACTS.map((i) => ({ value: i, label: i }))} />
            </Form.Item>
            <Form.Item label="Timeline Δ (days)" name="timeline_delta_days">
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Cost Δ" name="cost_delta">
              <InputNumber
                style={{ width: '100%' }}
                formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                parser={(v) => (v ? Number(v.replace(/[^0-9-]/g, '')) : 0) as any}
              />
            </Form.Item>
          </div>
          <Form.Item label="Scope Delta (detail change scope)" name="scope_delta">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} placeholder="Misal: tambah 3 dashboard, ubah API rate limit, dst" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Create (Draft)
          </Button>
        </Form>
      </Modal>

      <Modal
        title="Reject CR" open={rejectOpen}
        onCancel={() => { setRejectOpen(false); rejectForm.resetFields(); }}
        footer={null} destroyOnHidden
      >
        <Form
          form={rejectForm} layout="vertical"
          onFinish={(v) => detailCR && rejectMut.mutate({ id: detailCR.id, reason: v.rejection_reason })}
        >
          <Form.Item label="Rejection Reason" name="rejection_reason" rules={[{ required: true, min: 5 }]}>
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} placeholder="Alasan reject — minimal 5 karakter" />
          </Form.Item>
          <Button type="primary" danger htmlType="submit" loading={rejectMut.isPending} block>
            Reject
          </Button>
        </Form>
      </Modal>

      <Drawer
        title={detailCR ? `${detailCR.cr_number} — ${detailCR.title}` : 'CR Detail'}
        open={detailOpen} onClose={() => setDetailOpen(false)} width={520}
      >
        {detailCR && (
          <Space direction="vertical" size={14} style={{ width: '100%' }}>
            <div>
              <Tag className={crStatusColor(detailCR.status).className}>
                {crStatusColor(detailCR.status).label}
              </Tag>
              <Tag>{detailCR.impact_category}</Tag>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Description</Text>
              <div>{detailCR.description ?? '—'}</div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Scope Delta</Text>
              <div style={{ whiteSpace: 'pre-wrap' }}>{detailCR.scope_delta ?? '—'}</div>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Timeline Impact</Text>
                <div><strong>{detailCR.timeline_delta_days > 0 ? '+' : ''}{detailCR.timeline_delta_days} hari</strong></div>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Cost Impact</Text>
                <div><strong>{fmtIDR(detailCR.cost_delta)}</strong></div>
              </div>
            </div>
            <div>
              <Title level={5}>Approval Trail</Title>
              <Text style={{ fontSize: 12 }}>
                Requester: <strong>{detailCR.requester_nik}</strong>{' '}
                ({dayjs(detailCR.created_at).format('DD MMM HH:mm')})
              </Text>
              {detailCR.layer1_approver_nik && (
                <div style={{ marginTop: 4 }}>
                  <Text style={{ fontSize: 12 }}>
                    L1: <strong>{detailCR.layer1_approver_nik}</strong>{' '}
                    ({detailCR.layer1_approved_at})
                    {detailCR.layer1_notes && <em> — {detailCR.layer1_notes}</em>}
                  </Text>
                </div>
              )}
              {detailCR.layer2_approver_nik && (
                <div style={{ marginTop: 4 }}>
                  <Text style={{ fontSize: 12 }}>
                    L2: <strong>{detailCR.layer2_approver_nik}</strong>{' '}
                    ({detailCR.layer2_approved_at})
                    {detailCR.layer2_notes && <em> — {detailCR.layer2_notes}</em>}
                  </Text>
                </div>
              )}
              {detailCR.rejected_at && (
                <div style={{ marginTop: 4, color: 'var(--ide-red, #FF3B30)' }}>
                  <Text style={{ fontSize: 12 }}>
                    REJECTED ({detailCR.rejected_at}): {detailCR.rejection_reason}
                  </Text>
                </div>
              )}
            </div>
            {(detailCR.finance_notified_at || detailCR.sales_notified_at) && (
              <div style={{ background: 'rgba(0,113,227,0.05)', padding: 10, borderRadius: 6 }}>
                <Text strong style={{ fontSize: 12 }}>Auto-notifications:</Text>
                <ul style={{ marginTop: 4, marginBottom: 0, paddingLeft: 18, fontSize: 12 }}>
                  {detailCR.finance_notified_at && (
                    <li>Finance notified {detailCR.finance_notified_at} (cost impact)</li>
                  )}
                  {detailCR.sales_notified_at && (
                    <li>Sales notified {detailCR.sales_notified_at} (CLIENT project)</li>
                  )}
                </ul>
              </div>
            )}
          </Space>
        )}
      </Drawer>
    </div>
  );
}
