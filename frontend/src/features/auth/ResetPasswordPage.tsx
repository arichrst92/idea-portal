/**
 * Reset Password Page — TSK-007.
 *
 * URL: /reset-password?token=<token>
 * Flow: input new password (2x confirm) → submit → redirect login.
 */

import { LockOutlined } from '@ant-design/icons';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Alert, Button, Form, Input, Result, Typography } from 'antd';
import type { AxiosError } from 'axios';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { resetPassword } from '@/api/auth';

const { Title, Text } = Typography;

const schema = z.object({
  password: z
    .string()
    .min(8, 'Password minimal 8 karakter')
    .max(200),
  confirmPassword: z.string().min(1, 'Confirm password wajib'),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Password confirmation tidak sama',
  path: ['confirmPassword'],
});

type FormValues = z.infer<typeof schema>;

function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const { control, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { password: '', confirmPassword: '' },
  });

  const mutation = useMutation<
    { success: boolean; message: string },
    AxiosError<{ detail: { code: string; message: string } }>,
    { token: string; newPassword: string }
  >({
    mutationFn: ({ token, newPassword }) => resetPassword(token, newPassword),
    onSuccess: () => {
      setSuccess(true);
      setServerError(null);
      setTimeout(() => navigate('/login'), 2500);
    },
    onError: (error) => {
      const msg = error.response?.data?.detail?.message ?? error.message;
      setServerError(msg);
    },
  });

  const onSubmit = (values: FormValues) => {
    setServerError(null);
    mutation.mutate({ token, newPassword: values.password });
  };

  if (!token) {
    return (
      <div style={styles.page}>
        <div style={styles.formContainer}>
          <Result
            status="error"
            title="Token tidak ditemukan"
            subTitle="Link reset password tidak valid. Silakan request reset baru."
            extra={<Link to="/forgot-password"><Button type="primary">Request Reset Baru</Button></Link>}
          />
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div style={styles.page}>
        <div style={styles.formContainer}>
          <Result
            status="success"
            title="Password berhasil di-reset"
            subTitle="Anda akan otomatis di-redirect ke halaman login dalam beberapa detik."
            extra={<Link to="/login"><Button type="primary">Login Sekarang</Button></Link>}
          />
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.formContainer}>
        <Title level={3} style={{ marginBottom: 4 }}>Reset Password</Title>
        <Text type="secondary" style={{ marginBottom: 32, display: 'block' }}>
          Masukkan password baru Anda (minimal 8 karakter).
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

        <Form layout="vertical" onFinish={handleSubmit(onSubmit)}>
          <Form.Item
            label="Password Baru"
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
                  placeholder="Minimal 8 karakter"
                  prefix={<LockOutlined style={{ color: '#86868B' }} />}
                  autoFocus
                  autoComplete="new-password"
                />
              )}
            />
          </Form.Item>

          <Form.Item
            label="Konfirmasi Password"
            validateStatus={errors.confirmPassword ? 'error' : ''}
            help={errors.confirmPassword?.message}
          >
            <Controller
              name="confirmPassword"
              control={control}
              render={({ field }) => (
                <Input.Password
                  {...field}
                  size="large"
                  placeholder="Ulangi password baru"
                  prefix={<LockOutlined style={{ color: '#86868B' }} />}
                  autoComplete="new-password"
                />
              )}
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={mutation.isPending}>
              Reset Password
            </Button>
          </Form.Item>

          <div style={{ textAlign: 'center' }}>
            <Link to="/login">← Kembali ke Login</Link>
          </div>
        </Form>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: '100vh',
    background: '#F5F5F7',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  formContainer: {
    width: '100%',
    maxWidth: 440,
    background: '#FFFFFF',
    padding: 40,
    borderRadius: 14,
    boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
  },
};

export default ResetPasswordPage;
