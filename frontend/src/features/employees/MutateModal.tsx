/**
 * MutateModal — TSK-013 Polish + TSK-198 (pre-check warnings).
 *
 * Modal untuk lateral move: change dept, position, supervisor.
 * Bisa pilih salah satu / kombinasi (semua field optional).
 *
 * Per US-OP-013:
 *   AC-03: Active project memberships harus diresolve sebelum mutation efektif
 *   AC-07: Block kalau pending SP1/SP2 — harus resolved first
 * Reason + effective_date wajib, audit ke OrgChange.
 */

import { ExclamationCircleOutlined } from '@ant-design/icons';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Checkbox,
  DatePicker,
  Form,
  Input,
  Modal,
  Select,
  Typography,
} from 'antd';
import { message } from '@/lib/notify';
import type { AxiosError } from 'axios';
import dayjs from 'dayjs';
import { useEffect, useState } from 'react';

import {
  listDepartments,
  listPositions,
  mutateEmployee,
  type EmployeeDetail,
} from '@/api/organization';

const { Text } = Typography;

interface MutateModalProps {
  employee: EmployeeDetail;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const { TextArea } = Input;

export function MutateModal({ employee, open, onClose, onSuccess }: MutateModalProps) {
  const [form] = Form.useForm();
  const [serverError, setServerError] = useState<string | null>(null);
  const [selectedDept, setSelectedDept] = useState<string | undefined>(
    employee.department_id || undefined,
  );

  // TSK-198 AC-03/AC-07 — pre-flight checklist (manual confirmation)
  const [noActiveSP, setNoActiveSP] = useState(false);
  const [projectsResolved, setProjectsResolved] = useState(false);

  useEffect(() => {
    if (open) {
      form.resetFields();
      setSelectedDept(employee.department_id || undefined);
      setServerError(null);
      setNoActiveSP(false);
      setProjectsResolved(false);
    }
  }, [open, form, employee.department_id]);

  const deptQuery = useQuery({ queryKey: ['departments'], queryFn: listDepartments, enabled: open });
  const posQuery = useQuery({
    queryKey: ['positions-mutate', selectedDept],
    queryFn: () => listPositions(selectedDept),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: (values: {
      new_department_id?: string;
      new_position_id?: string;
      effective_date: string;
      reason: string;
    }) => mutateEmployee(employee.nik, values),
    onSuccess: () => {
      message.success('Mutasi berhasil');
      onSuccess();
      onClose();
    },
    onError: (err: AxiosError<{ detail?: { code?: string; message?: string } }>) => {
      const detail = err.response?.data?.detail;
      setServerError(detail?.message || 'Gagal mutasi');
    },
  });

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: Parameters<typeof mutation.mutate>[0] = {
        effective_date: dayjs(values.effective_date).format('YYYY-MM-DD'),
        reason: values.reason,
      };
      if (values.new_department_id) payload.new_department_id = values.new_department_id;
      if (values.new_position_id) payload.new_position_id = values.new_position_id;

      if (!payload.new_department_id && !payload.new_position_id) {
        setServerError('Pilih minimal 1 perubahan (dept atau posisi)');
        return;
      }

      // TSK-198 — block kalau pre-check belum lengkap
      if (!noActiveSP || !projectsResolved) {
        setServerError(
          'Pre-check belum lengkap. Konfirmasi: (1) tidak ada SP1/SP2 aktif, (2) project memberships sudah di-resolve.'
        );
        return;
      }

      mutation.mutate(payload);
    } catch {
      // validation error
    }
  };

  return (
    <Modal
      title={`Mutasi ${employee.full_name}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Batal
        </Button>,
        <Button key="submit" type="primary" loading={mutation.isPending} onClick={handleSubmit}>
          Mutasi
        </Button>,
      ]}
      destroyOnHidden
      width={560}
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
          background: 'var(--ide-orange-soft)',
          padding: '8px 12px',
          borderRadius: 'var(--ide-rs)',
          marginBottom: 16,
        }}
      >
        Saat ini: <strong>{employee.department_name || '—'}</strong> · <strong>{employee.position_name || '—'}</strong>
        <br />
        Pilih minimal 1 field yang berubah (dept atau posisi). Supervisor change akan diaktivasi setelah supervisor picker dengan UUID lookup tersedia.
      </div>

      {/* TSK-198 AC-03 + AC-07 — pre-flight checklist */}
      <div
        style={{
          background: 'rgba(255,149,0,0.06)',
          border: '1px solid rgba(255,149,0,0.3)',
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
        }}
      >
        <Text strong style={{ fontSize: 12, color: 'var(--ide-orange, #FF9500)' }}>
          <ExclamationCircleOutlined /> Pre-flight Check (wajib confirm semua)
        </Text>
        <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <Checkbox checked={noActiveSP} onChange={(e) => setNoActiveSP(e.target.checked)}>
            <Text style={{ fontSize: 12 }}>
              Karyawan ini <strong>tidak punya SP1/SP2 aktif</strong> yang belum di-clear
              (NC US-OP-013 AC-07).
            </Text>
          </Checkbox>
          <Checkbox
            checked={projectsResolved}
            onChange={(e) => setProjectsResolved(e.target.checked)}
          >
            <Text style={{ fontSize: 12 }}>
              Active project memberships sudah di-<strong>released</strong> atau di-transfer
              (AC-03). PMs sudah diberitahu.
            </Text>
          </Checkbox>
        </div>
      </div>

      <Form form={form} layout="vertical">
        <Form.Item label="Departemen Baru" name="new_department_id">
          <Select
            placeholder="Pilih dept baru (opsional)"
            allowClear
            loading={deptQuery.isLoading}
            onChange={(v) => setSelectedDept(v)}
            options={(deptQuery.data || []).map((d) => ({
              value: d.id,
              label: `${d.code} · ${d.name}`,
            }))}
          />
        </Form.Item>

        <Form.Item label="Posisi Baru" name="new_position_id">
          <Select
            placeholder="Pilih posisi baru (opsional)"
            allowClear
            loading={posQuery.isLoading}
            options={(posQuery.data || []).map((p) => ({
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
          label="Alasan Mutasi"
          name="reason"
          rules={[
            { required: true, message: 'Alasan wajib diisi (min 10 karakter)' },
            { min: 10, message: 'Min 10 karakter' },
            { max: 1000, message: 'Max 1000 karakter' },
          ]}
        >
          <TextArea
            rows={4}
            placeholder="Contoh: Restrukturisasi tim Q3, dipindah ke Operations untuk handle scaling infrastructure."
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}
