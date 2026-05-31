/**
 * MyPayslipsPage — TSK-052.
 *
 * Self-service slip history per US-FN-002 AC-10:
 * "Pay slip history is accessible to each employee from their first month
 *  of employment".
 *
 * Hanya tampilkan slip dari period yang sudah APPROVED/PAID/LOCKED.
 * RBAC: backend auto-filter ke current user via /me/payslips endpoint.
 */

import {
  DollarOutlined,
  FilePdfOutlined,
  LockOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button, Empty, Spin, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import {
  generateSlipPdf,
  getSlipPdfUrl,
  listMyPayslips,
  type PayrollSlip,
} from '@/api/payroll';
import { message } from '@/lib/notify';

const { Title, Text } = Typography;

const fmtIDR = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (!Number.isFinite(n)) return '—';
  return `Rp ${n.toLocaleString('id-ID')}`;
};

const MONTHS_ID = [
  'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
];

export default function MyPayslipsPage() {
  const query = useQuery({
    queryKey: ['my-payslips'],
    queryFn: listMyPayslips,
  });

  const pdfDownloadMut = useMutation({
    mutationFn: async (slipId: string) => {
      // If PDF tidak ada, generate dulu
      const slip = query.data?.find((s) => s.id === slipId);
      if (!slip?.pdf_url) {
        await generateSlipPdf(slipId);
      }
      return getSlipPdfUrl(slipId);
    },
    onSuccess: (data) => {
      if (data.url) {
        window.open(data.url, '_blank');
      } else {
        message.error('PDF tidak tersedia');
      }
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal download PDF'),
  });

  const columns: ColumnsType<PayrollSlip> = [
    {
      title: 'Periode',
      key: 'period',
      width: 180,
      render: (_, s) => {
        // PayrollSlip doesn't include year/month directly; derive from slip_no
        // Format: SLIP-YYYYMM-NIK
        const periodPart = s.slip_no.split('-')[1] ?? '';
        const year = periodPart.slice(0, 4);
        const monthNum = parseInt(periodPart.slice(4, 6), 10);
        const monthLabel = MONTHS_ID[monthNum - 1] ?? '?';
        return (
          <div>
            <Text strong>
              {monthLabel} {year}
            </Text>
            <div style={{ fontSize: 11, color: 'var(--ide-ink3, #6e6e73)', fontFamily: 'monospace' }}>
              {s.slip_no}
            </div>
          </div>
        );
      },
    },
    {
      title: 'Gross Income',
      dataIndex: 'gross_income',
      align: 'right',
      render: (v) => <Text style={{ fontFamily: 'monospace' }}>{fmtIDR(v)}</Text>,
    },
    {
      title: 'Total Potongan',
      dataIndex: 'total_deductions',
      align: 'right',
      render: (v) => (
        <Text style={{ fontFamily: 'monospace', color: 'var(--ide-red, #FF3B30)' }}>
          {fmtIDR(v)}
        </Text>
      ),
    },
    {
      title: 'Take Home Pay',
      dataIndex: 'take_home_pay',
      align: 'right',
      render: (v) => (
        <Text strong style={{ fontFamily: 'monospace', color: 'var(--ide-green, #34C759)' }}>
          {fmtIDR(v)}
        </Text>
      ),
    },
    {
      title: 'PDF',
      key: 'pdf',
      width: 120,
      align: 'center',
      render: (_, s) => (
        <Button
          size="small"
          type="primary"
          icon={<FilePdfOutlined />}
          loading={pdfDownloadMut.isPending && pdfDownloadMut.variables === s.id}
          onClick={() => pdfDownloadMut.mutate(s.id)}
        >
          Download
        </Button>
      ),
    },
  ];

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1100, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <Title level={3} style={{ margin: 0 }}>
          <DollarOutlined /> Slip Gaji Saya
        </Title>
        <Text type="secondary">
          History slip gaji Anda sejak bulan pertama bekerja di IDE Asia.
          Hanya slip yang sudah disetujui & dipublish yang tampil.
        </Text>
      </div>

      <div
        style={{
          background: 'rgba(0,113,227,0.04)',
          border: '1px solid rgba(0,113,227,0.15)',
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          fontSize: 13,
        }}
      >
        <LockOutlined style={{ color: 'var(--ide-blue, #0071E3)' }} />
        <span>
          <strong>Confidential.</strong> Slip gaji Anda hanya bisa diakses dengan akun ini.
          Jangan share PDF ke pihak lain tanpa kebutuhan resmi.
        </span>
      </div>

      {query.isLoading ? (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <Spin>
            <div style={{ minHeight: 24 }} />
          </Spin>
        </div>
      ) : query.data && query.data.length > 0 ? (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={query.data}
          size="middle"
          pagination={{ pageSize: 12, showSizeChanger: false }}
        />
      ) : (
        <Empty
          description={
            <span>
              <Text type="secondary">Belum ada slip gaji yang tersedia.</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>
                Slip akan muncul setelah payroll bulanan di-approve oleh GM/C-Level.
              </Text>
            </span>
          }
          style={{ padding: 60 }}
        />
      )}

      <div style={{ marginTop: 24, padding: 16, background: 'var(--ide-bg, #F5F5F7)', borderRadius: 8 }}>
        <Text strong style={{ fontSize: 13 }}>
          Pertanyaan tentang slip gaji?
        </Text>
        <div style={{ fontSize: 12, color: 'var(--ide-ink2, #6e6e73)', marginTop: 4 }}>
          Hubungi Finance via Slack channel <code>#hr-payroll</code> atau email{' '}
          <a href="mailto:finance@ide.asia">finance@ide.asia</a>.
        </div>
      </div>
    </div>
  );
}
