/**
 * PayrollPage — TSK-046.
 *
 * Tabs:
 *  - Configs   — payroll config per employee (basic_salary, allowance, BPJS)
 *  - Periods   — payroll period bulanan (create + generate slips + lock)
 *  - Slips     — list slip + detail komponen + add variable + set PPh21
 */

import {
  CalendarOutlined,
  CheckSquareOutlined,
  CloudDownloadOutlined,
  DollarOutlined,
  FilePdfOutlined,
  LockOutlined,
  PlusOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

import { AttendanceTab } from './AttendanceTab';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Drawer, Empty, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Spin, Table, Tabs, Tag, Tooltip, Typography} from 'antd';
import { message } from '@/lib/notify';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  addComponent,
  createPeriod,
  deleteComponent,
  generateSlipPdf,
  generateSlips,
  getSlip,
  getSlipPdfUrl,
  listConfigs,
  listPeriods,
  listSlips,
  lockPeriod,
  MONTHS_ID,
  periodLabel,
  periodStatusColor,
  setPph21,
  upsertConfig,
  type ComponentType,
  type PayrollConfig,
  type PayrollPeriod,
  type PayrollSlip,
} from '@/api/payroll';
import { listEmployees } from '@/api/organization';

const { Title, Text } = Typography;

const fmtIDR = (val: string | number) => {
  const n = typeof val === 'string' ? Number(val) : val;
  if (Number.isNaN(n)) return '—';
  return `Rp ${n.toLocaleString('id-ID', { maximumFractionDigits: 0 })}`;
};

// ─── Configs Tab ──────────────────────────────────────────────────

function ConfigsTab() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const query = useQuery({ queryKey: ['payroll-configs'], queryFn: () => listConfigs() });
  const employeesQ = useQuery({
    queryKey: ['employees-for-payroll'],
    queryFn: () => listEmployees({ page: 1, page_size: 200 }),
  });

  const upsertMut = useMutation({
    mutationFn: upsertConfig,
    onSuccess: () => {
      message.success('Config disimpan');
      queryClient.invalidateQueries({ queryKey: ['payroll-configs'] });
      setOpen(false);
      form.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal save config'),
  });

  const columns: ColumnsType<PayrollConfig> = [
    {
      title: 'NIK', dataIndex: 'employee_nik', key: 'nik', width: 100,
      render: (v: string | null) => (
        <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 12 }}>
          {v ?? '—'}
        </Text>
      ),
    },
    { title: 'Name', dataIndex: 'employee_name', key: 'name' },
    {
      title: 'Basic Salary', dataIndex: 'basic_salary', key: 'basic', align: 'right',
      render: (v: string) => <Text strong>{fmtIDR(v)}</Text>,
    },
    {
      title: 'Allowance', dataIndex: 'fixed_allowance', key: 'allow', align: 'right',
      render: (v: string) => fmtIDR(v),
    },
    {
      title: 'BPJS Kes %', dataIndex: 'bpjs_kesehatan_pct', key: 'bpjs_k',
      render: (v: string) => `${v}%`,
    },
    {
      title: 'BPJS TK %', dataIndex: 'bpjs_ketenagakerjaan_pct', key: 'bpjs_tk',
      render: (v: string) => `${v}%`,
    },
    {
      title: 'Effective', dataIndex: 'effective_date', key: 'eff', width: 110,
      render: (v: string) => dayjs(v).format('DD MMM YY'),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Payroll config per karyawan — basic salary, allowance, BPJS rate. Upsert akan create config baru
          dengan effective_date.
        </Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          Set Config
        </Button>
      </div>

      {query.isLoading ? (
        <Spin />
      ) : (query.data ?? []).length === 0 ? (
        <Empty description="Belum ada config" />
      ) : (
        <Table rowKey="id" columns={columns} dataSource={query.data ?? []} size="small" />
      )}

      <Modal
        title="Set Payroll Config" open={open}
        onCancel={() => setOpen(false)} footer={null} destroyOnHidden
        width={520}
      >
        <Form
          form={form} layout="vertical"
          initialValues={{
            bpjs_kesehatan_pct: 1.0,
            bpjs_ketenagakerjaan_pct: 2.0,
            effective_date: dayjs().format('YYYY-MM-DD'),
            fixed_allowance: 0,
          }}
          onFinish={(v) => upsertMut.mutate(v)}
        >
          <Form.Item label="Employee" name="employee_id" rules={[{ required: true }]}>
            <Select
              showSearch optionFilterProp="label"
              options={(employeesQ.data?.items ?? []).map((e: any) => ({
                value: e.id, label: `${e.nik} — ${e.full_name}`,
              }))}
            />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Basic Salary" name="basic_salary" rules={[{ required: true }]}>
              <InputNumber
                min={0} style={{ width: '100%' }}
                formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
              />
            </Form.Item>
            <Form.Item label="Fixed Allowance" name="fixed_allowance">
              <InputNumber
                min={0} style={{ width: '100%' }}
                formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
              />
            </Form.Item>
            <Form.Item label="BPJS Kesehatan %" name="bpjs_kesehatan_pct">
              <InputNumber min={0} max={100} step={0.1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="BPJS Ketenagakerjaan %" name="bpjs_ketenagakerjaan_pct">
              <InputNumber min={0} max={100} step={0.1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Effective Date" name="effective_date" rules={[{ required: true }]}>
              <Input placeholder="YYYY-MM-DD" />
            </Form.Item>
          </div>
          <Button type="primary" htmlType="submit" loading={upsertMut.isPending} block>
            Save
          </Button>
        </Form>
      </Modal>
    </div>
  );
}

// ─── Periods Tab ──────────────────────────────────────────────────

function PeriodsTab() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form] = Form.useForm();

  const query = useQuery({ queryKey: ['payroll-periods'], queryFn: listPeriods });

  const createMut = useMutation({
    mutationFn: createPeriod,
    onSuccess: () => {
      message.success('Periode dibuat');
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
      setOpen(false);
      form.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create periode'),
  });

  const generateMut = useMutation({
    mutationFn: (id: string) => generateSlips(id),
    onSuccess: (res) => {
      message.success(`Generated ${res.generated} slip, ${res.skipped} skipped`);
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
      queryClient.invalidateQueries({ queryKey: ['payroll-slips'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal generate'),
  });

  const lockMut = useMutation({
    mutationFn: (id: string) => lockPeriod(id),
    onSuccess: () => {
      message.success('Periode locked');
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
    },
  });

  const columns: ColumnsType<PayrollPeriod> = [
    {
      title: 'Periode', key: 'periode', width: 160,
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text strong>{periodLabel(r)}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>
            Pay date: {dayjs(r.pay_date).format('DD MMM YY')}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Status', dataIndex: 'status', key: 'status', width: 110,
      render: (s: any) => {
        const conf = periodStatusColor(s);
        return <Tag className={conf.className}>{conf.label}</Tag>;
      },
    },
    {
      title: 'Slips', dataIndex: 'slip_count', key: 'slips', align: 'center', width: 80,
    },
    {
      title: 'Total Gross', dataIndex: 'total_gross', key: 'gross', align: 'right',
      render: (v: string | null) => v ? fmtIDR(v) : '—',
    },
    {
      title: 'Total Take Home', dataIndex: 'total_take_home', key: 'th', align: 'right',
      render: (v: string | null) => (
        v ? <Text strong style={{ color: 'var(--ide-green, #34C759)' }}>{fmtIDR(v)}</Text> : '—'
      ),
    },
    {
      title: 'Actions', key: 'act', width: 240,
      render: (_, r) => (
        <Space size={4}>
          {r.status !== 'LOCKED' && r.slip_count === 0 && (
            <Tooltip title="Generate slips untuk semua active employees">
              <Button
                size="small" type="primary" icon={<ThunderboltOutlined />}
                loading={generateMut.isPending}
                onClick={() => generateMut.mutate(r.id)}
              >
                Generate Slips
              </Button>
            </Tooltip>
          )}
          {r.status !== 'LOCKED' && (
            <Popconfirm
              title="Lock periode ini? Setelah locked, slip tidak bisa diubah."
              onConfirm={() => lockMut.mutate(r.id)}
            >
              <Button size="small" icon={<LockOutlined />}>Lock</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Payroll periode bulanan. Buat periode → generate slips → review → lock.
        </Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setOpen(true)}>
          New Period
        </Button>
      </div>

      {query.isLoading ? <Spin /> :
        (query.data ?? []).length === 0 ? <Empty description="Belum ada periode" /> :
          <Table rowKey="id" columns={columns} dataSource={query.data ?? []} size="small" />}

      <Modal title="New Payroll Period" open={open}
        onCancel={() => setOpen(false)} footer={null} destroyOnHidden>
        <Form
          form={form} layout="vertical"
          initialValues={{ year: dayjs().year(), month: dayjs().month() + 1 }}
          onFinish={(v) => createMut.mutate(v)}
        >
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Year" name="year" rules={[{ required: true }]}>
              <InputNumber min={2020} max={2099} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Month" name="month" rules={[{ required: true }]}>
              <Select options={MONTHS_ID.map((m, i) => ({ value: i + 1, label: m }))} />
            </Form.Item>
          </div>
          <Form.Item label="Pay Date" name="pay_date" rules={[{ required: true }]}>
            <Input placeholder="YYYY-MM-DD" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Create
          </Button>
        </Form>
      </Modal>
    </div>
  );
}

// ─── Slips Tab ────────────────────────────────────────────────────

function SlipsTab() {
  const queryClient = useQueryClient();
  const [periodFilter, setPeriodFilter] = useState<string | undefined>();
  const [activeSlipId, setActiveSlipId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const periodsQ = useQuery({ queryKey: ['payroll-periods'], queryFn: listPeriods });
  const slipsQ = useQuery({
    queryKey: ['payroll-slips', periodFilter],
    queryFn: () => listSlips({ period_id: periodFilter }),
  });

  const columns: ColumnsType<PayrollSlip> = [
    {
      title: 'Slip No', dataIndex: 'slip_no', key: 'no', width: 140,
      render: (v: string) => (
        <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontWeight: 700, color: 'var(--ide-blue, #0071E3)' }}>
          {v}
        </Text>
      ),
    },
    {
      title: 'Employee', key: 'emp',
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text>{r.employee_name}</Text>
          <Text type="secondary" style={{ fontSize: 11 }}>{r.employee_nik}</Text>
        </Space>
      ),
    },
    { title: 'Periode', dataIndex: 'period_label', key: 'period', width: 120 },
    {
      title: 'Gross', dataIndex: 'gross_income', key: 'gross', align: 'right',
      render: (v: string) => fmtIDR(v),
    },
    {
      title: 'Deductions', dataIndex: 'total_deductions', key: 'ded', align: 'right',
      render: (v: string) => <Text style={{ color: 'var(--ide-red, #FF3B30)' }}>{fmtIDR(v)}</Text>,
    },
    {
      title: 'Take Home', dataIndex: 'take_home_pay', key: 'th', align: 'right',
      render: (v: string) => <Text strong style={{ color: 'var(--ide-green, #34C759)' }}>{fmtIDR(v)}</Text>,
    },
    {
      title: 'Action', key: 'act', width: 80, align: 'center',
      render: (_, r) => (
        <Button size="small" onClick={() => { setActiveSlipId(r.id); setDrawerOpen(true); }}>
          Detail
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: 12 }}>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>Filter periode:</Text>
          <Select
            allowClear placeholder="Semua periode" style={{ width: 200 }}
            value={periodFilter} onChange={setPeriodFilter}
            options={(periodsQ.data ?? []).map((p) => ({
              value: p.id, label: periodLabel(p),
            }))}
          />
        </Space>
      </div>

      {slipsQ.isLoading ? <Spin /> :
        (slipsQ.data ?? []).length === 0 ? <Empty description="Belum ada slip" /> :
          <Table rowKey="id" columns={columns} dataSource={slipsQ.data ?? []}
            size="small" pagination={{ pageSize: 20 }} />}

      <SlipDetailDrawer
        slipId={activeSlipId} open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setActiveSlipId(null); }}
        onChange={() => queryClient.invalidateQueries({ queryKey: ['payroll-slips'] })}
      />
    </div>
  );
}

function SlipDetailDrawer({
  slipId, open, onClose, onChange,
}: {
  slipId: string | null;
  open: boolean;
  onClose: () => void;
  onChange: () => void;
}) {
  const queryClient = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [pphOpen, setPphOpen] = useState(false);
  const [form] = Form.useForm();
  const [pphForm] = Form.useForm();

  const slipQ = useQuery({
    queryKey: ['payroll-slip', slipId],
    queryFn: () => getSlip(slipId!),
    enabled: !!slipId && open,
  });

  const addMut = useMutation({
    mutationFn: (data: any) => addComponent(slipId!, data),
    onSuccess: () => {
      message.success('Komponen ditambah');
      queryClient.invalidateQueries({ queryKey: ['payroll-slip', slipId] });
      onChange();
      setAddOpen(false);
      form.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal add komponen'),
  });

  const deleteMut = useMutation({
    mutationFn: (cid: string) => deleteComponent(cid),
    onSuccess: () => {
      message.success('Komponen dihapus');
      queryClient.invalidateQueries({ queryKey: ['payroll-slip', slipId] });
      onChange();
    },
  });

  const pphMut = useMutation({
    mutationFn: (amt: number) => setPph21(slipId!, amt),
    onSuccess: () => {
      message.success('PPh21 disimpan');
      queryClient.invalidateQueries({ queryKey: ['payroll-slip', slipId] });
      onChange();
      setPphOpen(false);
      pphForm.resetFields();
    },
  });

  const pdfMut = useMutation({
    mutationFn: () => generateSlipPdf(slipId!),
    onSuccess: () => {
      message.success('PDF di-generate');
      queryClient.invalidateQueries({ queryKey: ['payroll-slip', slipId] });
      onChange();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal generate PDF'),
  });

  const handleDownloadPdf = async () => {
    if (!slipId) return;
    try {
      const { url } = await getSlipPdfUrl(slipId);
      window.open(url, '_blank');
    } catch (e: any) {
      message.error(e?.response?.data?.detail?.message ?? 'Gagal generate URL');
    }
  };

  const s = slipQ.data;

  return (
    <Drawer
      title={s ? `${s.slip_no} — ${s.employee_name}` : 'Slip Detail'}
      open={open} onClose={onClose} width={620}
      extra={
        s && (
          <Space>
            {s.pdf_url ? (
              <Button icon={<CloudDownloadOutlined />} onClick={handleDownloadPdf}>
                Download PDF
              </Button>
            ) : (
              <Button
                icon={<FilePdfOutlined />}
                loading={pdfMut.isPending}
                onClick={() => pdfMut.mutate()}
              >
                Generate PDF
              </Button>
            )}
            <Button icon={<DollarOutlined />} onClick={() => setPphOpen(true)}>
              Set PPh21
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
              Add Component
            </Button>
          </Space>
        )
      }
    >
      {slipQ.isLoading ? <Spin /> : s && (
        <>
          <div style={{ background: 'rgba(0,113,227,0.05)', padding: 12, borderRadius: 8, marginBottom: 14 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Periode</Text>
                <div><Text strong>{s.period_label}</Text></div>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>NIK</Text>
                <div><Text>{s.employee_nik}</Text></div>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Gross Income</Text>
                <div><Text strong>{fmtIDR(s.gross_income)}</Text></div>
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 11 }}>Total Deductions</Text>
                <div><Text style={{ color: 'var(--ide-red, #FF3B30)' }}>{fmtIDR(s.total_deductions)}</Text></div>
              </div>
              <div style={{ gridColumn: 'span 2', borderTop: '1px solid rgba(0,0,0,0.1)', paddingTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>Take Home Pay</Text>
                <div>
                  <Title level={4} style={{ margin: 0, color: 'var(--ide-green, #34C759)' }}>
                    {fmtIDR(s.take_home_pay)}
                  </Title>
                </div>
              </div>
            </div>
          </div>

          <Title level={5}>Components</Title>
          {s.components.length === 0 ? (
            <Empty description="Belum ada komponen" />
          ) : (
            <Table
              rowKey="id" size="small" pagination={false}
              dataSource={s.components}
              columns={[
                { title: 'Code', dataIndex: 'code', width: 100,
                  render: (v: string) => <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 11 }}>{v}</Text> },
                { title: 'Name', dataIndex: 'name' },
                { title: 'Type', dataIndex: 'component_type', width: 110,
                  render: (v: ComponentType) => (
                    <Tag color={v === 'INCOME' ? 'green' : 'red'}>{v}</Tag>
                  ) },
                { title: 'Amount', dataIndex: 'amount', align: 'right',
                  render: (v: string) => fmtIDR(v) },
                { title: '', key: 'del', width: 50,
                  render: (_, r) => r.is_variable && (
                    <Popconfirm title="Hapus?" onConfirm={() => deleteMut.mutate(r.id)}>
                      <Button type="text" size="small" danger>×</Button>
                    </Popconfirm>
                  ) },
              ]}
            />
          )}

          <Modal title="Add Component" open={addOpen}
            onCancel={() => setAddOpen(false)} footer={null} destroyOnHidden>
            <Form form={form} layout="vertical"
              initialValues={{ component_type: 'INCOME', is_variable: true }}
              onFinish={(v) => addMut.mutate(v)}
            >
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 10 }}>
                <Form.Item label="Code" name="code" rules={[{ required: true }]}>
                  <Input placeholder="BONUS_AKHIR_TAHUN" />
                </Form.Item>
                <Form.Item label="Name" name="name" rules={[{ required: true }]}>
                  <Input placeholder="Bonus Akhir Tahun" />
                </Form.Item>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                <Form.Item label="Type" name="component_type">
                  <Select options={[
                    { value: 'INCOME', label: 'INCOME (penghasilan)' },
                    { value: 'DEDUCTION', label: 'DEDUCTION (potongan)' },
                  ]} />
                </Form.Item>
                <Form.Item label="Amount" name="amount" rules={[{ required: true }]}>
                  <InputNumber
                    min={0} style={{ width: '100%' }}
                    formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                    parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
                  />
                </Form.Item>
              </div>
              <Button type="primary" htmlType="submit" loading={addMut.isPending} block>
                Add
              </Button>
            </Form>
          </Modal>

          <Modal title="Set PPh21" open={pphOpen}
            onCancel={() => setPphOpen(false)} footer={null} destroyOnHidden>
            <Form form={pphForm} layout="vertical"
              onFinish={(v) => pphMut.mutate(v.amount)}
            >
              <Form.Item label="PPh21 Amount" name="amount" rules={[{ required: true }]}>
                <InputNumber
                  min={0} style={{ width: '100%' }}
                  formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                  parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
                />
              </Form.Item>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 10 }}>
                PPh21 di-input manual per slip (US-TK-049). Akan masuk sebagai DEDUCTION dengan code PPH21.
              </Text>
              <Button type="primary" htmlType="submit" loading={pphMut.isPending} block>
                Save PPh21
              </Button>
            </Form>
          </Modal>
        </>
      )}
    </Drawer>
  );
}

// ─── Main Page ────────────────────────────────────────────────────

export default function PayrollPage() {
  return (
    <div style={{ padding: '20px 24px', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <Title level={3} style={{ margin: 0 }}>Payroll</Title>
        <Text type="secondary" style={{ fontSize: 13 }}>
          Payroll config + periode bulanan + slip generation. Reimbursement di Finance (transfer terpisah).
        </Text>
      </div>

      <Tabs
        defaultActiveKey="periods"
        items={[
          { key: 'periods', label: <span><CalendarOutlined /> Periods</span>, children: <PeriodsTab /> },
          { key: 'attendance', label: <span><CheckSquareOutlined /> Attendance</span>, children: <AttendanceTab /> },
          { key: 'slips', label: <span><DollarOutlined /> Slips</span>, children: <SlipsTab /> },
          { key: 'configs', label: <span><SettingOutlined /> Configs</span>, children: <ConfigsTab /> },
        ]}
      />
    </div>
  );
}
