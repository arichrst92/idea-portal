/**
 * PublicKpiPage — TSK-108. Public page (no login) untuk client submit KPI rating.
 *
 * Akses via URL: /public/client-kpi/{token}
 */

import { CheckCircleFilled } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert, Button, Form, Input, Rate, Spin, Typography, message } from 'antd';
import dayjs from 'dayjs';
import { useParams } from 'react-router-dom';

import { getPublicKpiContext, submitPublicKpi } from '@/api/outsource';

const { Title, Text, Paragraph } = Typography;

export default function PublicKpiPage() {
  const { token } = useParams<{ token: string }>();
  const [form] = Form.useForm();

  const ctxQ = useQuery({
    queryKey: ['public-kpi-context', token],
    queryFn: () => getPublicKpiContext(token!),
    enabled: !!token,
    retry: false,
  });

  const submitMut = useMutation({
    mutationFn: (values: any) => submitPublicKpi(token!, values),
    onSuccess: () => {
      message.success('Terima kasih! Penilaian Anda berhasil disimpan.');
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal submit'),
  });

  if (!token) {
    return <Alert type="error" message="Token tidak valid" showIcon />;
  }

  if (ctxQ.isLoading) {
    return (
      <div style={{ padding: 60, textAlign: 'center' }}>
        <Spin size="large" tip="Memuat..." />
      </div>
    );
  }

  if (ctxQ.error || !ctxQ.data) {
    return (
      <div style={{ padding: 60, maxWidth: 520, margin: '0 auto' }}>
        <Alert
          type="error" showIcon
          message="Link tidak valid atau expired"
          description="Mohon hubungi Operation IDE Asia untuk request link baru."
        />
      </div>
    );
  }

  const ctx = ctxQ.data;
  const expired = dayjs(ctx.expires_at).isBefore(dayjs(), 'day');

  // Already submitted state
  if (ctx.is_submitted || submitMut.isSuccess) {
    return (
      <div style={{ padding: 60, maxWidth: 540, margin: '0 auto', textAlign: 'center' }}>
        <CheckCircleFilled style={{ fontSize: 64, color: '#34C759' }} />
        <Title level={3} style={{ marginTop: 16 }}>Terima Kasih</Title>
        <Paragraph>
          Penilaian KPI untuk <strong>{ctx.employee_name}</strong> sudah berhasil di-submit.
          IDE Asia telah menerima feedback Anda.
        </Paragraph>
        <Text type="secondary">Anda boleh tutup halaman ini.</Text>
      </div>
    );
  }

  if (expired) {
    return (
      <div style={{ padding: 60, maxWidth: 520, margin: '0 auto' }}>
        <Alert
          type="warning" showIcon
          message="Link sudah expired"
          description={`Link ini berlaku sampai ${dayjs(ctx.expires_at).format('DD MMM YYYY')}. Mohon hubungi Operation IDE Asia untuk request link baru.`}
        />
      </div>
    );
  }

  return (
    <div style={{ padding: '40px 20px', maxWidth: 720, margin: '0 auto', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ borderBottom: '3px solid #0071E3', paddingBottom: 14, marginBottom: 24 }}>
        <Text strong style={{ fontSize: 18, color: '#0071E3', letterSpacing: -0.5 }}>
          PT. Solusi Inovasi Bangsa
        </Text>
        <div style={{ fontSize: 11, color: '#6e6e73' }}>IDE Asia · IDEA Portal — Client KPI Assessment</div>
      </div>

      <Title level={3} style={{ margin: 0 }}>Penilaian Kinerja Karyawan Outsource</Title>
      <Paragraph type="secondary">
        Mohon bantu IDE Asia dengan menilai performa karyawan yang ditempatkan di perusahaan Anda
        untuk periode <strong>{ctx.assessment_period}</strong>.
      </Paragraph>

      {/* Context card */}
      <div style={{
        background: '#F5F5F7', padding: 16, borderRadius: 8, marginBottom: 24,
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Karyawan</Text>
            <div><strong>{ctx.employee_name}</strong></div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Posisi/Role</Text>
            <div><strong>{ctx.role}</strong></div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Client</Text>
            <div>{ctx.client_name}</div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Periode</Text>
            <div>{ctx.assessment_period}</div>
          </div>
        </div>
      </div>

      {/* Form */}
      <Form
        form={form} layout="vertical"
        onFinish={(v) => submitMut.mutate(v)}
      >
        <Title level={5} style={{ marginTop: 0 }}>Rating (1 = Sangat Kurang, 5 = Sangat Baik)</Title>

        {([
          { name: 'score_quality', label: 'Kualitas Pekerjaan', desc: 'Akurasi, ketelitian, dan standar output' },
          { name: 'score_communication', label: 'Komunikasi', desc: 'Kejelasan, responsif, profesional' },
          { name: 'score_attendance', label: 'Kehadiran & Disiplin', desc: 'Punctual, tidak sering absen' },
          { name: 'score_professionalism', label: 'Profesionalisme', desc: 'Sikap, etika kerja, attitude' },
          { name: 'score_initiative', label: 'Inisiatif', desc: 'Proaktif, problem solving, leadership' },
        ] as const).map((f) => (
          <Form.Item
            key={f.name}
            label={
              <div>
                <strong>{f.label}</strong>
                <div style={{ fontSize: 11, color: '#6e6e73', fontWeight: 400 }}>{f.desc}</div>
              </div>
            }
            name={f.name}
            rules={[{ required: true, message: 'Rating wajib diisi' }]}
          >
            <Rate style={{ fontSize: 28 }} />
          </Form.Item>
        ))}

        <Form.Item
          label={<strong>Feedback / Catatan Tambahan (opsional)</strong>}
          name="feedback"
        >
          <Input.TextArea
            autoSize={{ minRows: 3, maxRows: 6 }}
            placeholder="Ceritakan lebih detail tentang performa karyawan. Saran improvement juga sangat dihargai..."
          />
        </Form.Item>

        <Button
          type="primary" htmlType="submit" size="large" block
          loading={submitMut.isPending}
        >
          Submit Penilaian
        </Button>

        <Text type="secondary" style={{ fontSize: 11, display: 'block', textAlign: 'center', marginTop: 12 }}>
          Setelah di-submit, penilaian tidak bisa diubah. Link ini hanya berlaku 1x.
        </Text>
      </Form>

      <div style={{
        marginTop: 36, paddingTop: 16, borderTop: '1px solid #E8E8ED',
        fontSize: 10, color: '#86868B', textAlign: 'center',
      }}>
        PT. Solusi Inovasi Bangsa · portal.ide.asia · Confidential
      </div>
    </div>
  );
}
