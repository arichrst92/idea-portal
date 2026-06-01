/**
 * Separation Detail Page — TSK-017.
 * Timeline approval flow + action buttons sesuai status.
 */

import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  CheckOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  CloseOutlined,
  DollarOutlined,
  ExclamationCircleOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, DatePicker, Empty, Form, Input, Modal, Spin, Typography } from 'antd';
import { message, modal } from '@/lib/notify';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { generateFinalPayroll } from '@/api/payroll';

import {
  SEPARATION_TYPE_META,
  approveL1,
  approveL2,
  cancelSeparation,
  executeSeparation,
  getSeparation,
  recordExitInterview,
  rejectSeparation,
  separationStatusColor,
  type Separation,
} from '@/api/separation';
import { useAuthStore } from '@/store/auth';

const { TextArea } = Input;

function formatDate(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString('id-ID', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return value;
  }
}

function formatDateTime(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('id-ID', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

function formatIDR(value: string | null): string {
  if (!value) return '—';
  const n = parseFloat(value);
  if (!isFinite(n)) return value;
  return `Rp ${n.toLocaleString('id-ID')}`;
}

// ─── Timeline event ──────────────────────────────────────────────

interface TimelineEvent {
  icon: React.ReactNode;
  color: string;
  title: string;
  by: string | null;
  at: string | null;
  notes?: string | null;
}

function TimelineRow({ event, isLast }: { event: TimelineEvent; isLast: boolean }) {
  return (
    <div style={{ display: 'flex', gap: 14, position: 'relative' }}>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: event.color,
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 14,
            flexShrink: 0,
            zIndex: 1,
          }}
        >
          {event.icon}
        </div>
        {!isLast && (
          <div
            style={{
              width: 2,
              flex: 1,
              background: 'var(--ide-border)',
              minHeight: 28,
              marginTop: 4,
            }}
          />
        )}
      </div>
      <div style={{ flex: 1, paddingBottom: 14 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ide-ink)' }}>{event.title}</div>
        <div style={{ fontSize: 11, color: 'var(--ide-ink3)', marginTop: 2 }}>
          {event.by && (
            <>
              <span style={{ fontFamily: 'var(--ide-font-mono)' }}>{event.by}</span>
              {' · '}
            </>
          )}
          {formatDateTime(event.at)}
        </div>
        {event.notes && (
          <div
            style={{
              marginTop: 6,
              fontSize: 12,
              color: 'var(--ide-ink2)',
              background: 'var(--ide-bg)',
              padding: '6px 10px',
              borderRadius: 'var(--ide-rs)',
            }}
          >
            {event.notes}
          </div>
        )}
      </div>
    </div>
  );
}

function buildTimeline(sep: Separation): TimelineEvent[] {
  const events: TimelineEvent[] = [
    {
      icon: <ExclamationCircleOutlined />,
      color: 'var(--ide-blue)',
      title: 'Initiated',
      by: sep.initiated_by_nik,
      at: sep.created_at,
      notes: sep.reason,
    },
  ];

  if (sep.approval_l1_at) {
    events.push({
      icon: <CheckCircleFilled />,
      color: 'var(--ide-green)',
      title: 'Approved L1 (Atasan Langsung)',
      by: sep.approval_l1_nik,
      at: sep.approval_l1_at,
      notes: sep.approval_l1_notes,
    });
  } else if (sep.status === 'PENDING_APPROVAL_L1') {
    events.push({
      icon: <ClockCircleOutlined />,
      color: 'var(--ide-orange)',
      title: 'Pending L1 Approval',
      by: null,
      at: null,
    });
  }

  if (sep.approval_l2_at) {
    events.push({
      icon: <CheckCircleFilled />,
      color: 'var(--ide-green)',
      title: 'Approved L2 (GM/Executive)',
      by: sep.approval_l2_nik,
      at: sep.approval_l2_at,
      notes: sep.approval_l2_notes,
    });
  } else if (sep.status === 'PENDING_APPROVAL_L2') {
    events.push({
      icon: <ClockCircleOutlined />,
      color: 'var(--ide-orange)',
      title: 'Pending L2 Approval',
      by: null,
      at: null,
    });
  }

  if (sep.executed_at) {
    events.push({
      icon: <ThunderboltOutlined />,
      color: 'var(--ide-green)',
      title: 'Executed (Employee deactivated)',
      by: null,
      at: sep.executed_at,
    });
  }

  if (sep.rejected_at) {
    events.push({
      icon: <CloseCircleOutlined />,
      color: 'var(--ide-red)',
      title: 'Rejected',
      by: null,
      at: sep.rejected_at,
      notes: sep.rejection_reason,
    });
  }

  if (sep.cancelled_at) {
    events.push({
      icon: <StopOutlined />,
      color: 'var(--ide-ink3)',
      title: 'Cancelled',
      by: null,
      at: sep.cancelled_at,
      notes: sep.cancellation_reason,
    });
  }

  if (sep.exit_interview_completed_at) {
    events.push({
      icon: <CheckOutlined />,
      color: 'var(--ide-purple)',
      title: 'Exit Interview Recorded',
      by: null,
      at: sep.exit_interview_completed_at,
      notes: sep.exit_interview_notes,
    });
  }

  return events;
}

// ─── Action button group ─────────────────────────────────────────

function ActionBar({
  sep,
  onAction,
  isApprover,
  isInitiator,
}: {
  sep: Separation;
  onAction: () => void;
  isApprover: boolean;
  isInitiator: boolean;
}) {
  const approveMut = useMutation({
    mutationFn: ({ level, notes }: { level: 1 | 2; notes?: string }) =>
      level === 1 ? approveL1(sep.id, notes) : approveL2(sep.id, notes),
    onSuccess: () => {
      message.success('Approved');
      onAction();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal approve'),
  });

  const rejectMut = useMutation({
    mutationFn: (reason: string) => rejectSeparation(sep.id, reason),
    onSuccess: () => {
      message.success('Rejected');
      onAction();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal reject'),
  });

  const cancelMut = useMutation({
    mutationFn: (reason: string) => cancelSeparation(sep.id, reason),
    onSuccess: () => {
      message.success('Cancelled');
      onAction();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal cancel'),
  });

  const executeMut = useMutation({
    mutationFn: () => executeSeparation(sep.id),
    onSuccess: () => {
      message.success('Executed — employee deactivated');
      onAction();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal execute'),
  });

  // TSK-054 Final Payroll
  const [finalPayrollOpen, setFinalPayrollOpen] = useState(false);
  const [finalPayrollForm] = Form.useForm();

  const finalPayrollMut = useMutation({
    mutationFn: (v: any) =>
      generateFinalPayroll({
        employee_id: sep.employee_id,
        last_working_day: v.last_working_day.format('YYYY-MM-DD'),
        pay_date: v.pay_date.format('YYYY-MM-DD'),
        notes: v.notes || null,
      }),
    onSuccess: (res) => {
      message.success(
        `Final payroll generated · Take Home Rp ${parseFloat(res.take_home).toLocaleString('id-ID')} · ${res.days_worked}/${res.working_days_in_month} hari kerja`
      );
      setFinalPayrollOpen(false);
      finalPayrollForm.resetFields();
      onAction();
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail;
      if (d?.code === 'DUPLICATE') {
        message.warning(d.message);
      } else {
        message.error(d?.message ?? 'Gagal generate final payroll');
      }
    },
  });

  const handleApprove = (level: 1 | 2) => {
    modal.confirm({
      title: `Approve L${level}`,
      content: (
        <Form layout="vertical">
          <Form.Item label="Catatan (opsional)">
            <TextArea
              id={`approve-l${level}-notes`}
              rows={3}
              placeholder="Catatan internal..."
            />
          </Form.Item>
        </Form>
      ),
      okText: 'Approve',
      onOk: () => {
        const el = document.getElementById(`approve-l${level}-notes`) as HTMLTextAreaElement | null;
        approveMut.mutate({ level, notes: el?.value || undefined });
      },
    });
  };

  const handleReject = () => {
    modal.confirm({
      title: 'Reject Separation',
      content: (
        <Form layout="vertical">
          <Form.Item label="Alasan Reject (min 10 karakter)" required>
            <TextArea id="reject-reason" rows={3} placeholder="Jelaskan alasan..." />
          </Form.Item>
        </Form>
      ),
      okText: 'Reject',
      okType: 'danger',
      onOk: () => {
        const el = document.getElementById('reject-reason') as HTMLTextAreaElement | null;
        if (!el?.value || el.value.length < 10) {
          message.warning('Alasan min 10 karakter');
          return Promise.reject();
        }
        return rejectMut.mutateAsync(el.value);
      },
    });
  };

  const handleCancel = () => {
    modal.confirm({
      title: 'Cancel Separation',
      content: (
        <Form layout="vertical">
          <Form.Item label="Alasan Cancel (min 10 karakter)" required>
            <TextArea id="cancel-reason" rows={3} placeholder="Mengapa di-cancel..." />
          </Form.Item>
        </Form>
      ),
      okText: 'Cancel Separation',
      okType: 'danger',
      onOk: () => {
        const el = document.getElementById('cancel-reason') as HTMLTextAreaElement | null;
        if (!el?.value || el.value.length < 10) {
          message.warning('Alasan min 10 karakter');
          return Promise.reject();
        }
        return cancelMut.mutateAsync(el.value);
      },
    });
  };

  const handleExecute = () => {
    modal.confirm({
      title: 'Execute Separation',
      content: (
        <div>
          <p>
            Eksekusi separation untuk <strong>{sep.employee_name}</strong>?
          </p>
          <p style={{ fontSize: 12, color: 'var(--ide-ink2)' }}>
            Effects:
            <br />
            • Employee status berubah sesuai tipe ({sep.separation_type})
            <br />
            • Last working day = {formatDate(sep.effective_date)}
            <br />
            • Employee soft-deleted (archive)
            <br />
            • User login dinonaktifkan
          </p>
        </div>
      ),
      okText: 'Execute',
      okType: 'danger',
      onOk: () => executeMut.mutateAsync(),
    });
  };

  const buttons: React.ReactNode[] = [];

  if (sep.status === 'PENDING_APPROVAL_L1' && isApprover && !isInitiator) {
    buttons.push(
      <Button
        key="al1"
        icon={<CheckOutlined />}
        type="primary"
        onClick={() => handleApprove(1)}
        loading={approveMut.isPending}
        style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}
      >
        Approve L1
      </Button>,
    );
    buttons.push(
      <Button key="r" icon={<CloseOutlined />} danger onClick={handleReject}>
        Reject
      </Button>,
    );
  }

  if (sep.status === 'PENDING_APPROVAL_L2' && isApprover && !isInitiator) {
    buttons.push(
      <Button
        key="al2"
        icon={<CheckOutlined />}
        type="primary"
        onClick={() => handleApprove(2)}
        loading={approveMut.isPending}
        style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}
      >
        Approve L2 (Final)
      </Button>,
    );
    buttons.push(
      <Button key="r" icon={<CloseOutlined />} danger onClick={handleReject}>
        Reject
      </Button>,
    );
  }

  if (sep.status === 'APPROVED' && isApprover) {
    buttons.push(
      <Button
        key="e"
        icon={<ThunderboltOutlined />}
        type="primary"
        onClick={handleExecute}
        loading={executeMut.isPending}
        style={{ background: 'var(--ide-red)', borderColor: 'var(--ide-red)' }}
      >
        Execute Separation
      </Button>,
    );
  }

  // TSK-054 — Generate Final Payroll setelah EXECUTED
  if (sep.status === 'EXECUTED' && isApprover) {
    buttons.push(
      <Button
        key="fp"
        icon={<DollarOutlined />}
        type="primary"
        onClick={() => setFinalPayrollOpen(true)}
      >
        Generate Final Payroll
      </Button>,
    );
  }

  if (
    !['EXECUTED', 'CANCELLED', 'REJECTED'].includes(sep.status) &&
    (isInitiator || isApprover)
  ) {
    buttons.push(
      <Button key="c" icon={<StopOutlined />} onClick={handleCancel}>
        Cancel
      </Button>,
    );
  }

  if (buttons.length === 0) {
    return (
      <div style={{ fontSize: 12, color: 'var(--ide-ink3)', fontStyle: 'italic' }}>
        Tidak ada action yang tersedia untuk status saat ini.
      </div>
    );
  }

  return (
    <>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{buttons}</div>

      {/* TSK-054 — Final Payroll Modal */}
      <Modal
        title={<><DollarOutlined /> Generate Final Payroll</>}
        open={finalPayrollOpen}
        onCancel={() => setFinalPayrollOpen(false)}
        footer={null}
        destroyOnHidden
      >
        <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
          Per knowledge.md sec.12: "Gaji prorata jika resign/terminated di tengah
          bulan". Sistem akan hitung prorata basic salary berdasarkan hari kerja
          dari awal bulan sampai last working day, ditambah tunjangan tetap (prorata),
          dikurangi BPJS (full sesuai UU). Komisi sales pending tidak ter-include.
        </Typography.Paragraph>

        <Form
          form={finalPayrollForm}
          layout="vertical"
          initialValues={{
            last_working_day: sep.effective_date ? dayjs(sep.effective_date) : dayjs(),
            pay_date: dayjs(),
          }}
          onFinish={(v) => finalPayrollMut.mutate(v)}
        >
          <Form.Item
            label="Last Working Day"
            name="last_working_day"
            rules={[{ required: true, message: 'Last working day wajib' }]}
            tooltip="Hari terakhir karyawan bekerja. Days worked dihitung dari tanggal 1 bulan ini sampai tanggal ini."
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item
            label="Payment Date"
            name="pay_date"
            rules={[{ required: true, message: 'Payment date wajib' }]}
            tooltip="Tanggal transfer final payroll ke karyawan"
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item label="Notes (opsional)" name="notes">
            <TextArea rows={2} placeholder="Catatan untuk audit log..." />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            loading={finalPayrollMut.isPending}
            icon={<ThunderboltOutlined />}
          >
            Generate Final Payroll
          </Button>
        </Form>
      </Modal>
    </>
  );
}

// ─── Main Detail Page ────────────────────────────────────────────

export default function SeparationDetailPage() {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);

  const query = useQuery({
    queryKey: ['separation', id],
    queryFn: () => getSeparation(id),
    enabled: !!id,
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['separation', id] });
    queryClient.invalidateQueries({ queryKey: ['separations'] });
  };

  if (query.isLoading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <Empty description="Separation tidak ditemukan" />
        <Button onClick={() => navigate('/separations')} style={{ marginTop: 12 }}>
          Kembali
        </Button>
      </div>
    );
  }

  const sep = query.data;
  const typeMeta = SEPARATION_TYPE_META[sep.separation_type];
  const statusTag = separationStatusColor(sep.status);
  const timeline = buildTimeline(sep);

  const isExecutive =
    user?.roles.some((r) => r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA') ??
    false;
  const isApprover =
    isExecutive ||
    (user?.roles.some((r) => ['C_LEVEL', 'GM'].includes(r.code)) ?? false);
  const isInitiator = user?.id === sep.initiated_by_user_id;

  return (
    <div className="ide-font" style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/separations')}
        style={{ marginBottom: 14, fontWeight: 600 }}
      >
        Daftar Separation
      </Button>

      {/* Header card */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          padding: '20px 24px',
          marginBottom: 14,
        }}
      >
        <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--ide-blue), var(--ide-purple))',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 22,
              fontWeight: 800,
              flexShrink: 0,
            }}
          >
            {sep.employee_name?.split(' ').map((n) => n[0]).slice(0, 2).join('').toUpperCase() || '?'}
          </div>
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--ide-ink)' }}>
              {sep.employee_name || '—'}
            </div>
            <div style={{ fontSize: 12, color: 'var(--ide-ink3)', marginTop: 2 }}>
              <span style={{ fontFamily: 'var(--ide-font-mono)' }}>{sep.employee_nik}</span> ·{' '}
              {sep.employee_department || 'No dept'}
            </div>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 8 }}>
              <span
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  color: typeMeta.color,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                {typeMeta.icon} {typeMeta.label}
              </span>
              <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: 'var(--ide-ink3)', textTransform: 'uppercase' }}>
              Effective Date
            </div>
            <div
              style={{
                fontSize: 20,
                fontWeight: 800,
                fontFamily: 'var(--ide-font-mono)',
                color: 'var(--ide-ink)',
              }}
            >
              {formatDate(sep.effective_date)}
            </div>
            <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>
              Notice: {sep.notice_period_days} hari
            </div>
          </div>
        </div>

        <div
          style={{
            marginTop: 16,
            padding: '12px 14px',
            background: 'var(--ide-bg)',
            borderRadius: 'var(--ide-rs)',
            fontSize: 13,
            color: 'var(--ide-ink)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {sep.reason}
        </div>

        {sep.severance_amount && (
          <div style={{ marginTop: 12, fontSize: 12, color: 'var(--ide-ink2)' }}>
            Severance:{' '}
            <strong style={{ fontFamily: 'var(--ide-font-mono)', color: 'var(--ide-green)' }}>
              {formatIDR(sep.severance_amount)}
            </strong>
          </div>
        )}
      </div>

      {/* Action bar */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          padding: '14px 20px',
          marginBottom: 14,
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: 0.8,
            marginBottom: 10,
          }}
        >
          Actions
        </div>
        <ActionBar sep={sep} onAction={refresh} isApprover={isApprover} isInitiator={isInitiator} />
      </div>

      {/* Timeline */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          padding: '20px 24px',
        }}
      >
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: 0.8,
            marginBottom: 14,
          }}
        >
          Timeline
        </div>
        {timeline.map((event, idx) => (
          <TimelineRow key={idx} event={event} isLast={idx === timeline.length - 1} />
        ))}
      </div>
    </div>
  );
}
