/**
 * Leave Request List + Balance Dashboard — TSK-019.
 */

import { CheckOutlined, CloseOutlined, PlusOutlined, StopOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  DatePicker,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Spin,
  message,
} from 'antd';
import type { AxiosError } from 'axios';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  approveLeaveL1,
  approveLeaveL2,
  cancelLeave,
  createLeaveRequest,
  getEmployeeBalances,
  leaveStatusColor,
  leaveTypeColor,
  listLeaveRequests,
  listLeaveTypes,
  rejectLeave,
  type LeaveBalance,
  type LeaveRequestListItem,
  type LeaveRequestStatus,
} from '@/api/leave';
import { listEmployees } from '@/api/organization';
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

// ─── Balance Card ────────────────────────────────────────────────

function BalanceCard({ balance }: { balance: LeaveBalance }) {
  const color = leaveTypeColor(balance.leave_type_code);
  const total = balance.allocated_days + balance.carried_over_days;
  const pct = total > 0 ? Math.round((balance.used_days / total) * 100) : 0;

  return (
    <div
      style={{
        background: 'var(--ide-surface)',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-rm)',
        padding: 14,
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div
          style={{
            fontSize: 11,
            fontWeight: 700,
            color,
            textTransform: 'uppercase',
            letterSpacing: 0.5,
          }}
        >
          {balance.leave_type_code}
        </div>
        <div
          style={{
            fontSize: 18,
            fontWeight: 800,
            color: 'var(--ide-ink)',
            fontFamily: 'var(--ide-font-mono)',
          }}
        >
          {balance.remaining_days}
        </div>
      </div>
      <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginBottom: 8 }}>
        {balance.leave_type_name}
      </div>
      <div style={{ height: 4, background: 'var(--ide-bg)', borderRadius: 2, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: color,
            transition: 'width 0.3s',
          }}
        />
      </div>
      <div
        style={{
          fontSize: 10,
          color: 'var(--ide-ink3)',
          marginTop: 4,
          fontFamily: 'var(--ide-font-mono)',
        }}
      >
        {balance.used_days} / {total} used
      </div>
    </div>
  );
}

// ─── Create Modal ────────────────────────────────────────────────

function CreateLeaveModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const empQuery = useQuery({
    queryKey: ['employees-for-leave'],
    queryFn: () => listEmployees({ page_size: 200 }),
    enabled: open,
  });
  const typeQuery = useQuery({
    queryKey: ['leave-types'],
    queryFn: listLeaveTypes,
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: createLeaveRequest,
    onSuccess: () => {
      message.success('Leave request submitted untuk approval L1');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: AxiosError<{ detail?: { message?: string } }>) => {
      message.error(err.response?.data?.detail?.message || 'Gagal create leave request');
    },
  });

  return (
    <Modal
      title="Submit Leave Request"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          type="primary"
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            mutation.mutate({
              employee_id: v.employee_id,
              leave_type_id: v.leave_type_id,
              start_date: dayjs(v.range[0]).format('YYYY-MM-DD'),
              end_date: dayjs(v.range[1]).format('YYYY-MM-DD'),
              reason: v.reason,
            });
          }}
        >
          Submit
        </Button>,
      ]}
      destroyOnClose
      width={560}
    >
      <Form form={form} layout="vertical">
        <Form.Item
          label="Karyawan"
          name="employee_id"
          rules={[{ required: true, message: 'Pilih karyawan' }]}
        >
          <Select
            placeholder="Cari NIK / nama"
            showSearch
            optionFilterProp="label"
            loading={empQuery.isLoading}
            options={(empQuery.data?.items || []).map((e) => ({
              value: e.id,
              label: `${e.nik} · ${e.full_name}`,
            }))}
          />
        </Form.Item>
        <Form.Item
          label="Jenis Cuti"
          name="leave_type_id"
          rules={[{ required: true }]}
        >
          <Select
            placeholder="Pilih jenis cuti"
            loading={typeQuery.isLoading}
            options={(typeQuery.data || []).map((t) => ({
              value: t.id,
              label: `${t.code} — ${t.name} (${t.default_days_per_year}d/yr${t.is_paid ? '' : ', unpaid'})`,
            }))}
          />
        </Form.Item>
        <Form.Item
          label="Periode Cuti"
          name="range"
          rules={[{ required: true }]}
        >
          <DatePicker.RangePicker style={{ width: '100%' }} format="DD MMM YYYY" />
        </Form.Item>
        <Form.Item label="Alasan" name="reason">
          <TextArea rows={3} placeholder="Liburan keluarga, urusan personal, dst" />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── Approval Row Actions ────────────────────────────────────────

function RowActions({
  req,
  onAction,
  isApprover,
  currentUserId,
}: {
  req: LeaveRequestListItem;
  onAction: () => void;
  isApprover: boolean;
  currentUserId: string | undefined;
}) {
  const approveL1Mut = useMutation({
    mutationFn: () => approveLeaveL1(req.id),
    onSuccess: () => {
      message.success('Approved L1');
      onAction();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message || 'Gagal approve L1'),
  });

  const approveL2Mut = useMutation({
    mutationFn: () => approveLeaveL2(req.id),
    onSuccess: () => {
      message.success('Approved L2 (final) — saldo dikurangi');
      onAction();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message || 'Gagal approve L2'),
  });

  const cancelMut = useMutation({
    mutationFn: () => cancelLeave(req.id),
    onSuccess: () => {
      message.success('Cancelled');
      onAction();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message || 'Gagal cancel'),
  });

  const handleReject = () => {
    Modal.confirm({
      title: 'Reject Leave Request',
      content: (
        <Form layout="vertical">
          <Form.Item label="Alasan reject (min 5 char)" required>
            <TextArea id={`reject-${req.id}`} rows={3} />
          </Form.Item>
        </Form>
      ),
      okText: 'Reject',
      okType: 'danger',
      onOk: async () => {
        const el = document.getElementById(`reject-${req.id}`) as HTMLTextAreaElement;
        if (!el?.value || el.value.length < 5) {
          message.warning('Alasan min 5 karakter');
          return Promise.reject();
        }
        try {
          await rejectLeave(req.id, el.value);
          message.success('Rejected');
          onAction();
        } catch (e: any) {
          message.error(e?.response?.data?.detail?.message || 'Gagal reject');
        }
      },
    });
  };

  const btns: React.ReactNode[] = [];
  if (req.status === 'PENDING_L1' && isApprover) {
    btns.push(
      <Button
        key="al1"
        size="small"
        type="primary"
        icon={<CheckOutlined />}
        loading={approveL1Mut.isPending}
        onClick={() => approveL1Mut.mutate()}
        style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}
      >
        L1
      </Button>,
      <Button
        key="r1"
        size="small"
        danger
        icon={<CloseOutlined />}
        onClick={handleReject}
      >
        Reject
      </Button>,
    );
  }
  if (req.status === 'PENDING_L2' && isApprover) {
    btns.push(
      <Button
        key="al2"
        size="small"
        type="primary"
        icon={<CheckOutlined />}
        loading={approveL2Mut.isPending}
        onClick={() => approveL2Mut.mutate()}
        style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}
      >
        L2 (final)
      </Button>,
      <Button
        key="r2"
        size="small"
        danger
        icon={<CloseOutlined />}
        onClick={handleReject}
      >
        Reject
      </Button>,
    );
  }
  if (['PENDING_L1', 'PENDING_L2', 'APPROVED'].includes(req.status)) {
    btns.push(
      <Button
        key="c"
        size="small"
        icon={<StopOutlined />}
        loading={cancelMut.isPending}
        onClick={() => cancelMut.mutate()}
      >
        Cancel
      </Button>,
    );
  }

  return <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>{btns}</div>;
}

// ─── Row ─────────────────────────────────────────────────────────

function LeaveRow({
  req,
  onAction,
  isApprover,
  currentUserId,
}: {
  req: LeaveRequestListItem;
  onAction: () => void;
  isApprover: boolean;
  currentUserId: string | undefined;
}) {
  const badge = leaveStatusColor(req.status);
  const typeColor = leaveTypeColor(req.leave_type_code);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1.5fr 1fr 1.4fr 0.6fr 1fr 1.6fr',
        gap: 12,
        padding: '14px 20px',
        borderBottom: '1px solid var(--ide-border2)',
        fontSize: 13,
        alignItems: 'center',
      }}
    >
      <div>
        <div style={{ fontWeight: 700, color: 'var(--ide-ink)' }}>{req.employee_name || '—'}</div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--ide-ink3)',
            fontFamily: 'var(--ide-font-mono)',
          }}
        >
          {req.employee_nik}
        </div>
      </div>
      <div>
        <span
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: typeColor,
            padding: '2px 8px',
            background: 'var(--ide-bg)',
            borderRadius: 4,
          }}
        >
          {req.leave_type_code}
        </span>
        <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginTop: 2 }}>
          {req.leave_type_name}
        </div>
      </div>
      <div style={{ fontSize: 12 }}>
        <div style={{ color: 'var(--ide-ink)' }}>{formatDate(req.start_date)}</div>
        <div style={{ color: 'var(--ide-ink3)', fontSize: 11 }}>→ {formatDate(req.end_date)}</div>
      </div>
      <div
        style={{
          fontSize: 16,
          fontWeight: 800,
          color: 'var(--ide-ink)',
          fontFamily: 'var(--ide-font-mono)',
          textAlign: 'center',
        }}
      >
        {req.days_count}
        <div
          style={{
            fontSize: 9,
            color: 'var(--ide-ink3)',
            fontWeight: 500,
            textTransform: 'uppercase',
          }}
        >
          days
        </div>
      </div>
      <div>
        <span className={`ide-tag ${badge.className}`}>{badge.label}</span>
      </div>
      <RowActions
        req={req}
        onAction={onAction}
        isApprover={isApprover}
        currentUserId={currentUserId}
      />
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function LeaveListPage() {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [statusFilter, setStatusFilter] = useState<LeaveRequestStatus | undefined>(undefined);
  const [employeeFilter, setEmployeeFilter] = useState<string | undefined>(undefined);
  const [createOpen, setCreateOpen] = useState(false);

  const isApprover =
    user?.roles.some((r) =>
      ['DIREKTUR_UTAMA', 'WAKIL_DIREKTUR_UTAMA', 'C_LEVEL', 'GM', 'MANAGER'].includes(r.code),
    ) ?? false;

  const empQuery = useQuery({
    queryKey: ['employees-leave-filter'],
    queryFn: () => listEmployees({ page_size: 200 }),
  });

  const reqQuery = useQuery({
    queryKey: ['leave-requests', statusFilter, employeeFilter],
    queryFn: () =>
      listLeaveRequests({
        status: statusFilter,
        employee_id: employeeFilter,
        page_size: 100,
      }),
  });

  // Balance summary kalau ada employee filter
  const balanceQuery = useQuery({
    queryKey: ['leave-balances', employeeFilter],
    queryFn: () => getEmployeeBalances(employeeFilter!),
    enabled: !!employeeFilter,
  });

  const items = reqQuery.data?.items || [];
  const pending = items.filter((r) =>
    ['PENDING_L1', 'PENDING_L2'].includes(r.status),
  ).length;
  const approved = items.filter((r) => r.status === 'APPROVED').length;
  const rejected = items.filter((r) => r.status === 'REJECTED').length;

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['leave-requests'] });
    queryClient.invalidateQueries({ queryKey: ['leave-balances'] });
  };

  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 18,
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
            Leave Requests
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
            Cuti karyawan dengan saldo tracking + 2-layer approval (Supervisor → GM/HR).
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)', fontWeight: 600 }}
        >
          Submit Leave Request
        </Button>
      </div>

      {/* Balance summary (kalau employee filter aktif) */}
      {balanceQuery.data && (
        <div style={{ marginBottom: 18 }}>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--ide-ink3)',
              textTransform: 'uppercase',
              letterSpacing: 0.5,
              marginBottom: 8,
            }}
          >
            Leave Balance — {balanceQuery.data.employee_name} ({balanceQuery.data.year})
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 10,
            }}
          >
            {balanceQuery.data.balances.map((b) => (
              <BalanceCard key={b.id} balance={b} />
            ))}
          </div>
        </div>
      )}

      {/* KPIs */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div className="ide-kpi">
          <div className="ide-kpi-val">{items.length}</div>
          <div className="ide-kpi-lbl">Total Requests</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-orange)' }}>
            {pending}
          </div>
          <div className="ide-kpi-lbl">Pending Approval</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-green)' }}>
            {approved}
          </div>
          <div className="ide-kpi-lbl">Approved</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-red)' }}>
            {rejected}
          </div>
          <div className="ide-kpi-lbl">Rejected</div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Select
          placeholder="All Karyawan"
          style={{ width: 280 }}
          allowClear
          showSearch
          optionFilterProp="label"
          value={employeeFilter}
          onChange={(v) => setEmployeeFilter(v)}
          options={(empQuery.data?.items || []).map((e) => ({
            value: e.id,
            label: `${e.nik} · ${e.full_name}`,
          }))}
        />
        <Select
          placeholder="All Status"
          style={{ width: 200 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as LeaveRequestStatus)}
          options={[
            { value: 'PENDING_L1', label: 'Pending L1' },
            { value: 'PENDING_L2', label: 'Pending L2' },
            { value: 'APPROVED', label: 'Approved' },
            { value: 'REJECTED', label: 'Rejected' },
            { value: 'CANCELLED', label: 'Cancelled' },
          ]}
        />
        {isApprover && (
          <Alert
            type="info"
            message="Anda dapat approve/reject sebagai supervisor"
            showIcon
            style={{ marginLeft: 'auto' }}
          />
        )}
      </div>

      {/* Table */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.5fr 1fr 1.4fr 0.6fr 1fr 1.6fr',
            gap: 12,
            padding: '12px 20px',
            background: 'var(--ide-bg)',
            borderBottom: '1px solid var(--ide-border)',
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
          }}
        >
          <div>Karyawan</div>
          <div>Jenis</div>
          <div>Period</div>
          <div style={{ textAlign: 'center' }}>Days</div>
          <div>Status</div>
          <div style={{ textAlign: 'right' }}>Actions</div>
        </div>

        {reqQuery.isLoading && (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        )}

        {reqQuery.data && items.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span style={{ color: 'var(--ide-ink2)' }}>Belum ada leave request</span>
            }
            style={{ padding: '40px 20px' }}
          />
        )}

        {items.map((r) => (
          <LeaveRow
            key={r.id}
            req={r}
            onAction={refresh}
            isApprover={isApprover}
            currentUserId={user?.id}
          />
        ))}
      </div>

      <CreateLeaveModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={refresh}
      />
    </div>
  );
}
