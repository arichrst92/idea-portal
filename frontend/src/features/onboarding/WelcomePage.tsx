/**
 * WelcomePage — TSK-040 (US-OP-003 AC-04+AC-05).
 *
 * Display:
 * - Hero header dengan welcome text
 * - Employee info card (nama, position, dept, supervisor, join date)
 * - Resources grid (handbook, SOP, IT support, HR contact)
 * - Mark seen button (dismiss)
 *
 * Auto-rendered di Dashboard via WelcomeBanner kalau show_welcome=true.
 */

import {
  ApartmentOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  RocketOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Empty, Spin, Typography } from 'antd';
import dayjs from 'dayjs';
import { useNavigate } from 'react-router-dom';

import { apiClient } from '@/api/client';
import { message } from '@/lib/notify';

const { Title, Text, Paragraph } = Typography;

interface WelcomeInfo {
  new_employee: boolean;
  show_welcome: boolean;
  welcome_seen_at: string | null;
  employee_name: string;
  joined_date: string | null;
  department_name: string | null;
  position_name: string | null;
  supervisor_name: string | null;
  resources: Array<{ label: string; url: string; icon: string }>;
}

export default function WelcomePage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['welcome-info'],
    queryFn: async () => {
      const r = await apiClient.get<WelcomeInfo>('/api/v1/employees/me/welcome-info');
      return r.data;
    },
  });

  const markSeenMut = useMutation({
    mutationFn: async () => {
      await apiClient.post('/api/v1/employees/me/welcome-seen');
    },
    onSuccess: () => {
      message.success('Selamat bergabung di IDE Asia! 🎉');
      queryClient.invalidateQueries({ queryKey: ['welcome-info'] });
      navigate('/');
    },
  });

  if (query.isLoading) {
    return (
      <div style={{ padding: 60, textAlign: 'center' }}>
        <Spin>
          <div style={{ minHeight: 24 }} />
        </Spin>
      </div>
    );
  }

  const data = query.data;
  if (!data || !data.employee_name) {
    return (
      <div style={{ padding: 40, maxWidth: 600, margin: '0 auto' }}>
        <Empty description="Welcome info tidak tersedia. Mungkin Anda tidak terhubung dengan record karyawan." />
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '24px 24px 60px' }}>
      {/* Hero */}
      <div
        style={{
          background:
            'linear-gradient(135deg, #0071E3 0%, #5856D6 50%, #AF52DE 100%)',
          color: 'white',
          borderRadius: 16,
          padding: '40px 32px',
          marginBottom: 24,
          textAlign: 'center',
        }}
      >
        <RocketOutlined style={{ fontSize: 48, marginBottom: 12 }} />
        <Title level={1} style={{ color: 'white', margin: 0, fontSize: 36 }}>
          Selamat Datang!
        </Title>
        <Paragraph
          style={{
            color: 'rgba(255,255,255,0.92)',
            fontSize: 16,
            marginTop: 12,
            marginBottom: 0,
          }}
        >
          Senang Anda bergabung di <strong>PT. Solusi Inovasi Bangsa (IDE Asia)</strong>.
          <br />
          Kami percaya kontribusi Anda akan membuat perubahan nyata.
        </Paragraph>
      </div>

      {/* Employee info card */}
      <div
        style={{
          background: 'var(--ide-surface, white)',
          border: '1px solid var(--ide-border, #E8E8ED)',
          borderRadius: 12,
          padding: 24,
          marginBottom: 24,
        }}
      >
        <Title level={4} style={{ marginTop: 0, marginBottom: 16 }}>
          Profil Anda
        </Title>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: 16,
            fontSize: 14,
          }}
        >
          <div>
            <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase' }}>
              <UserOutlined /> Nama
            </Text>
            <div style={{ fontWeight: 700, fontSize: 16, marginTop: 4 }}>
              {data.employee_name}
            </div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase' }}>
              <CalendarOutlined /> Tanggal Join
            </Text>
            <div style={{ fontWeight: 600, marginTop: 4 }}>
              {data.joined_date ? dayjs(data.joined_date).format('DD MMMM YYYY') : '—'}
            </div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase' }}>
              <ApartmentOutlined /> Departemen
            </Text>
            <div style={{ fontWeight: 600, marginTop: 4 }}>
              {data.department_name ?? '—'}
            </div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase' }}>
              Posisi
            </Text>
            <div style={{ fontWeight: 600, marginTop: 4 }}>
              {data.position_name ?? '—'}
            </div>
          </div>
          <div style={{ gridColumn: 'span 2' }}>
            <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase' }}>
              <TeamOutlined /> Supervisor Langsung
            </Text>
            <div style={{ fontWeight: 600, marginTop: 4 }}>
              {data.supervisor_name ?? '— belum di-assign'}
            </div>
          </div>
        </div>
      </div>

      {/* Resources */}
      <div
        style={{
          background: 'var(--ide-surface, white)',
          border: '1px solid var(--ide-border, #E8E8ED)',
          borderRadius: 12,
          padding: 24,
          marginBottom: 24,
        }}
      >
        <Title level={4} style={{ marginTop: 0, marginBottom: 6 }}>
          Sumber Daya Penting
        </Title>
        <Paragraph type="secondary" style={{ marginBottom: 16, fontSize: 13 }}>
          Mohon pelajari dokumen ini selama probation Anda.
        </Paragraph>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 12,
          }}
        >
          {data.resources.map((r) => (
            <a
              key={r.label}
              href={r.url}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: 14,
                background: 'var(--ide-bg, #F5F5F7)',
                borderRadius: 8,
                textDecoration: 'none',
                color: 'inherit',
                border: '1px solid transparent',
                transition: 'all 0.12s',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--ide-blue, #0071E3)';
                e.currentTarget.style.background = 'rgba(0,113,227,0.04)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'transparent';
                e.currentTarget.style.background = 'var(--ide-bg, #F5F5F7)';
              }}
            >
              <span style={{ fontSize: 24 }}>{r.icon}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{r.label}</div>
                <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>Klik untuk buka</div>
              </div>
            </a>
          ))}
        </div>
      </div>

      {/* Next steps */}
      <div
        style={{
          background: 'rgba(0,113,227,0.06)',
          border: '1px solid rgba(0,113,227,0.2)',
          borderRadius: 12,
          padding: 20,
          marginBottom: 24,
          textAlign: 'center',
        }}
      >
        <Title level={5} style={{ color: 'var(--ide-blue, #0071E3)', margin: 0 }}>
          🎯 Langkah Berikutnya
        </Title>
        <Paragraph style={{ marginTop: 8, marginBottom: 0, fontSize: 13 }}>
          Buka <strong>Onboarding Checklist</strong> untuk lengkapi data Anda
          (KTP, NPWP, BPJS, dll). Operation akan kontak Anda dalam 1-2 hari kerja.
        </Paragraph>
      </div>

      {/* Mark seen */}
      <div style={{ textAlign: 'center' }}>
        <Button
          type="primary"
          size="large"
          icon={<CheckCircleOutlined />}
          onClick={() => markSeenMut.mutate()}
          loading={markSeenMut.isPending}
        >
          Saya Sudah Membaca · Lanjut ke Dashboard
        </Button>
        {data.welcome_seen_at && (
          <Paragraph
            type="secondary"
            style={{ fontSize: 11, marginTop: 8, marginBottom: 0 }}
          >
            Welcome page sudah Anda baca pada{' '}
            {dayjs(data.welcome_seen_at).format('DD MMM YYYY HH:mm')}.
          </Paragraph>
        )}
      </div>
    </div>
  );
}
