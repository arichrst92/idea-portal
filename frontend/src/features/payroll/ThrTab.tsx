/**
 * ThrTab — TSK-053 (US-FN-003).
 *
 * Bulk generate THR per tahun, list rows dengan paid status, mark paid action.
 *
 * Spec:
 * - US-FN-003 AC-02: prorata < 1 tahun masa kerja
 * - US-FN-003 AC-03: separate from monthly payroll
 * - US-FN-003 AC-05: separate ledger entry (will be wired di TSK-FN integration)
 * - knowledge.md sec.12: THR transfer terpisah, configurable
 */

import {
  CheckCircleOutlined,
  GiftOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  DatePicker,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  generateThr,
  listThr,
  markThrPaid,
  type Thr,
  type ThrStatus,
} from '@/api/payroll';
import { message } from '@/lib/notify';

const { Text } = Typography;

const fmtIDR = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (!Number.isFinite(n)) return '—';
  return `Rp ${n.toLocaleString('id-ID')}`;
};

const STATUS_COLOR: Record<ThrStatus, { label: string; color: string }> = {
  GENERATED: { label: 'Generated', color: 'orange' },
  APPROVED: { label: 'Approved', color: 'blue' },
  PAID: { label: 'Paid', color: 'green' },
  CANCELLED: { label: 'Cancelled', color: 'red' },
};

export function ThrTab() {
  const queryClient = useQueryClient();
  const currentYear = dayjs().year();
  const [yearFilter, setYearFilter] = useState<number>(currentYear);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [generateForm] = Form.useForm();
  const [markPaidRowId, setMarkPaidRowId] = useState<string | null>(null);
  const [markPaidForm] = Form.useForm();

  const query = useQuery({
    queryKey: ['thr-list', yearFilter],
    queryFn: () => listThr({ thr_year: yearFilter }),
  });

  const generateMut = useMutation({
    mutationFn: (v: any) =>
      generateThr(v.thr_year, v.reference_date, v.overwrite_existing),
    onSuccess: (res) => {
      message.success(
        `THR ${res.thr_year}: generated ${res.generated}, skipped ${res.skipped} · Total ${fmtIDR(res.total_amount_idr)}`
      );
      if (res.errors.length > 0) {
        message.warning(`${res.errors.length} employees skipped — cek detail`);
      }
      setGenerateOpen(false);
      generateForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['thr-list'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal generate THR'),
  });

  const markPaidMut = useMutation({
    mutationFn: (v: any) =>
      markThrPaid(markPaidRowId!, v.payment_date, v.transfer_ref),
    onSuccess: () => {
      message.success('THR ditandai PAID');
      setMarkPaidRowId(null);
      markPaidForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['thr-list'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal mark paid'),
  });

  const columns: ColumnsType<Thr> = [
    {
      title: 'Karyawan',
      key: 'employee',
      width: 220,
      render: (_, t) => (
        <Space direction="vertical" size={0}>
          <Text strong>{t.employee_name ?? '—'}</Text>
          <Text type="secondary" style={{ fontSize: 11, fontFamily: 'monospace' }}>
            {t.employee_nik ?? '—'}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Base Salary',
      dataIndex: 'base_salary',
      align: 'right',
      render: (v) => <Text style={{ fontFamily: 'monospace' }}>{fmtIDR(v)}</Text>,
    },
    {
      title: 'Bulan Kerja',
      dataIndex: 'months_worked',
      align: 'center',
      width: 110,
      render: (v: string) => {
        const n = parseFloat(v);
        const isProrata = n < 12;
        return (
          <Tag color={isProrata ? 'orange' : 'blue'}>
            {n.toFixed(2)} {isProrata && '(prorata)'}
          </Tag>
        );
      },
    },
    {
      title: 'THR Amount',
      dataIndex: 'thr_amount',
      align: 'right',
      render: (v) => (
        <Text strong style={{ fontFamily: 'monospace', color: 'var(--ide-green, #34C759)' }}>
          {fmtIDR(v)}
        </Text>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      width: 110,
      align: 'center',
      render: (s: ThrStatus) => {
        const conf = STATUS_COLOR[s];
        return <Tag color={conf.color}>{conf.label}</Tag>;
      },
    },
    {
      title: 'Payment',
      key: 'payment',
      width: 180,
      render: (_, t) =>
        t.status === 'PAID' && t.payment_date ? (
          <Space direction="vertical" size={0}>
            <Text style={{ fontSize: 12 }}>
              {dayjs(t.payment_date).format('DD MMM YYYY')}
            </Text>
            {t.transfer_ref && (
              <Text type="secondary" style={{ fontSize: 11, fontFamily: 'monospace' }}>
                Ref: {t.transfer_ref}
              </Text>
            )}
          </Space>
        ) : (
          <Text type="secondary" style={{ fontSize: 11 }}>—</Text>
        ),
    },
    {
      title: 'Actions',
      key: 'act',
      width: 140,
      render: (_, t) =>
        t.status === 'GENERATED' || t.status === 'APPROVED' ? (
          <Button
            size="small"
            type="primary"
            icon={<CheckCircleOutlined />}
            onClick={() => setMarkPaidRowId(t.id)}
          >
            Mark Paid
          </Button>
        ) : null,
    },
  ];

  const totalForYear = (query.data ?? []).reduce(
    (sum, t) => sum + parseFloat(t.thr_amount),
    0
  );
  const paidCount = (query.data ?? []).filter((t) => t.status === 'PAID').length;
  const totalCount = (query.data ?? []).length;

  return (
    <div style={{ padding: 16 }}>
      <Alert
        message={`THR per US-FN-003: prorata untuk masa kerja < 12 bulan. Transfer terpisah dari payroll bulanan.`}
        type="info"
        icon={<GiftOutlined />}
        showIcon
        style={{ marginBottom: 16 }}
      />

      <div
        style={{
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          marginBottom: 16,
          padding: 16,
          background: 'var(--ide-bg, #F5F5F7)',
          borderRadius: 8,
        }}
      >
        <Space direction="vertical" size={2}>
          <Text type="secondary" style={{ fontSize: 11 }}>Tahun THR</Text>
          <Select
            value={yearFilter}
            onChange={setYearFilter}
            style={{ width: 140 }}
            options={Array.from({ length: 5 }, (_, i) => currentYear - 2 + i).map((y) => ({
              value: y,
              label: y,
            }))}
          />
        </Space>

        <div style={{ flex: 1 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>Total THR {yearFilter}</Text>
          <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ide-blue, #0071E3)' }}>
            {fmtIDR(totalForYear)}
          </div>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {paidCount}/{totalCount} sudah PAID
          </Text>
        </div>

        <Button
          type="primary"
          icon={<ThunderboltOutlined />}
          onClick={() => {
            generateForm.setFieldsValue({
              thr_year: currentYear,
              reference_date: dayjs(),
              overwrite_existing: false,
            });
            setGenerateOpen(true);
          }}
        >
          Generate THR
        </Button>
      </div>

      {query.isLoading ? (
        <div style={{ padding: 40, textAlign: 'center' }}>
          <Spin>
            <div style={{ minHeight: 24 }} />
          </Spin>
        </div>
      ) : query.data && query.data.length > 0 ? (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={query.data}
          size="small"
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      ) : (
        <Empty
          description={
            <span>
              Belum ada THR untuk tahun {yearFilter}.
              <br />
              <Text type="secondary" style={{ fontSize: 11 }}>
                Klik "Generate THR" untuk membuat THR semua karyawan eligible.
              </Text>
            </span>
          }
        />
      )}

      {/* Generate Modal */}
      <Modal
        title={<><GiftOutlined /> Generate THR Bulk</>}
        open={generateOpen}
        onCancel={() => setGenerateOpen(false)}
        footer={null}
        destroyOnHidden
      >
        <Form
          form={generateForm}
          layout="vertical"
          onFinish={(v) =>
            generateMut.mutate({
              thr_year: v.thr_year,
              reference_date: v.reference_date.format('YYYY-MM-DD'),
              overwrite_existing: v.overwrite_existing ?? false,
            })
          }
        >
          <Form.Item label="Tahun THR" name="thr_year" rules={[{ required: true }]}>
            <InputNumber min={2020} max={2099} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            label="Reference Date (untuk hitung masa kerja)"
            name="reference_date"
            rules={[{ required: true }]}
            tooltip="Biasanya H-7 Lebaran. Bulan kerja dihitung sampai tanggal ini."
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item
            label="Overwrite Existing"
            name="overwrite_existing"
            tooltip="Centang kalau mau replace THR yang sudah ada (kecuali yang sudah PAID)"
          >
            <Select
              options={[
                { value: false, label: 'Tidak — skip existing' },
                { value: true, label: 'Ya — replace (kecuali PAID)' },
              ]}
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            loading={generateMut.isPending}
            icon={<ThunderboltOutlined />}
          >
            Generate
          </Button>
        </Form>
      </Modal>

      {/* Mark Paid Modal */}
      <Modal
        title={<><CheckCircleOutlined /> Mark THR as Paid</>}
        open={!!markPaidRowId}
        onCancel={() => setMarkPaidRowId(null)}
        footer={null}
        destroyOnHidden
      >
        <Form
          form={markPaidForm}
          layout="vertical"
          initialValues={{ payment_date: dayjs() }}
          onFinish={(v) =>
            markPaidMut.mutate({
              payment_date: v.payment_date.format('YYYY-MM-DD'),
              transfer_ref: v.transfer_ref || null,
            })
          }
        >
          <Form.Item label="Payment Date" name="payment_date" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item
            label="Transfer Reference"
            name="transfer_ref"
            tooltip="No referensi transfer bank (opsional)"
          >
            <Input placeholder="ex: TRF202604120015" />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            loading={markPaidMut.isPending}
            icon={<CheckCircleOutlined />}
          >
            Confirm Paid
          </Button>
        </Form>
      </Modal>
    </div>
  );
}
