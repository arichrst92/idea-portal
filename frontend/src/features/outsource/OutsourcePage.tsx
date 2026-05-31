/**
 * OutsourcePage — TSK-100 Outsource Placement Management.
 *
 * Tabs: Placements (default), Clients (master).
 * Placement table: employee, client, role, dates, billing type+rate,
 * monthly estimate, days until end (red kalau <30d).
 */

import {
  ApartmentOutlined,
  CalendarOutlined,
  DeleteOutlined,
  PlusOutlined,
  TeamOutlined,
} from '@ant-design/icons';

import { ClientDashboardDrawer } from './ClientDashboardDrawer';
import { SpoTab } from './SpoTab';
import { TimesheetsTab } from './TimesheetsTab';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Empty, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Spin, Table, Tabs, Tag, Tooltip, Typography} from 'antd';
import { message } from '@/lib/notify';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';

import { listEmployees } from '@/api/organization';
import {
  createOutsourceClient,
  createPlacement,
  deletePlacement,
  listAmendments,
  listOutsourceClients,
  listPlacements,
  renewPlacement as renewPlacementApi,
  updatePlacement,
  type BillingType,
  type OutsourceClient,
  type Placement,
  type PlacementAmendment,
} from '@/api/outsource';

const { Text, Title } = Typography;

const fmtIDR = (val: string | number | null) => {
  if (val === null || val === undefined) return '—';
  const n = typeof val === 'string' ? Number(val) : val;
  if (Number.isNaN(n)) return '—';
  if (n >= 1_000_000_000) return `Rp ${(n / 1_000_000_000).toFixed(1)}M`;
  if (n >= 1_000_000) return `Rp ${(n / 1_000_000).toFixed(1)}jt`;
  return `Rp ${n.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
};

function KPI({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid rgba(0,0,0,0.06)',
      borderRadius: 10, padding: 14, flex: 1,
    }}>
      <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        {label}
      </Text>
      <div style={{ fontSize: 20, fontWeight: 700, marginTop: 2, color: color ?? undefined }}>
        {value}
      </div>
    </div>
  );
}

// ─── Placements Tab ──────────────────────────────────────────────

function PlacementsTab() {
  const queryClient = useQueryClient();
  const [activeFilter, setActiveFilter] = useState<boolean | undefined>(true);
  const [clientFilter, setClientFilter] = useState<string | undefined>();
  const [createOpen, setCreateOpen] = useState(false);
  const [form] = Form.useForm();
  const [renewPlacement, setRenewPlacement] = useState<Placement | null>(null);
  const [renewOpen, setRenewOpen] = useState(false);
  const [renewForm] = Form.useForm();

  const placementsQ = useQuery({
    queryKey: ['placements', activeFilter, clientFilter],
    queryFn: () => listPlacements({ is_active: activeFilter, client_id: clientFilter }),
  });
  const clientsQ = useQuery({
    queryKey: ['outsource-clients'],
    queryFn: listOutsourceClients,
  });
  const employeesQ = useQuery({
    queryKey: ['employees-for-outsource'],
    queryFn: () => listEmployees({ page: 1, page_size: 200 }),
  });

  const createMut = useMutation({
    mutationFn: createPlacement,
    onSuccess: () => {
      message.success('Placement dibuat');
      queryClient.invalidateQueries({ queryKey: ['placements'] });
      setCreateOpen(false); form.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create placement'),
  });

  const toggleActiveMut = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updatePlacement(id, { is_active }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['placements'] });
    },
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deletePlacement(id),
    onSuccess: () => {
      message.success('Placement dihapus');
      queryClient.invalidateQueries({ queryKey: ['placements'] });
    },
  });

  const items = placementsQ.data?.items ?? [];
  const meta = placementsQ.data;

  const columns: ColumnsType<Placement> = [
    {
      title: 'Karyawan', key: 'emp',
      render: (_, r) => (
        <div>
          <div style={{ fontWeight: 600 }}>{r.employee_name}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>{r.employee_nik}</Text>
        </div>
      ),
    },
    {
      title: 'Client', key: 'client',
      render: (_, r) => (
        <div>
          <Text strong style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12, color: 'var(--ide-blue, #0071E3)' }}>
            {r.client_code}
          </Text>
          <div style={{ fontSize: 11, color: 'var(--ide-ink3, #6e6e73)' }}>
            {r.client_name}
          </div>
        </div>
      ),
    },
    { title: 'Role', dataIndex: 'role_at_client', key: 'role' },
    {
      title: 'Period', key: 'period', width: 170,
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text style={{ fontSize: 12 }}>
            {dayjs(r.start_date).format('DD MMM YY')} → {r.end_date ? dayjs(r.end_date).format('DD MMM YY') : 'open-ended'}
          </Text>
          {r.days_until_end !== null && r.is_active && (
            <Text style={{
              fontSize: 11,
              color: r.days_until_end < 30 ? 'var(--ide-red, #FF3B30)' :
                     r.days_until_end < 90 ? 'var(--ide-orange, #FF9500)' :
                     'var(--ide-ink3, #6e6e73)',
              fontWeight: r.days_until_end < 30 ? 700 : 400,
            }}>
              {r.days_until_end > 0 ? `${r.days_until_end} hari lagi` : `Lewat ${-r.days_until_end} hari`}
            </Text>
          )}
        </Space>
      ),
    },
    {
      title: 'Billing', key: 'billing', width: 160, align: 'right',
      render: (_, r) => (
        <Space direction="vertical" size={0} style={{ alignItems: 'flex-end' }}>
          <Tag color={r.billing_type === 'FLAT' ? 'blue' : 'purple'}>
            {r.billing_type === 'FLAT' ? 'Flat Monthly' : 'Per Workday'}
          </Tag>
          <Text strong style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12 }}>
            {fmtIDR(r.billing_rate)}
            {r.billing_type === 'PER_WORKDAY' && <span style={{ fontSize: 10 }}> /hari</span>}
          </Text>
          <Text type="secondary" style={{ fontSize: 10 }}>
            ≈ {fmtIDR(r.monthly_billing_estimate)} /bulan
          </Text>
        </Space>
      ),
    },
    {
      title: 'Status', key: 'status', width: 90, align: 'center',
      render: (_, r) => (
        <Tag color={r.is_active ? 'green' : 'default'}>
          {r.is_active ? 'Active' : 'Ended'}
        </Tag>
      ),
    },
    {
      title: 'Actions', key: 'act', width: 170, align: 'center',
      render: (_, r) => (
        <Space size={4}>
          {r.is_active && (
            <Tooltip title="Renew / Amend (rate or end_date)">
              <Button size="small" type="primary"
                onClick={() => { setRenewPlacement(r); setRenewOpen(true); }}>
                Renew
              </Button>
            </Tooltip>
          )}
          {r.is_active ? (
            <Tooltip title="End placement">
              <Button size="small"
                onClick={() => toggleActiveMut.mutate({ id: r.id, is_active: false })}>
                End
              </Button>
            </Tooltip>
          ) : (
            <Tooltip title="Reactivate">
              <Button size="small"
                onClick={() => toggleActiveMut.mutate({ id: r.id, is_active: true })}>
                Activate
              </Button>
            </Tooltip>
          )}
          <Popconfirm title="Hapus placement?" onConfirm={() => deleteMut.mutate(r.id)}>
            <Button type="text" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      {/* KPI strip */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <KPI label="Total Placement" value={meta?.total ?? 0} />
        <KPI label="Active" value={meta?.active_count ?? 0} color="var(--ide-green, #34C759)" />
        <KPI label="Expiring 30d" value={meta?.expiring_30d ?? 0} color="var(--ide-orange, #FF9500)" />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>Filter:</Text>
          <Select
            value={activeFilter} onChange={setActiveFilter}
            style={{ width: 140 }}
            options={[
              { value: true, label: 'Active only' },
              { value: false, label: 'Ended only' },
              { value: undefined as any, label: 'All' },
            ]}
          />
          <Select
            allowClear placeholder="All clients" style={{ width: 200 }}
            value={clientFilter} onChange={setClientFilter}
            options={(clientsQ.data ?? []).map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` }))}
          />
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          New Placement
        </Button>
      </div>

      {placementsQ.isLoading ? <Spin /> :
        items.length === 0 ? <Empty description="Belum ada placement" /> :
          <Table rowKey="id" columns={columns} dataSource={items} size="small" pagination={{ pageSize: 20 }} />}

      <Modal title="New Placement" open={createOpen}
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        footer={null} destroyOnHidden width={620}
      >
        <Form
          form={form} layout="vertical"
          initialValues={{ billing_type: 'FLAT', billing_rate: 5000000 }}
          onFinish={(v) => createMut.mutate(v)}
        >
          <Form.Item label="Karyawan" name="employee_id" rules={[{ required: true }]}>
            <Select
              showSearch optionFilterProp="label" placeholder="Pilih karyawan outsource"
              options={(employeesQ.data?.items ?? []).map((e: any) => ({
                value: e.id, label: `${e.nik} — ${e.full_name}`,
              }))}
            />
          </Form.Item>
          <Form.Item label="Client" name="client_id" rules={[{ required: true }]}>
            <Select
              showSearch optionFilterProp="label" placeholder="Pilih client"
              options={(clientsQ.data ?? []).map((c) => ({
                value: c.id, label: `${c.code} — ${c.name}`,
              }))}
            />
          </Form.Item>
          <Form.Item label="Role at Client" name="role_at_client" rules={[{ required: true }]}>
            <Input placeholder="Senior Developer / Customer Service" />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Start Date (YYYY-MM-DD)" name="start_date" rules={[{ required: true }]}>
              <Input placeholder="2026-06-01" />
            </Form.Item>
            <Form.Item label="End Date (opsional)" name="end_date">
              <Input placeholder="2026-12-31" />
            </Form.Item>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Billing Type" name="billing_type">
              <Select options={[
                { value: 'FLAT', label: 'Flat Monthly' },
                { value: 'PER_WORKDAY', label: 'Per Workday' },
              ] as { value: BillingType; label: string }[]} />
            </Form.Item>
            <Form.Item label="Billing Rate (Rp)" name="billing_rate" rules={[{ required: true }]}>
              <InputNumber
                min={0} style={{ width: '100%' }}
                formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
              />
            </Form.Item>
          </div>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Create
          </Button>
        </Form>
      </Modal>

      <RenewPlacementModal
        placement={renewPlacement}
        open={renewOpen}
        onClose={() => { setRenewOpen(false); setRenewPlacement(null); renewForm.resetFields(); }}
        form={renewForm}
      />
    </div>
  );
}

// ─── Renew Placement Modal (TSK-107) ─────────────────────────────

function RenewPlacementModal({
  placement, open, onClose, form,
}: {
  placement: Placement | null;
  open: boolean;
  onClose: () => void;
  form: any;
}) {
  const queryClient = useQueryClient();

  const amendmentsQ = useQuery({
    queryKey: ['amendments', placement?.id],
    queryFn: () => listAmendments(placement!.id),
    enabled: !!placement && open,
  });

  const renewMut = useMutation({
    mutationFn: (data: any) => renewPlacementApi(placement!.id, data),
    onSuccess: () => {
      message.success('Placement diperbarui');
      queryClient.invalidateQueries({ queryKey: ['placements'] });
      queryClient.invalidateQueries({ queryKey: ['amendments', placement?.id] });
      onClose();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal renew'),
  });

  if (!placement) return null;

  return (
    <Modal
      title={`Renew / Amend — ${placement.employee_name} → ${placement.client_code}`}
      open={open} onCancel={onClose} footer={null} destroyOnHidden width={680}
    >
      <div style={{
        background: 'rgba(0,113,227,0.05)', padding: 12, borderRadius: 8,
        marginBottom: 14, fontSize: 12,
      }}>
        <strong>Current:</strong>{' '}
        End date <strong>{placement.end_date ? dayjs(placement.end_date).format('DD MMM YY') : 'open-ended'}</strong>{' '}
        · Rate <strong>Rp {Number(placement.billing_rate).toLocaleString('id-ID')}</strong>{' '}
        ({placement.billing_type === 'FLAT' ? '/bulan' : '/hari'})
      </div>

      <Form
        form={form} layout="vertical"
        initialValues={{ effective_date: dayjs().format('YYYY-MM-DD') }}
        onFinish={(v) => renewMut.mutate(v)}
      >
        <Form.Item label="Effective Date" name="effective_date" rules={[{ required: true }]}>
          <Input placeholder="YYYY-MM-DD" />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <Form.Item label="New End Date (opsional)" name="new_end_date">
            <Input placeholder="YYYY-MM-DD" />
          </Form.Item>
          <Form.Item label="New Billing Rate (opsional)" name="new_billing_rate">
            <InputNumber
              min={0} style={{ width: '100%' }}
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
              parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
            />
          </Form.Item>
        </div>
        <Form.Item label="Document URL (MinIO obj, opsional)" name="document_url">
          <Input placeholder="outsource/amendments/AMD-xxx.pdf" />
        </Form.Item>
        <Form.Item label="Notes" name="notes">
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={renewMut.isPending} block>
          Apply Amendment
        </Button>
      </Form>

      {(amendmentsQ.data ?? []).length > 0 && (
        <>
          <Text strong style={{ fontSize: 12, display: 'block', marginTop: 18, marginBottom: 8 }}>
            History ({amendmentsQ.data!.length})
          </Text>
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            {amendmentsQ.data!.map((a: PlacementAmendment) => (
              <div key={a.id} style={{
                background: 'rgba(0,0,0,0.02)', padding: 10, borderRadius: 6,
                fontSize: 11,
              }}>
                <Space>
                  <Text strong style={{
                    fontFamily: 'ui-monospace, Menlo, monospace',
                    color: 'var(--ide-blue, #0071E3)',
                  }}>{a.amendment_no}</Text>
                  <Text type="secondary">{dayjs(a.effective_date).format('DD MMM YY')}</Text>
                  <Text type="secondary">by {a.created_by_nik ?? '—'}</Text>
                </Space>
                <div style={{ marginTop: 4 }}>
                  {a.old_end_date !== a.new_end_date && a.new_end_date && (
                    <span>End: {a.old_end_date ?? 'open'} → <strong>{a.new_end_date}</strong>{' · '}</span>
                  )}
                  {a.old_billing_rate !== a.new_billing_rate && a.new_billing_rate && (
                    <span>
                      Rate: Rp {Number(a.old_billing_rate ?? 0).toLocaleString('id-ID')} →{' '}
                      <strong>Rp {Number(a.new_billing_rate).toLocaleString('id-ID')}</strong>
                    </span>
                  )}
                </div>
                {a.notes && <div style={{ marginTop: 4, color: 'var(--ide-ink3, #6e6e73)' }}>{a.notes}</div>}
              </div>
            ))}
          </Space>
        </>
      )}
    </Modal>
  );
}

// ─── Clients Tab ─────────────────────────────────────────────────

function ClientsTab() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();
  const [activeClientId, setActiveClientId] = useState<string | null>(null);
  const [dashOpen, setDashOpen] = useState(false);

  const query = useQuery({ queryKey: ['outsource-clients'], queryFn: listOutsourceClients });

  const createMut = useMutation({
    mutationFn: createOutsourceClient,
    onSuccess: () => {
      message.success('Client dibuat');
      queryClient.invalidateQueries({ queryKey: ['outsource-clients'] });
      setOpen(false); form.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create client'),
  });

  const columns: ColumnsType<OutsourceClient> = [
    {
      title: 'Code', dataIndex: 'code', key: 'code', width: 100,
      render: (v: string) => (
        <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontWeight: 700, color: 'var(--ide-blue, #0071E3)' }}>
          {v}
        </Text>
      ),
    },
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'PIC', dataIndex: 'pic_name', key: 'pic' },
    {
      title: 'Email', dataIndex: 'pic_email', key: 'email',
      render: (v: string | null) => (
        <Text style={{ fontSize: 11 }}>{v ?? '—'}</Text>
      ),
    },
    {
      title: 'Placements', key: 'plac', width: 120, align: 'center',
      render: (_, r) => (
        <Space>
          <Text strong>{r.active_placement_count}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>/ {r.placement_count}</Text>
        </Space>
      ),
    },
    {
      title: 'Dashboard', key: 'dash', width: 110, align: 'center',
      render: (_, r) => (
        <Button size="small" type="primary"
          onClick={() => { setActiveClientId(r.id); setDashOpen(true); }}>
          View
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Master client outsource — perusahaan yang menerima placement karyawan IDEA.
        </Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          New Client
        </Button>
      </div>

      {query.isLoading ? <Spin /> :
        (query.data ?? []).length === 0 ? <Empty description="Belum ada client" /> :
          <Table rowKey="id" columns={columns} dataSource={query.data ?? []} size="small" />}

      <Modal title="New Client" open={open}
        onCancel={() => { setOpen(false); form.resetFields(); }}
        footer={null} destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={(v) => createMut.mutate(v)}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10 }}>
            <Form.Item label="Code" name="code" rules={[{ required: true }]}>
              <Input placeholder="CLI-001" />
            </Form.Item>
            <Form.Item label="Name" name="name" rules={[{ required: true }]}>
              <Input placeholder="PT Klien Outsource" />
            </Form.Item>
          </div>
          <Form.Item label="PIC Name" name="pic_name">
            <Input />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="PIC Email" name="pic_email">
              <Input type="email" />
            </Form.Item>
            <Form.Item label="PIC Phone" name="pic_phone">
              <Input />
            </Form.Item>
          </div>
          <Form.Item label="Address" name="address">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Create
          </Button>
        </Form>
      </Modal>

      <ClientDashboardDrawer
        clientId={activeClientId}
        open={dashOpen}
        onClose={() => { setDashOpen(false); setActiveClientId(null); }}
      />
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function OutsourcePage() {
  return (
    <div style={{ padding: '20px 24px', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <Title level={3} style={{ margin: 0 }}>Outsource Management</Title>
        <Text type="secondary" style={{ fontSize: 13 }}>
          Placement karyawan ke client + master client. Timesheet flow + BA + SP-O di TSK lanjutan.
        </Text>
      </div>

      <Tabs
        defaultActiveKey="placements"
        items={[
          { key: 'placements', label: <span><TeamOutlined /> Placements</span>, children: <PlacementsTab /> },
          { key: 'timesheets', label: <span><CalendarOutlined /> Timesheets</span>, children: <TimesheetsTab /> },
          { key: 'spo', label: <span>⚠️ Complaints / SP-O</span>, children: <SpoTab /> },
          { key: 'clients', label: <span><ApartmentOutlined /> Clients</span>, children: <ClientsTab /> },
        ]}
      />
    </div>
  );
}
