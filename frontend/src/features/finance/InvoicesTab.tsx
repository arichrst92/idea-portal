/**
 * InvoicesTab — Finance/Invoice list + create + payment tracking + aging
 * (TSK-022D).
 *
 * Features:
 * - KPI strip: total outstanding, paid YTD, overdue count, current count
 * - Status filter + aging bucket coloring
 * - Create invoice with PPN auto-compute
 * - Payment tracking modal (set paid_amount → auto-status PARTIAL/PAID)
 * - Soft delete (cancel) for non-paid invoices
 */

import { DeleteOutlined, DollarOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useMemo, useState } from 'react';

import {
  createInvoice,
  deleteInvoice,
  invoiceStatusColor,
  listInvoices,
  updateInvoice,
  type InvoiceListItem,
  type InvoiceStatus,
} from '@/api/finance';
import { listProjects } from '@/api/projects';

const { Text } = Typography;

const STATUSES: InvoiceStatus[] = [
  'PENDING', 'SENT', 'PARTIAL', 'PAID', 'OVERDUE', 'CANCELLED',
];

const fmtIDR = (val: number | string) => {
  const n = typeof val === 'string' ? Number(val) : val;
  if (Number.isNaN(n)) return '—';
  if (n >= 1_000_000_000) return `Rp ${(n / 1_000_000_000).toFixed(2)}M`;
  if (n >= 1_000_000) return `Rp ${(n / 1_000_000).toFixed(1)}jt`;
  if (n >= 1_000) return `Rp ${(n / 1_000).toFixed(0)}rb`;
  return `Rp ${n.toLocaleString('id-ID')}`;
};

const fmtIDRfull = (val: number | string) => {
  const n = typeof val === 'string' ? Number(val) : val;
  if (Number.isNaN(n)) return '—';
  return `Rp ${n.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
};

const agingColor = (bucket: string | null) => {
  switch (bucket) {
    case 'PAID': return 'green';
    case 'CURRENT': return 'blue';
    case '1-30': return 'orange';
    case '31-60': return 'volcano';
    case '61-90': return 'red';
    case '90+': return 'magenta';
    default: return 'default';
  }
};

function KPI({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid rgba(0,0,0,0.06)',
        borderRadius: 10,
        padding: 14,
        flex: 1,
      }}
    >
      <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        {label}
      </Text>
      <div style={{ fontSize: 20, fontWeight: 700, marginTop: 2, color: color ?? undefined }}>
        {value}
      </div>
    </div>
  );
}

export default function InvoicesTab() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [activeInvoice, setActiveInvoice] = useState<InvoiceListItem | null>(null);
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | undefined>();
  const [createForm] = Form.useForm();
  const [paymentForm] = Form.useForm();

  const query = useQuery({
    queryKey: ['invoices', statusFilter],
    queryFn: () => listInvoices({ status: statusFilter, page_size: 100 }),
  });

  const projectsQ = useQuery({
    queryKey: ['projects-for-invoice'],
    queryFn: () => listProjects({ page_size: 100 }),
  });

  const createMut = useMutation({
    mutationFn: createInvoice,
    onSuccess: () => {
      message.success('Invoice created');
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      setCreateOpen(false);
      createForm.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create invoice'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateInvoice(id, data),
    onSuccess: () => {
      message.success('Invoice updated');
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
      setPaymentOpen(false);
      paymentForm.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal update invoice'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteInvoice(id),
    onSuccess: () => {
      message.success('Invoice dihapus');
      queryClient.invalidateQueries({ queryKey: ['invoices'] });
    },
  });

  const items = query.data?.items ?? [];

  const kpi = useMemo(() => {
    let outstanding = 0, paid = 0, overdueCount = 0, currentCount = 0;
    const yearStart = dayjs().startOf('year');
    items.forEach((inv) => {
      const total = Number(inv.total_amount);
      const paidAmt = Number(inv.paid_amount);
      if (inv.status !== 'CANCELLED') {
        outstanding += total - paidAmt;
      }
      if (inv.status === 'PAID' && inv.paid_at && dayjs(inv.paid_at).isAfter(yearStart)) {
        paid += total;
      }
      if (inv.aging_bucket && inv.aging_bucket !== 'CURRENT' && inv.aging_bucket !== 'PAID') {
        overdueCount += 1;
      }
      if (inv.aging_bucket === 'CURRENT') currentCount += 1;
    });
    return { outstanding, paid, overdueCount, currentCount };
  }, [items]);

  const columns: ColumnsType<InvoiceListItem> = [
    {
      title: 'Invoice No', dataIndex: 'invoice_no', key: 'invoice_no', width: 140,
      render: (v: string) => (
        <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontWeight: 700, color: 'var(--ide-blue, #0071E3)' }}>
          {v}
        </Text>
      ),
    },
    {
      title: 'Project / Client', key: 'project',
      render: (_, r) => (
        <div>
          {r.project_code && (
            <div style={{ fontSize: 12 }}>
              <Text strong>{r.project_code}</Text>{' '}
              <Text type="secondary" style={{ fontSize: 11 }}>{r.project_name}</Text>
            </div>
          )}
          {r.client_name_snapshot && (
            <div style={{ fontSize: 11, color: 'var(--ide-ink3, #6e6e73)' }}>
              {r.client_name_snapshot}
            </div>
          )}
          {!r.project_code && !r.client_name_snapshot && (
            <Text type="secondary" style={{ fontSize: 11 }}>—</Text>
          )}
        </div>
      ),
    },
    {
      title: 'Amount (Total)', key: 'amount', align: 'right', width: 140,
      render: (_, r) => (
        <Tooltip title={`Base ${fmtIDRfull(r.amount)} + PPN ${r.tax_pct}% = ${fmtIDRfull(r.total_amount)}`}>
          <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontWeight: 600 }}>
            {fmtIDR(r.total_amount)}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: 'Paid', key: 'paid', align: 'right', width: 110,
      render: (_, r) => {
        const paid = Number(r.paid_amount);
        const total = Number(r.total_amount);
        const pct = total > 0 ? Math.round((paid / total) * 100) : 0;
        return (
          <Space direction="vertical" size={0}>
            <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12 }}>
              {fmtIDR(paid)}
            </Text>
            <Text type="secondary" style={{ fontSize: 10 }}>{pct}%</Text>
          </Space>
        );
      },
    },
    {
      title: 'Status', dataIndex: 'status', key: 'status', width: 110,
      render: (s: InvoiceStatus) => {
        const conf = invoiceStatusColor(s);
        return <Tag className={conf.className}>{conf.label}</Tag>;
      },
    },
    {
      title: 'Aging', dataIndex: 'aging_bucket', key: 'aging', width: 100,
      render: (b: string | null, r) => {
        if (!b) return <Text type="secondary" style={{ fontSize: 11 }}>—</Text>;
        return (
          <Tooltip title={r.days_overdue ? `${r.days_overdue} hari overdue` : 'Belum jatuh tempo'}>
            <Tag color={agingColor(b)}>{b}</Tag>
          </Tooltip>
        );
      },
    },
    {
      title: 'Due Date', dataIndex: 'due_date', key: 'due', width: 110,
      render: (d: string | null) => (
        d ? <Text style={{ fontSize: 12 }}>{dayjs(d).format('DD MMM YY')}</Text> : <Text type="secondary">—</Text>
      ),
    },
    {
      title: 'Action', key: 'action', width: 100, align: 'center',
      render: (_, r) => (
        <Space size={4}>
          <Tooltip title="Record payment">
            <Button
              type="text" size="small" icon={<DollarOutlined />}
              disabled={r.status === 'PAID' || r.status === 'CANCELLED'}
              onClick={() => {
                setActiveInvoice(r);
                paymentForm.setFieldsValue({
                  paid_amount: Number(r.paid_amount),
                });
                setPaymentOpen(true);
              }}
            />
          </Tooltip>
          <Popconfirm title="Cancel invoice ini?" onConfirm={() => deleteMut.mutate(r.id)}>
            <Button type="text" size="small" danger icon={<DeleteOutlined />} disabled={r.status === 'PAID'} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* KPI strip */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <KPI label="Outstanding (AR)" value={fmtIDR(kpi.outstanding)} color="var(--ide-orange, #FF9500)" />
        <KPI label="Paid YTD" value={fmtIDR(kpi.paid)} color="var(--ide-green, #34C759)" />
        <KPI label="Overdue" value={kpi.overdueCount} color="var(--ide-red, #FF3B30)" />
        <KPI label="Current" value={kpi.currentCount} color="var(--ide-blue, #0071E3)" />
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>Filter status:</Text>
          <Select
            allowClear placeholder="Semua status" style={{ width: 160 }}
            value={statusFilter} onChange={setStatusFilter}
            options={STATUSES.map((s) => ({ value: s, label: s }))}
          />
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          New Invoice
        </Button>
      </div>

      {query.isLoading ? (
        <Spin />
      ) : items.length === 0 ? (
        <Empty description="Belum ada invoice" />
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={items}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      )}

      {/* Create Modal */}
      <Modal
        title="Create Invoice"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        footer={null}
        destroyOnClose
        width={620}
      >
        <Form
          form={createForm}
          layout="vertical"
          initialValues={{ currency: 'IDR', tax_pct: 11 }}
          onFinish={(v) => createMut.mutate(v)}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Invoice No" name="invoice_no" rules={[{ required: true }]}>
              <Input placeholder="INV-2026-001" style={{ fontFamily: 'ui-monospace, Menlo, monospace' }} />
            </Form.Item>
            <Form.Item label="Currency" name="currency">
              <Select options={[{ value: 'IDR', label: 'IDR' }, { value: 'USD', label: 'USD' }]} />
            </Form.Item>
          </div>

          <Form.Item label="Project (optional, link untuk auto-trigger via phase)" name="project_id">
            <Select
              allowClear showSearch optionFilterProp="label"
              placeholder="Standalone invoice / pilih project"
              options={(projectsQ.data?.items ?? []).map((p) => ({
                value: p.id,
                label: `${p.code} — ${p.name}`,
              }))}
            />
          </Form.Item>

          <Form.Item label="Client Name (snapshot, opsional)" name="client_name_snapshot">
            <Input placeholder="PT Klien ABC" />
          </Form.Item>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <Form.Item label="Termin %" name="termin_pct">
              <InputNumber min={0} max={100} style={{ width: '100%' }} placeholder="Optional" />
            </Form.Item>
            <Form.Item label="Amount (base)" name="amount" rules={[{ required: true }]}>
              <InputNumber
                min={0} style={{ width: '100%' }}
                formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
              />
            </Form.Item>
            <Form.Item label="Tax % (PPN)" name="tax_pct">
              <InputNumber min={0} max={100} step={1} style={{ width: '100%' }} />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Issue Date (YYYY-MM-DD)" name="issue_date">
              <Input placeholder="2026-05-29" />
            </Form.Item>
            <Form.Item label="Due Date (YYYY-MM-DD)" name="due_date">
              <Input placeholder="2026-06-29" />
            </Form.Item>
          </div>

          <Form.Item label="Notes" name="notes">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Create
          </Button>
        </Form>
      </Modal>

      {/* Payment Modal */}
      <Modal
        title={activeInvoice ? `Record Payment — ${activeInvoice.invoice_no}` : 'Record Payment'}
        open={paymentOpen}
        onCancel={() => { setPaymentOpen(false); paymentForm.resetFields(); }}
        footer={null}
        destroyOnClose
      >
        {activeInvoice && (
          <Form
            form={paymentForm}
            layout="vertical"
            onFinish={(v) => updateMut.mutate({ id: activeInvoice.id, data: v })}
          >
            <div style={{ background: 'rgba(0,113,227,0.05)', padding: 12, borderRadius: 8, marginBottom: 14 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>Total Amount:</Text>{' '}
              <Text strong>{fmtIDRfull(activeInvoice.total_amount)}</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>Currently Paid:</Text>{' '}
              <Text>{fmtIDRfull(activeInvoice.paid_amount)}</Text>
            </div>
            <Form.Item label="New Paid Amount (cumulative)" name="paid_amount" rules={[{ required: true }]}>
              <InputNumber
                min={0} max={Number(activeInvoice.total_amount)} style={{ width: '100%' }}
                formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
              />
            </Form.Item>
            <Form.Item label="Paid At (YYYY-MM-DD)" name="paid_at">
              <Input placeholder="2026-05-29" />
            </Form.Item>
            <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 10 }}>
              Status akan auto-flip: paid &lt; total → PARTIAL · paid ≥ total → PAID
            </Text>
            <Button type="primary" htmlType="submit" loading={updateMut.isPending} block>
              Save Payment
            </Button>
          </Form>
        )}
      </Modal>
    </div>
  );
}
