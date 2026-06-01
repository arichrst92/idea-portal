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
  CheckOutlined,
  CheckSquareOutlined,
  CloseOutlined,
  CloudDownloadOutlined,
  DollarOutlined,
  FilePdfOutlined,
  LockOutlined,
  PlusOutlined,
  SendOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';

import { AttendanceTab } from './AttendanceTab';
import { ThrTab } from './ThrTab';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Drawer, Empty, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Spin, Table, Tabs, Tag, Tooltip, Typography} from 'antd';
import { message } from '@/lib/notify';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  addComponent,
  approvePayroll,
  calculatePayroll,
  calculatePayrollPreview,
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
  rejectPayroll,
  submitPayrollForApproval,
  suggestPph21,
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
  const [calcPreviewPeriodId, setCalcPreviewPeriodId] = useState<string | null>(null);
  const [rejectPeriodId, setRejectPeriodId] = useState<string | null>(null);
  const [rejectForm] = Form.useForm();

  const query = useQuery({ queryKey: ['payroll-periods'], queryFn: listPeriods });

  const createMut = useMutation({
    // Convert empty string → null for optional date fields (TSK-055)
    mutationFn: (v: any) =>
      createPeriod({
        year: v.year,
        month: v.month,
        pay_date: v.pay_date,
        cutoff_date: v.cutoff_date ? v.cutoff_date : null,
        publish_date: v.publish_date ? v.publish_date : null,
      }),
    onSuccess: () => {
      message.success('Periode dibuat');
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
      setOpen(false);
      form.resetFields();
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail;
      // NC-OP-008-02 — duplicate periode explicit
      if (detail?.code === 'DUPLICATE_PERIOD') {
        message.error(detail.message);
      } else {
        message.error(detail?.message ?? 'Gagal create periode');
      }
    },
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

  // TSK-048 Calc engine mutations
  const calcMut = useMutation({
    mutationFn: (id: string) => calculatePayroll(id),
    onSuccess: (res) => {
      message.success(
        `Payroll calculated: ${res.generated} slip · Total Take Home: ${fmtIDR(res.total_take_home_idr)}`
      );
      if (res.anomaly_warnings.length > 0) {
        message.warning(res.anomaly_warnings[0]);
      }
      setCalcPreviewPeriodId(null);
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
      queryClient.invalidateQueries({ queryKey: ['payroll-slips'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal calculate'),
  });

  // TSK-050 Approval workflow mutations
  const submitApprovalMut = useMutation({
    mutationFn: (id: string) => submitPayrollForApproval(id),
    onSuccess: () => {
      message.success('Payroll submitted untuk approval GM/C-Level');
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal submit'),
  });

  const approveMut = useMutation({
    mutationFn: (id: string) => approvePayroll(id),
    onSuccess: () => {
      message.success('Payroll approved ✓');
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail;
      if (d?.code === 'SELF_APPROVAL') {
        message.error(d.message);
      } else {
        message.error(d?.message ?? 'Gagal approve');
      }
    },
  });

  const rejectMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      rejectPayroll(id, reason),
    onSuccess: () => {
      message.success('Payroll rejected — kembali ke Finance untuk fix');
      setRejectPeriodId(null);
      rejectForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['payroll-periods'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal reject'),
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
          {r.status === 'DRAFT' && r.slip_count === 0 && (
            <Tooltip title="TSK-048 — Calc engine: attendance × config → slips dengan prorata & overtime">
              <Button
                size="small" type="primary" icon={<ThunderboltOutlined />}
                onClick={() => setCalcPreviewPeriodId(r.id)}
              >
                Calculate
              </Button>
            </Tooltip>
          )}
          {r.status === 'REVIEWING' && r.slip_count > 0 && (
            <Tooltip title="Submit ke GM/C-Level untuk approval (US-FN-002 AC-06)">
              <Button
                size="small" type="primary" icon={<SendOutlined />}
                loading={submitApprovalMut.isPending}
                onClick={() => submitApprovalMut.mutate(r.id)}
              >
                Submit Approval
              </Button>
            </Tooltip>
          )}
          {r.status === 'PENDING_APPROVAL' && (
            <>
              <Tooltip title="Approve payroll (GM/C-Level). Self-approval di-block.">
                <Popconfirm
                  title="Approve payroll ini?"
                  description="Setelah approved, slip siap dipublish ke karyawan."
                  onConfirm={() => approveMut.mutate(r.id)}
                >
                  <Button
                    size="small" type="primary" icon={<CheckOutlined />}
                    loading={approveMut.isPending}
                  >
                    Approve
                  </Button>
                </Popconfirm>
              </Tooltip>
              <Tooltip title="Reject — kembali ke Finance untuk fix">
                <Button
                  size="small" danger icon={<CloseOutlined />}
                  onClick={() => setRejectPeriodId(r.id)}
                >
                  Reject
                </Button>
              </Tooltip>
            </>
          )}
          {r.status !== 'LOCKED' && r.status !== 'DRAFT' && r.status !== 'PENDING_APPROVAL' && r.slip_count === 0 && (
            <Tooltip title="Legacy — generate slips tanpa attendance prorata">
              <Button
                size="small" icon={<ThunderboltOutlined />}
                loading={generateMut.isPending}
                onClick={() => generateMut.mutate(r.id)}
              >
                Generate Slips
              </Button>
            </Tooltip>
          )}
          {(r.status === 'APPROVED' || r.status === 'PAID') && (
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
          <Form.Item
            label="Pay Date"
            name="pay_date"
            rules={[{ required: true, message: 'Tanggal pembayaran wajib' }]}
            tooltip="Tanggal transfer gaji ke karyawan"
          >
            <Input placeholder="YYYY-MM-DD" />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item
              label="Cut-off Date"
              name="cutoff_date"
              tooltip="Tanggal attendance & komponen variable harus sudah di-input (opsional, default: pay_date - 5 hari)"
            >
              <Input placeholder="YYYY-MM-DD (opsional)" />
            </Form.Item>
            <Form.Item
              label="Publish Date"
              name="publish_date"
              tooltip="Tanggal slip PDF di-publish ke portal karyawan (opsional, default: pay_date)"
            >
              <Input placeholder="YYYY-MM-DD (opsional)" />
            </Form.Item>
          </div>
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 12 }}>
            Per knowledge.md sec.12: "Tanggal gajian dikonfigurasi per periode".
            Config bisa di-edit selama period masih DRAFT.
          </Text>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Create
          </Button>
        </Form>
      </Modal>

      {/* TSK-048 Calc Preview Modal */}
      <CalcPreviewModal
        periodId={calcPreviewPeriodId}
        onClose={() => setCalcPreviewPeriodId(null)}
        onConfirm={(id) => calcMut.mutate(id)}
        confirmLoading={calcMut.isPending}
      />

      {/* TSK-050 Reject Modal */}
      <Modal
        title="Reject Payroll"
        open={!!rejectPeriodId}
        onCancel={() => setRejectPeriodId(null)}
        footer={null}
        destroyOnHidden
      >
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
          Payroll akan kembali ke status REVIEWING untuk Finance fix sebelum
          submit ulang. Notifikasi akan dikirim ke submitter.
        </Text>
        <Form
          form={rejectForm}
          layout="vertical"
          onFinish={(v) =>
            rejectMut.mutate({ id: rejectPeriodId!, reason: v.rejection_reason })
          }
        >
          <Form.Item
            label="Alasan Reject"
            name="rejection_reason"
            rules={[
              { required: true, message: 'Alasan wajib diisi' },
              { min: 3, message: 'Minimal 3 karakter' },
            ]}
          >
            <Input.TextArea
              rows={4}
              placeholder="Contoh: Komisi sales bulan ini perlu di-review, ada anomaly di slip Budi..."
            />
          </Form.Item>
          <Space>
            <Button onClick={() => setRejectPeriodId(null)}>Batal</Button>
            <Button
              type="primary"
              danger
              htmlType="submit"
              loading={rejectMut.isPending}
              icon={<CloseOutlined />}
            >
              Confirm Reject
            </Button>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}

// ─── TSK-048: Calc Preview Modal ───────────────────────────────────

function CalcPreviewModal({
  periodId,
  onClose,
  onConfirm,
  confirmLoading,
}: {
  periodId: string | null;
  onClose: () => void;
  onConfirm: (id: string) => void;
  confirmLoading: boolean;
}) {
  const previewQ = useQuery({
    queryKey: ['payroll-calc-preview', periodId],
    queryFn: () => calculatePayrollPreview(periodId!),
    enabled: !!periodId,
    retry: false,
  });

  const preview = previewQ.data;

  return (
    <Modal
      title={<><ThunderboltOutlined /> Calculate Payroll — Pre-flight Check</>}
      open={!!periodId}
      onCancel={onClose}
      width={620}
      destroyOnHidden
      footer={[
        <Button key="c" onClick={onClose}>Batal</Button>,
        <Button
          key="ok"
          type="primary"
          loading={confirmLoading}
          disabled={!preview?.can_proceed}
          icon={<ThunderboltOutlined />}
          onClick={() => periodId && onConfirm(periodId)}
        >
          Run Calc
        </Button>,
      ]}
    >
      {previewQ.isLoading && (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <Spin>
            <div style={{ minHeight: 24 }} />
          </Spin>
        </div>
      )}

      {preview && (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          <div style={{
            padding: 14, background: 'var(--ide-bg, #F5F5F7)', borderRadius: 8,
            display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16,
          }}>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Hari Kerja</Text>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ide-blue)' }}>
                {preview.calendar_working_days} <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>hari</Text>
              </div>
            </div>
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>Estimasi Slip</Text>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ide-green, #34C759)' }}>
                {preview.estimated_employee_count - preview.attendance_missing_count} <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>karyawan</Text>
              </div>
            </div>
          </div>

          {preview.attendance_missing_count > 0 && (
            <div style={{
              padding: 12, borderRadius: 8,
              background: 'rgba(255,149,0,0.08)',
              border: '1px solid rgba(255,149,0,0.3)',
            }}>
              <Text strong style={{ color: 'var(--ide-orange, #FF9500)' }}>
                ⚠ {preview.attendance_missing_count} karyawan belum input attendance
              </Text>
              <div style={{ fontSize: 12, marginTop: 4, color: 'var(--ide-ink2)' }}>
                Lengkapi di tab Attendance dulu (NC-OP-008-01).
              </div>
            </div>
          )}

          {preview.blockers.length > 0 && (
            <div style={{
              padding: 12, borderRadius: 8,
              background: 'rgba(255,59,48,0.08)',
              border: '1px solid rgba(255,59,48,0.3)',
            }}>
              <Text strong style={{ color: 'var(--ide-red, #FF3B30)' }}>
                Calc tidak bisa dijalankan:
              </Text>
              <ul style={{ margin: '8px 0 0 20px', fontSize: 13 }}>
                {preview.blockers.map((b, i) => <li key={i}>{b}</li>)}
              </ul>
            </div>
          )}

          {preview.can_proceed && (
            <div style={{
              padding: 12, borderRadius: 8,
              background: 'rgba(52,199,89,0.08)',
              border: '1px solid rgba(52,199,89,0.3)',
            }}>
              <Text strong style={{ color: 'var(--ide-green, #34C759)' }}>
                ✓ Siap calculate
              </Text>
              <div style={{ fontSize: 12, marginTop: 4, color: 'var(--ide-ink2)' }}>
                Akan generate {preview.estimated_employee_count} slip dengan prorata basic salary,
                overtime (1.5× hourly rate), BPJS Kesehatan 1%, BPJS Ketenagakerjaan 2%.
                Komisi sales pending auto-inject. Status period → REVIEWING setelah selesai.
              </div>
            </div>
          )}

          <Text type="secondary" style={{ fontSize: 11 }}>
            Spec: US-OP-008 + US-FN-002 · Edge cases: NC-OP-008-01/02, NC-FN-002-02/05.
          </Text>
        </Space>
      )}
    </Modal>
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
    onError: (e: any) => {
      const detail = e?.response?.data?.detail;
      if (detail?.code === 'NET_NEGATIVE') {
        message.error(detail.message);  // NC-FN-002-02 explicit
      } else {
        message.error(detail?.message ?? 'Gagal set PPh21');
      }
    },
  });

  // TSK-049 — auto-suggest PPh21 saat modal buka
  const pphSuggestQ = useQuery({
    queryKey: ['pph21-suggest', slipId],
    queryFn: () => suggestPph21(slipId!),
    enabled: !!slipId && pphOpen,
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

          <Modal title="Set PPh21 Manual" open={pphOpen}
            onCancel={() => setPphOpen(false)} footer={null} destroyOnHidden>
            <Form form={pphForm} layout="vertical"
              onFinish={(v) => pphMut.mutate(v.amount)}
            >
              {pphSuggestQ.data && (
                <div style={{
                  background: 'rgba(0,113,227,0.06)',
                  border: '1px solid rgba(0,113,227,0.2)',
                  borderRadius: 8, padding: 12, marginBottom: 12,
                }}>
                  <Text strong style={{ fontSize: 12, color: 'var(--ide-blue, #0071E3)' }}>
                    💡 Suggested: {fmtIDR(pphSuggestQ.data.suggested_pph21)}
                  </Text>
                  <div style={{ fontSize: 11, color: 'var(--ide-ink2)', marginTop: 4 }}>
                    Annual gross {fmtIDR(pphSuggestQ.data.annual_gross)} × bracket progresif (PTKP TK/0 = Rp 54jt), dibagi 12.
                    Final keputusan Finance.
                  </div>
                  <Button
                    size="small" type="link" style={{ padding: 0, marginTop: 4 }}
                    onClick={() => pphForm.setFieldValue('amount', Number(pphSuggestQ.data!.suggested_pph21))}
                  >
                    Gunakan suggestion
                  </Button>
                </div>
              )}
              <Form.Item label="PPh21 Amount" name="amount" rules={[{ required: true }]}>
                <InputNumber
                  min={0} style={{ width: '100%' }}
                  formatter={(v) => (v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
                  parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0) as any}
                />
              </Form.Item>
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 10 }}>
                PPh21 di-input manual per slip (US-FN-002 AC-03). Akan masuk sebagai DEDUCTION code PPH21.
                Sistem akan reject kalau net pay jadi negative (NC-FN-002-02).
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
          { key: 'thr', label: <span><PlusOutlined /> THR</span>, children: <ThrTab /> },
          { key: 'configs', label: <span><SettingOutlined /> Configs</span>, children: <ConfigsTab /> },
        ]}
      />
    </div>
  );
}
