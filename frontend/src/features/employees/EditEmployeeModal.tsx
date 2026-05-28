/**
 * EditEmployeeModal — TSK-013 Polish
 *
 * Modal untuk PATCH employee field (full_name, contact, status, dst).
 * Untuk department/position change pakai MutateModal (audit OrgChange).
 * Untuk promote pakai PromoteModal.
 *
 * Field yang bisa di-edit di sini: data personal + contact + status + financial.
 */

import { useMutation } from '@tanstack/react-query';
import { Alert, Button, DatePicker, Form, Input, Modal, Select, message } from 'antd';
import type { AxiosError } from 'axios';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';

import { updateEmployee, type EmployeeDetail, type EmployeeUpdateRequest } from '@/api/organization';

interface EditEmployeeModalProps {
  employee: EmployeeDetail;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const { TextArea } = Input;

export function EditEmployeeModal({ employee, open, onClose, onSuccess }: EditEmployeeModalProps) {
  const [form] = Form.useForm();
  const [serverError, setServerError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        full_name: employee.full_name,
        phone_number: employee.phone_number || '',
        address: employee.address || '',
        emergency_contact: employee.emergency_contact || '',
        date_of_birth: employee.date_of_birth ? dayjs(employee.date_of_birth) : null,
        gender: employee.gender || undefined,
        status: employee.status,
        probation_end_date: employee.probation_end_date ? dayjs(employee.probation_end_date) : null,
        bank_name: employee.bank_name || '',
        bank_account: employee.bank_account || '',
        npwp: employee.npwp || '',
      });
      setServerError(null);
    }
  }, [open, form, employee]);

  const mutation = useMutation({
    mutationFn: (data: EmployeeUpdateRequest) => updateEmployee(employee.nik, data),
    onSuccess: () => {
      message.success('Data karyawan diperbarui');
      onSuccess();
      onClose();
    },
    onError: (err: AxiosError<{ detail?: { code?: string; message?: string } }>) => {
      const detail = err.response?.data?.detail;
      setServerError(detail?.message || 'Gagal update');
    },
  });

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: EmployeeUpdateRequest = {
        full_name: values.full_name?.trim() || undefined,
        phone_number: values.phone_number?.trim() || null,
        address: values.address?.trim() || null,
        emergency_contact: values.emergency_contact?.trim() || null,
        date_of_birth: values.date_of_birth ? dayjs(values.date_of_birth).format('YYYY-MM-DD') : null,
        gender: values.gender || null,
        status: values.status,
        probation_end_date: values.probation_end_date
          ? dayjs(values.probation_end_date).format('YYYY-MM-DD')
          : null,
        bank_name: values.bank_name?.trim() || null,
        bank_account: values.bank_account?.trim() || null,
        npwp: values.npwp?.trim() || null,
      };
      mutation.mutate(payload);
    } catch {
      // validation error
    }
  };

  return (
    <Modal
      title={`Edit ${employee.full_name}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Batal
        </Button>,
        <Button key="submit" type="primary" loading={mutation.isPending} onClick={handleSubmit}>
          Simpan
        </Button>,
      ]}
      destroyOnClose
      width={620}
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
          fontSize: 11,
          color: 'var(--ide-ink3)',
          marginBottom: 14,
          padding: '6px 10px',
          background: 'var(--ide-bg)',
          borderRadius: 'var(--ide-rs)',
        }}
      >
        NIK <strong style={{ fontFamily: 'var(--ide-font-mono)' }}>{employee.nik}</strong> tidak bisa diubah.
        Untuk pindah dept/posisi, gunakan Mutate/Promote.
      </div>

      <Form form={form} layout="vertical">
        <Form.Item
          label="Nama Lengkap"
          name="full_name"
          rules={[{ required: true, message: 'Nama tidak boleh kosong' }]}
        >
          <Input placeholder="Nama lengkap" />
        </Form.Item>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="Nomor HP" name="phone_number">
            <Input placeholder="08xx-xxxx-xxxx" />
          </Form.Item>
          <Form.Item label="Gender" name="gender">
            <Select
              allowClear
              placeholder="Pilih gender"
              options={[
                { value: 'Male', label: 'Male' },
                { value: 'Female', label: 'Female' },
                { value: 'Other', label: 'Other' },
              ]}
            />
          </Form.Item>
        </div>

        <Form.Item label="Tanggal Lahir" name="date_of_birth">
          <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
        </Form.Item>

        <Form.Item label="Alamat" name="address">
          <TextArea rows={2} placeholder="Alamat lengkap" />
        </Form.Item>

        <Form.Item label="Emergency Contact" name="emergency_contact">
          <Input placeholder="Nama & nomor kontak darurat" />
        </Form.Item>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="Status" name="status">
            <Select
              options={[
                { value: 'PROBATION', label: 'Probation' },
                { value: 'ACTIVE', label: 'Active' },
                { value: 'ON_LEAVE', label: 'On Leave' },
                { value: 'RESIGNED', label: 'Resigned' },
                { value: 'TERMINATED', label: 'Terminated' },
                { value: 'ALUMNI', label: 'Alumni' },
              ]}
            />
          </Form.Item>
          <Form.Item label="Probation End Date" name="probation_end_date">
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
        </div>

        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
            margin: '8px 0 6px',
          }}
        >
          Financial
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="Bank" name="bank_name">
            <Input placeholder="BCA, Mandiri, dll" />
          </Form.Item>
          <Form.Item label="Rekening" name="bank_account">
            <Input style={{ fontFamily: 'var(--ide-font-mono)' }} placeholder="123-456-7890" />
          </Form.Item>
        </div>

        <Form.Item label="NPWP" name="npwp">
          <Input style={{ fontFamily: 'var(--ide-font-mono)' }} placeholder="xx.xxx.xxx.x-xxx.xxx" />
        </Form.Item>
      </Form>
    </Modal>
  );
}
