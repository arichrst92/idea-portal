/**
 * Forgot Password Page — TSK-007.
 *
 * Flow:
 * 1. User input NIK
 * 2. Submit → backend generate token
 * 3. Display generic success message (anti-enumeration)
 * 4. DEV mode: show token + link untuk testing tanpa email
 */

import { UserOutlined } from '@ant-design/icons';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Alert, Button, Form, Input, Result, Typography } from 'antd';
import type { AxiosError } from 'axios';
import { useState } from 'react';
import { Controller, useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { z } from 'zod';

import { forgotPassword, type ForgotPasswordResponse } from '@/api/auth';

const { Title, Text, Paragraph } = Typography;

const schema = z.object({
  nik: z.string().min(1, 'NIK tidak boleh kosong'),
});

type FormValues = z.infer<typeof schema>;

function ForgotPasswordPage() {
  const [serverError, setServerError] = useState<string | null>(null);
  const [response, setResponse] = useState<ForgotPasswordResponse | null>(null);

  const { control, handleSubmit, formState: { errors } } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { nik: '' },
  });

  const mutation = useMutation<ForgotPasswordResponse, AxiosError<{ detail: { message: string } }>, string>({
    mutationFn: forgotPassword,
    onSuccess: (data) => {
      setResponse(data);
      setServerError(null);
    },
    onError: (error) => {
      const msg = error.response?.data?.detail?.message ?? error.message;
      setServerError(msg);
    },
  });

  const onSubmit = (values: FormValues) => {
    setServerError(null);
    mutation.mutate(values.nik);
  };

  if (response) {
    return (
      <div style={styles.page}>
        <div style={styles.formContainer}>
          <Result
            status="success"
            title="Permintaan terkirim"
            subTitle={response.message}
            extra={
              response.reset_token ? (
                <Alert
                  type="warning"
                  message="DEV mode — token testing"
                  description={
                    <div>
                      <Paragraph style={{ marginBottom: 4 }}>
                        <Text strong>Reset token:</Text> <Text code>{response.reset_token}</Text>
                      </Paragraph>
                      <Paragraph>
                        <Link to={`/reset-password?token=${encodeURIComponent(response.reset_token)}`}>
                          Klik di sini untuk reset password →
                        </Link>
                      </Paragraph>
                    </div>
                  }
                />
              ) : (
                <Link to="/login">← Kembali ke Login</Link>
              )
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div style={styles.page}>
      <div style={styles.formContainer}>
        <Title level={3} style={{ marginBottom: 4 }}>Lupa Password</Title>
        <Text type="secondary" style={{ marginBottom: 32, display: 'block' }}>
          Masukkan NIK Anda untuk request password reset.
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
                />
              )}
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" size="large" block loading={mutation.isPending}>
              Kirim Permintaan Reset
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

export default ForgotPasswordPage;
