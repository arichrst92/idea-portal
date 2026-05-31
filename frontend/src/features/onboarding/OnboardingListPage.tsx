/**
 * Onboarding Assignments List — TSK-016.
 * Visual reference: GUI html/IDEA_Onboarding.html (progress bars + cards).
 */

import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Empty, Form, Input, Modal, Select, Spin} from 'antd';
import { message } from '@/lib/notify';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { listEmployees } from '@/api/organization';
import {
  assignmentStatusColor,
  createAssignment,
  listAssignments,
  listTemplates,
  type AssignmentListItem,
  type AssignmentStatus,
} from '@/api/onboarding';

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

function getInitials(name: string | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function ProgressCard({
  item,
  onClick,
}: {
  item: AssignmentListItem;
  onClick: () => void;
}) {
  const statusTag = assignmentStatusColor(item.status);
  const progressColor =
    item.progress_percent >= 100
      ? 'var(--ide-green)'
      : item.progress_percent >= 50
        ? 'var(--ide-blue)'
        : 'var(--ide-orange)';

  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--ide-surface)',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-r)',
        padding: '18px 22px',
        cursor: 'pointer',
        transition: 'all 0.15s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = 'var(--ide-blue)';
        e.currentTarget.style.boxShadow = 'var(--ide-shadow-sm)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--ide-border)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 12 }}>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--ide-blue), var(--ide-teal))',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 14,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {getInitials(item.employee_name)}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ide-ink)' }}>
            {item.employee_name || '—'}
          </div>
          <div
            style={{
              fontSize: 11,
              color: 'var(--ide-ink3)',
              fontFamily: 'var(--ide-font-mono)',
              marginTop: 2,
            }}
          >
            {item.employee_nik || '—'} · {item.employee_department || 'No dept'}
          </div>
        </div>
        <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
      </div>

      <div
        style={{
          fontSize: 11,
          color: 'var(--ide-ink2)',
          fontWeight: 600,
          marginBottom: 8,
        }}
      >
        {item.template_name || 'Template'}
      </div>

      {/* Progress bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 4,
        }}
      >
        <span style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>
          {item.completed_tasks} / {item.total_tasks} tasks
        </span>
        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color: progressColor,
            fontFamily: 'var(--ide-font-mono)',
          }}
        >
          {item.progress_percent}%
        </span>
      </div>
      <div style={{ height: 6, background: 'var(--ide-bg)', borderRadius: 3, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${item.progress_percent}%`,
            background: progressColor,
            transition: 'width 0.3s',
          }}
        />
      </div>

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 10,
          color: 'var(--ide-ink3)',
          marginTop: 10,
        }}
      >
        <span>Started: {formatDate(item.started_at)}</span>
        <span>Target: {formatDate(item.target_completion_date)}</span>
      </div>
    </div>
  );
}

// ─── Create Assignment Modal ─────────────────────────────────────

function AssignModal({
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
    queryKey: ['employees-for-assign'],
    queryFn: () => listEmployees({ page_size: 200 }),
    enabled: open,
  });
  const tmplQuery = useQuery({
    queryKey: ['templates-active'],
    queryFn: () => listTemplates({ is_active: true }),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: createAssignment,
    onSuccess: () => {
      message.success('Onboarding assignment dibuat');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail?.message || 'Gagal create assignment');
    },
  });

  return (
    <Modal
      title="Assign Onboarding"
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
              template_id: v.template_id,
              notes: v.notes,
            });
          }}
        >
          Assign
        </Button>,
      ]}
      destroyOnHidden
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
              value: e.id, // employees.id UUID untuk FK ke onboarding_assignments
              label: `${e.nik} · ${e.full_name} (${e.department_name || 'no dept'})`,
            }))}
          />
        </Form.Item>
        <Form.Item
          label="Template"
          name="template_id"
          rules={[{ required: true, message: 'Pilih template' }]}
        >
          <Select
            placeholder="Pilih template onboarding"
            loading={tmplQuery.isLoading}
            options={(tmplQuery.data || []).map((t) => ({
              value: t.id,
              label: `${t.name} (${t.task_count} tasks${t.department_name ? ` · ${t.department_name}` : ''})`,
            }))}
          />
        </Form.Item>
        <Form.Item label="Catatan (opsional)" name="notes">
          <Input.TextArea rows={3} placeholder="Catatan untuk HR/Manager..." />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function OnboardingListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<AssignmentStatus | undefined>(undefined);
  const [assignOpen, setAssignOpen] = useState(false);

  const query = useQuery({
    queryKey: ['onboarding-assignments', statusFilter],
    queryFn: () => listAssignments({ status: statusFilter, page_size: 100 }),
  });

  const items = query.data?.items || [];
  const filtered = search
    ? items.filter(
        (a) =>
          (a.employee_name || '').toLowerCase().includes(search.toLowerCase()) ||
          (a.employee_nik || '').toLowerCase().includes(search.toLowerCase()) ||
          (a.template_name || '').toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  // KPI
  const inProgress = items.filter((a) => a.status === 'IN_PROGRESS').length;
  const completed = items.filter((a) => a.status === 'COMPLETED').length;
  const overdue = items.filter(
    (a) =>
      a.status !== 'COMPLETED' &&
      a.target_completion_date !== null &&
      new Date(a.target_completion_date) < new Date(),
  ).length;
  const avgProgress =
    items.length > 0
      ? Math.round(items.reduce((acc, a) => acc + a.progress_percent, 0) / items.length)
      : 0;

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
            Onboarding
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
            Progress checklist setiap karyawan baru.
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setAssignOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)', fontWeight: 600 }}
        >
          Assign Onboarding
        </Button>
      </div>

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
          <div className="ide-kpi-lbl">Total Assignments</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-blue)' }}>
            {inProgress}
          </div>
          <div className="ide-kpi-lbl">In Progress</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-green)' }}>
            {completed}
          </div>
          <div className="ide-kpi-lbl">Completed</div>
        </div>
        <div className="ide-kpi">
          <div
            className="ide-kpi-val"
            style={{ color: overdue > 0 ? 'var(--ide-red)' : 'var(--ide-ink3)' }}
          >
            {overdue}
          </div>
          <div className="ide-kpi-lbl">Overdue</div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--ide-ink3)' }} />}
          placeholder="Cari NIK / nama / template..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="Semua Status"
          style={{ width: 180 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as AssignmentStatus)}
          options={[
            { value: 'NOT_STARTED', label: 'Not Started' },
            { value: 'IN_PROGRESS', label: 'In Progress' },
            { value: 'COMPLETED', label: 'Completed' },
            { value: 'CANCELLED', label: 'Cancelled' },
          ]}
        />
        <div style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--ide-ink3)' }}>
          Avg Progress:{' '}
          <strong style={{ fontFamily: 'var(--ide-font-mono)' }}>{avgProgress}%</strong>
        </div>
      </div>

      {/* Cards grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
          gap: 14,
        }}
      >
        {query.isLoading && (
          <div style={{ gridColumn: '1 / -1', padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        )}

        {query.data && filtered.length === 0 && (
          <div style={{ gridColumn: '1 / -1' }}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span style={{ color: 'var(--ide-ink2)' }}>
                  {search ? `Tidak ada match "${search}"` : 'Belum ada onboarding assignment'}
                </span>
              }
            />
          </div>
        )}

        {filtered.map((item) => (
          <ProgressCard
            key={item.id}
            item={item}
            onClick={() => navigate(`/onboarding/${item.id}`)}
          />
        ))}
      </div>

      <AssignModal
        open={assignOpen}
        onClose={() => setAssignOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['onboarding-assignments'] })}
      />
    </div>
  );
}
