/**
 * Login Page — TSK-001 + TSK-010 (Login Page UI)
 *
 * Port dari GUI html/IDEA_Login.html ke React + Ant Design.
 * Layout: split-screen — left dark hero, right white form.
 * Form: NIK + password, validasi via React Hook Form + Zod.
 *
 * Aturan (knowledge.md):
 * - Login pakai NIK, BUKAN email (sec.1)
 * - NC-SYS-001-01: 5x failed → account locked 30 min (handled backend)
 *
 * AC reference (US-EX-005 untuk Wakil Direktur — generic login flow):
 * - Form NIK + password
 * - Show/hide password toggle
 * - Validation: tidak boleh kosong
 * - Error message dari backend (invalid credentials, locked, inactive)
 */

import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Alert, Button, Form, Input, Typography } from 'antd';
import type { AxiosError } from 'axios';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { z } from 'zod';

import { login, type ApiError, type LoginRequest, type LoginResponse } from '@/api/auth';
import { useAuthStore } from '@/store/auth';

const { Title, Text, Paragraph } = Typography;

const loginSchema = z.object({
  nik: z.string().min(1, 'NIK tidak boleh kosong'),
  password: z.string().min(1, 'Password tidak boleh kosong'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [serverError, setServerError] = useState<string | null>(null);

  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { nik: '', password: '' },
  });

  const mutation = useMutation<LoginResponse, AxiosError<{ detail: ApiError }>, LoginRequest>({
    mutationFn: login,
    onSuccess: (data) => {
      setAuth(data.user, data.access_token, data.refresh_token);
      setServerError(null);
      navigate('/');
    },
    onError: (error) => {
      const detail = error.response?.data?.detail;
      if (detail?.message) {
        setServerError(detail.message);
      } else if (error.message) {
        setServerError(`Koneksi error: ${error.message}`);
      } else {
        setServerError('Terjadi kesalahan. Silakan coba lagi.');
      }
    },
  });

  const onSubmit = (values: LoginFormValues) => {
    setServerError(null);
    mutation.mutate(values);
  };

  return (
    <div style={styles.page}>
      {/* LEFT PANEL — Dark hero */}
      <div style={styles.leftPanel}>
        <div style={styles.leftPanelOverlay} />
        <div style={styles.leftTop}>
          <div style={styles.logo}>
            <div style={styles.logoMark}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="3" width="7" height="7" rx="1.8" fill="#0A0A0A" />
                <rect x="14" y="3" width="7" height="7" rx="1.8" fill="#0A0A0A" opacity=".5" />
                <rect x="3" y="14" width="7" height="7" rx="1.8" fill="#0A0A0A" opacity=".5" />
                <rect x="14" y="14" width="7" height="7" rx="1.8" fill="#0A0A0A" opacity=".85" />
              </svg>
            </div>
            <div>
              <div style={styles.logoName}>IDEA</div>
              <div style={styles.logoTagline}>IT Consultant &amp; Outsourcing</div>
            </div>
          </div>
        </div>

        <div style={styles.leftMiddle}>
          <Title level={2} style={{ color: '#fff', marginBottom: 16 }}>
            Portal Karyawan IDEA
          </Title>
          <Paragraph style={{ color: 'rgba(255,255,255,.7)', fontSize: 14, maxWidth: 400 }}>
            ERP &amp; HRIS untuk seluruh karyawan PT. Solusi Inovasi Bangsa.
            Login dengan NIK Anda untuk akses portal.
          </Paragraph>
        </div>

        <div style={styles.leftBottom}>
          <Text style={{ color: 'rgba(255,255,255,.4)', fontSize: 11 }}>
            © {new Date().getFullYear()} PT. Solusi Inovasi Bangsa
          </Text>
        </div>
      </div>

      {/* RIGHT PANEL — Login form */}
      <div style={styles.rightPanel}>
        <div style={styles.formContainer}>
          <Title level={3} style={{ marginBottom: 4 }}>
            Sign In
          </Title>
          <Text type="secondary" style={{ marginBottom: 32, display: 'block' }}>
            Masukkan NIK dan password Anda
          </Text>

          {serverError && (
            <Alert
              type="error"
              message={serverError}
              showIcon
              style={{ marginBottom: 16 }}
              closable
              onClose={() => setServerError(null)}
            />
          )}

          <Form layout="vertical" onFinish={handleSubmit(onSubmit)} autoComplete="on">
            <Form.Item
              label="NIK Karyawan"
              validateStatus={errors.nik ? 'error' : ''}
              help={errors.nik?.message}
            >
              <Controller
                name="nik"
                control={control}
                render={({ field }) => (
                  <Input
                    {...field}
                    size="large"
                    placeholder="Contoh: EMP-001"
                    prefix={<UserOutlined style={{ color: '#86868B' }} />}
                    autoFocus
                    autoComplete="username"
                  />
                )}
              />
            </Form.Item>

            <Form.Item
              label="Password"
              validateStatus={errors.password ? 'error' : ''}
              help={errors.password?.message}
            >
              <Controller
                name="password"
                control={control}
                render={({ field }) => (
                  <Input.Password
                    {...field}
                    size="large"
                    placeholder="Password"
                    prefix={<LockOutlined style={{ color: '#86868B' }} />}
                    autoComplete="current-password"
                  />
                )}
              />
            </Form.Item>

            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                size="large"
                block
                loading={mutation.isPending}
              >
                Masuk
              </Button>
            </Form.Item>

            <div style={styles.forgotLink}>
              <a onClick={() => navigate('/forgot-password')} style={{ cursor: 'pointer' }}>
                Lupa password?
              </a>
            </div>
          </Form>

          <div style={styles.helpBox}>
            <Text strong style={{ display: 'block', marginBottom: 4 }}>
              NIK &amp; password dikonfigurasi oleh IT Admin
            </Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              Hubungi Dept. Operation jika belum memiliki akun atau lupa password.
            </Text>
          </div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
  },
  leftPanel: {
    position: 'relative',
    background: '#0A0A0A',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    padding: '52px 56px',
    overflow: 'hidden',
  },
  leftPanelOverlay: {
    position: 'absolute',
    inset: 0,
    background: `
      radial-gradient(ellipse 80% 60% at 20% 20%, rgba(0,113,227,0.18) 0%, transparent 60%),
      radial-gradient(ellipse 60% 80% at 80% 80%, rgba(0,113,227,0.10) 0%, transparent 60%)
    `,
    pointerEvents: 'none',
  },
  leftTop: { position: 'relative', zIndex: 1 },
  leftMiddle: {
    position: 'relative',
    zIndex: 1,
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
  },
  leftBottom: { position: 'relative', zIndex: 1 },
  logo: { display: 'flex', alignItems: 'center', gap: 14 },
  logoMark: {
    width: 40,
    height: 40,
    background: '#FFFFFF',
    borderRadius: 10,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  logoName: { color: '#fff', fontSize: 22, fontWeight: 700, lineHeight: 1 },
  logoTagline: { color: 'rgba(255,255,255,.5)', fontSize: 11, marginTop: 4 },
  rightPanel: {
    background: '#FFFFFF',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  formContainer: {
    width: '100%',
    maxWidth: 400,
  },
  forgotLink: {
    textAlign: 'center',
    fontSize: 13,
    marginBottom: 24,
  },
  helpBox: {
    marginTop: 32,
    padding: 16,
    background: '#F5F5F7',
    borderRadius: 10,
    fontSize: 13,
  },
};

export default LoginPage;
