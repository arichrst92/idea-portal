/**
 * PromoteModal — TSK-013 Polish
 *
 * Modal untuk promote employee ke posisi lebih tinggi (level lebih rendah).
 * Validasi: new_position_level < current_position_level (backend enforce 400).
 *
 * Per US-OP-012: reason + effective_date wajib, audit ke OrgChange.
 */

import { useMutation, useQuery } from '@tanstack/react-query';
import { Alert, Button, DatePicker, Form, Input, Modal, Select} from 'antd';
import { message } from '@/lib/notify';
import type { AxiosError } from 'axios';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';

import { listPositions, promoteEmployee, type EmployeeDetail } from '@/api/organization';

interface PromoteModalProps {
  employee: EmployeeDetail;
  open: boolean;
  currentPositionLevel: number | null; // dari emp.position.level
  onClose: () => void;
  onSuccess: () => void;
}

const { TextArea } = Input;

export function PromoteModal({
  employee,
  open,
  currentPositionLevel,
  onClose,
  onSuccess,
}: PromoteModalProps) {
  const [form] = Form.useForm();
  const [serverError, setServerError] = useState<string | null>(null);

  // Reset form saat modal open/close
  useEffect(() => {
    if (open) {
      form.resetFields();
      setServerError(null);
    }
  }, [open, form]);

  // Filter positions: hanya yang level < current (promosi = naik = level lebih rendah)
  const posQuery = useQuery({
    queryKey: ['positions-promote', employee.department_id],
    queryFn: () => listPositions(employee.department_id || undefined),
    enabled: open,
  });

  const eligiblePositions = (posQuery.data || []).filter(
    (p) => currentPositionLevel === null || p.level < currentPositionLevel,
  );

  const mutation = useMutation({
    mutationFn: (values: {
      new_position_id: string;
      effective_date: string;
      reason: string;
    }) => promoteEmployee(employee.nik, values),
    onSuccess: () => {
      message.success('Promosi berhasil');
      onSuccess();
      onClose();
    },
    onError: (err: AxiosError<{ detail?: { code?: string; message?: string } }>) => {
      const detail = err.response?.data?.detail;
      setServerError(detail?.message || 'Gagal promosi');
    },
  });

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      mutation.mutate({
        new_position_id: values.new_position_id,
        effective_date: dayjs(values.effective_date).format('YYYY-MM-DD'),
        reason: values.reason,
      });
    } catch {
      // Validation error — AntD will display
    }
  };

  return (
    <Modal
      title={`Promote ${employee.full_name}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Batal
        </Button>,
        <Button key="submit" type="primary" loading={mutation.isPending} onClick={handleSubmit}>
          Promosi
        </Button>,
      ]}
      destroyOnHidden
    >
      {serverError && (
        <Alert
          type="error"
          message={serverError}
          showIcon
          closable
          onClose={() => setServerError(null)}
          style={{ marginBottom: 16 }}
        />
      )}

      <div
        style={{
          fontSize: 12,
          color: 'var(--ide-ink2)',
          background: 'var(--ide-blue-soft)',
          padding: '8px 12px',
          borderRadius: 'var(--ide-rs)',
          marginBottom: 16,
        }}
      >
        Posisi saat ini: <strong>{employee.position_name || '—'}</strong>{' '}
        {currentPositionLevel !== null && <>(Level {currentPositionLevel})</>}
      </div>

      <Form form={form} layout="vertical" requiredMark>
        <Form.Item
          label="Posisi Baru"
          name="new_position_id"
          rules={[{ required: true, message: 'Pilih posisi tujuan promosi' }]}
        >
          <Select
            placeholder={eligiblePositions.length === 0 ? 'Tidak ada posisi lebih tinggi tersedia' : 'Pilih posisi baru'}
            loading={posQuery.isLoading}
            disabled={eligiblePositions.length === 0}
            options={eligiblePositions.map((p) => ({
              value: p.id,
              label: `${p.code} · ${p.name} (Level ${p.level})`,
            }))}
          />
        </Form.Item>

        <Form.Item
          label="Tanggal Efektif"
          name="effective_date"
          rules={[{ required: true, message: 'Tanggal efektif wajib diisi' }]}
        >
          <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
        </Form.Item>

        <Form.Item
          label="Alasan Promosi"
          name="reason"
          rules={[
            { required: true, message: 'Alasan wajib diisi (min 10 karakter)' },
            { min: 10, message: 'Min 10 karakter' },
            { max: 1000, message: 'Max 1000 karakter' },
          ]}
        >
          <TextArea
            rows={4}
            placeholder="Contoh: Performance excellent selama 6 bulan, dengan rating rata-rata 92/100. Initiative dalam migrasi sistem legacy."
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
