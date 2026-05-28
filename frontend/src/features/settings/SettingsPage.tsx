/**
 * Settings Page — user preferences (theme, font size, motion, password).
 *
 * Accessible via /settings untuk authenticated users.
 * Sections:
 * - Tampilan (theme, font size)
 * - Aksesibilitas (reduced motion)
 * - Keamanan (change password)
 */

import { LockOutlined } from '@ant-design/icons';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import {
  App as AntApp,
  Button,
  Card,
  Form,
  Input,
  Segmented,
  Space,
  Switch,
  Typography,
} from 'antd';
import type { AxiosError } from 'axios';
import { Controller, useForm } from 'react-hook-form';
import { z } from 'zod';

import { changePassword } from '@/api/auth';
import { ThemeSwitcher } from '@/components/ThemeSwitcher';
import { type FontSize, usePreferencesStore } from '@/store/preferences';

const { Title, Text, Paragraph } = Typography;

const passwordSchema = z
  .object({
    current: z.string().min(1, 'Password lama wajib'),
    next: z.string().min(8, 'Password baru minimal 8 karakter'),
    confirm: z.string().min(1, 'Confirm password wajib'),
  })
  .refine((d) => d.next === d.confirm, {
    message: 'Confirm password tidak sama',
    path: ['confirm'],
  })
  .refine((d) => d.next !== d.current, {
    message: 'Password baru tidak boleh sama dengan password lama',
    path: ['next'],
  });

type PasswordFormValues = z.infer<typeof passwordSchema>;

function SettingsPage() {
  const { notification } = AntApp.useApp();
  const fontSize = usePreferencesStore((s) => s.fontSize);
  const setFontSize = usePreferencesStore((s) => s.setFontSize);
  const reducedMotion = usePreferencesStore((s) => s.reducedMotion);
  const setReducedMotion = usePreferencesStore((s) => s.setReducedMotion);

  const { control, handleSubmit, reset, formState: { errors } } = useForm<PasswordFormValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: { current: '', next: '', confirm: '' },
  });

  const passwordMutation = useMutation<
    { success: boolean; message: string },
    AxiosError<{ detail: { message: string } }>,
    { current: string; next: string }
  >({
    mutationFn: ({ current, next }) => changePassword(current, next),
    onSuccess: (data) => {
      notification.success({ message: 'Password diubah', description: data.message });
      reset();
    },
    onError: (err) => {
      const msg = err.response?.data?.detail?.message ?? 'Gagal ubah password';
      notification.error({ message: 'Error', description: msg });
    },
  });

  const onSubmitPassword = (values: PasswordFormValues) => {
    passwordMutation.mutate({ current: values.current, next: values.next });
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: 720, margin: '0 auto' }}>
      <Title level={2}>⚙️ Pengaturan</Title>
      <Paragraph type="secondary">Sesuaikan tampilan dan keamanan akun Anda.</Paragraph>

      <Card title="🎨 Tampilan" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>Theme mode</Text>
            <ThemeSwitcher size="middle" />
            <Paragraph type="secondary" style={{ fontSize: 12, marginTop: 6, marginBottom: 0 }}>
              "System" mengikuti preferensi OS Anda (Light/Dark).
            </Paragraph>
          </div>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>Ukuran font</Text>
            <Segmented<FontSize>
              value={fontSize}
              onChange={(v) => setFontSize(v)}
              options={[
                { label: 'Kecil (13px)', value: 'small' },
                { label: 'Sedang (14px)', value: 'medium' },
                { label: 'Besar (16px)', value: 'large' },
              ]}
              aria-label="Font size"
            />
          </div>
        </Space>
      </Card>

      <Card title="♿ Aksesibilitas" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <Text strong>Reduced motion</Text>
              <Paragraph type="secondary" style={{ fontSize: 12, margin: 0 }}>
                Kurangi animasi untuk pengguna yang sensitif gerakan.
              </Paragraph>
            </div>
            <Switch
              checked={reducedMotion}
              onChange={setReducedMotion}
              aria-label="Toggle reduced motion"
            />
          </div>
        </Space>
      </Card>

      <Card title="🔐 Keamanan — Ubah Password">
        <Form layout="vertical" onFinish={handleSubmit(onSubmitPassword)}>
          <Form.Item
            label="Password Lama"
            validateStatus={errors.current ? 'error' : ''}
            help={errors.current?.message}
          >
            <Controller
              name="current"
              control={control}
              render={({ field }) => (
                <Input.Password
                  {...field}
                  size="large"
                  placeholder="Password saat ini"
                  prefix={<LockOutlined />}
                  autoComplete="current-password"
                />
              )}
            />
          </Form.Item>

          <Form.Item
            label="Password Baru"
            validateStatus={errors.next ? 'error' : ''}
            help={errors.next?.message}
          >
            <Controller
              name="next"
              control={control}
              render={({ field }) => (
                <Input.Password
                  {...field}
                  size="large"
                  placeholder="Minimal 8 karakter"
                  prefix={<LockOutlined />}
                  autoComplete="new-password"
                />
              )}
            />
          </Form.Item>

          <Form.Item
            label="Konfirmasi Password Baru"
            validateStatus={errors.confirm ? 'error' : ''}
            help={errors.confirm?.message}
          >
            <Controller
              name="confirm"
              control={control}
              render={({ field }) => (
                <Input.Password
                  {...field}
                  size="large"
                  placeholder="Ulangi password baru"
                  prefix={<LockOutlined />}
                  autoComplete="new-password"
                />
              )}
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={passwordMutation.isPending}>
              Ubah Password
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}

export default SettingsPage;
