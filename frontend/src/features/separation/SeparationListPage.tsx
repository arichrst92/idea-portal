/**
 * Separation List Page — TSK-017.
 * Visual reference: GUI html/IDEA_layoff_resign.html
 */

import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, DatePicker, Empty, Form, Input, InputNumber, Modal, Select, Spin, message } from 'antd';
import type { AxiosError } from 'axios';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { listEmployees } from '@/api/organization';
import {
  createSeparation,
  listSeparations,
  SEPARATION_TYPE_META,
  separationStatusColor,
  type SeparationListItem,
  type SeparationStatus,
  type SeparationType,
} from '@/api/separation';

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

function getInitials(name: string | null): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function SeparationRow({ item, onClick }: { item: SeparationListItem; onClick: () => void }) {
  const typeMeta = SEPARATION_TYPE_META[item.separation_type];
  const statusTag = separationStatusColor(item.status);
  const daysUntilEffective = Math.ceil(
    (new Date(item.effective_date).getTime() - Date.now()) / (1000 * 60 * 60 * 24),
  );

  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '2fr 1.2fr 1fr 1.2fr 1fr',
        gap: 14,
        padding: '14px 20px',
        borderBottom: '1px solid var(--ide-border2)',
        fontSize: 13,
        alignItems: 'center',
        cursor: 'pointer',
        transition: 'background 0.12s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--ide-bg)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--ide-blue), var(--ide-purple))',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 11,
            fontWeight: 700,
            flexShrink: 0,
          }}
        >
          {getInitials(item.employee_name)}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ide-ink)' }}>
            {item.employee_name || '—'}
          </div>
          <div
            style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'var(--ide-font-mono)' }}
          >
            {item.employee_nik || '—'} · {item.employee_department || 'No dept'}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 14 }}>{typeMeta.icon}</span>
        <span style={{ fontSize: 12, fontWeight: 600, color: typeMeta.color }}>
          {typeMeta.label}
        </span>
      </div>

      <div>
        <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
      </div>

      <div style={{ fontSize: 12, color: 'var(--ide-ink2)' }}>
        {formatDate(item.effective_date)}
        {daysUntilEffective > 0 && item.status !== 'EXECUTED' && (
          <div style={{ fontSize: 10, color: 'var(--ide-ink3)' }}>{daysUntilEffective}d lagi</div>
        )}
      </div>

      <div style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'var(--ide-font-mono)' }}>
        by {item.initiated_by_nik || '—'}
      </div>
    </div>
  );
}

// ─── Initiate Modal ──────────────────────────────────────────────

function InitiateModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const [serverError, setServerError] = useState<string | null>(null);

  const empQuery = useQuery({
    queryKey: ['employees-for-separation'],
    queryFn: () => listEmployees({ page_size: 200 }),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: createSeparation,
    onSuccess: () => {
      message.success('Separation request created (auto-submitted ke L1 approval)');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: AxiosError<{ detail?: { message?: string; code?: string } }>) => {
      setServerError(err.response?.data?.detail?.message || 'Gagal create separation');
    },
  });

  const handleSubmit = async () => {
    try {
      const v = await form.validateFields();
      setServerError(null);
      mutation.mutate({
        employee_id: v.employee_id,
        separation_type: v.separation_type,
        reason: v.reason,
        effective_date: dayjs(v.effective_date).format('YYYY-MM-DD'),
        notice_period_days: v.notice_period_days || 30,
        severance_amount: v.severance_amount ? String(v.severance_amount) : undefined,
      });
    } catch {
      // form validation error
    }
  };

  return (
    <Modal
      title="Initiate Separation"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button key="s" type="primary" loading={mutation.isPending} onClick={handleSubmit}>
          Submit untuk Approval
        </Button>,
      ]}
      destroyOnClose
      width={560}
    >
      {serverError && (
        <div
          style={{
            marginBottom: 14,
            padding: '8px 12px',
            background: 'var(--ide-red-soft)',
            color: 'var(--ide-red)',
            borderRadius: 'var(--ide-rs)',
            fontSize: 12,
            fontWeight: 600,
          }}
        >
          {serverError}
        </div>
      )}

      <Form form={form} layout="vertical" initialValues={{ notice_period_days: 30 }}>
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
              label: `${e.nik} · ${e.full_name} (${e.department_name || 'no dept'})`,
            }))}
          />
        </Form.Item>

        <Form.Item
          label="Tipe Separation"
          name="separation_type"
          rules={[{ required: true, message: 'Pilih tipe' }]}
        >
          <Select
            placeholder="Pilih tipe"
            options={[
              { value: 'RESIGNATION', label: '👋 Resignation' },
              { value: 'LAYOFF', label: '📉 Layoff' },
              { value: 'TERMINATION', label: '⛔ Termination (SP3)' },
              { value: 'END_OF_CONTRACT', label: '📄 End of Contract' },
              { value: 'RETIREMENT', label: '🎉 Retirement' },
            ]}
          />
        </Form.Item>

        <Form.Item
          label="Alasan"
          name="reason"
          rules={[
            { required: true, message: 'Wajib diisi' },
            { min: 10, message: 'Min 10 karakter' },
            { max: 2000, message: 'Max 2000 karakter' },
          ]}
        >
          <TextArea rows={4} placeholder="Jelaskan alasan separation..." />
        </Form.Item>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item
            label="Effective Date (Last Working Day)"
            name="effective_date"
            rules={[{ required: true, message: 'Wajib diisi' }]}
          >
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item label="Notice Period (hari)" name="notice_period_days">
            <InputNumber min={0} max={365} style={{ width: '100%' }} />
          </Form.Item>
        </div>

        <Form.Item label="Severance Amount (IDR, opsional)" name="severance_amount">
          <InputNumber
            min={0}
            style={{ width: '100%', fontFamily: 'var(--ide-font-mono)' }}
            formatter={(v) => (v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : '')}
            parser={(v) => (v ? Number(v.replace(/[^0-9]/g, '')) : 0)}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function SeparationListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<SeparationStatus | undefined>(undefined);
  const [typeFilter, setTypeFilter] = useState<SeparationType | undefined>(undefined);
  const [initiateOpen, setInitiateOpen] = useState(false);

  const query = useQuery({
    queryKey: ['separations', statusFilter, typeFilter],
    queryFn: () =>
      listSeparations({
        status: statusFilter,
        separation_type: typeFilter,
        page_size: 100,
      }),
  });

  const items = query.data?.items || [];
  const filtered = search
    ? items.filter(
        (s) =>
          (s.employee_name || '').toLowerCase().includes(search.toLowerCase()) ||
          (s.employee_nik || '').toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  // KPI counts
  const pending = items.filter(
    (s) => s.status === 'PENDING_APPROVAL_L1' || s.status === 'PENDING_APPROVAL_L2',
  ).length;
  const approved = items.filter((s) => s.status === 'APPROVED').length;
  const executed = items.filter((s) => s.status === 'EXECUTED').length;
  const resignationCount = items.filter((s) => s.separation_type === 'RESIGNATION').length;
  const layoffCount = items.filter((s) => s.separation_type === 'LAYOFF').length;
  const terminationCount = items.filter((s) => s.separation_type === 'TERMINATION').length;

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
            Separation
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
            Resignation, Layoff, Termination, End of Contract — semua proses pemberhentian.
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setInitiateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)', fontWeight: 600 }}
        >
          Initiate Separation
        </Button>
      </div>

      {/* KPIs */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-orange)' }}>
            {pending}
          </div>
          <div className="ide-kpi-lbl">Pending Approval</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-blue)' }}>
            {approved}
          </div>
          <div className="ide-kpi-lbl">Approved (siap eksekusi)</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-green)' }}>
            {executed}
          </div>
          <div className="ide-kpi-lbl">Executed</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val">{resignationCount}</div>
          <div className="ide-kpi-lbl">Resignation</div>
        </div>
        <div className="ide-kpi">
          <div
            className="ide-kpi-val"
            style={{ color: terminationCount > 0 ? 'var(--ide-red)' : 'var(--ide-ink3)' }}
          >
            {layoffCount + terminationCount}
          </div>
          <div className="ide-kpi-lbl">Layoff + Termination</div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--ide-ink3)' }} />}
          placeholder="Cari NIK / nama..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="Semua Tipe"
          style={{ width: 180 }}
          allowClear
          value={typeFilter}
          onChange={(v) => setTypeFilter(v as SeparationType)}
          options={[
            { value: 'RESIGNATION', label: 'Resignation' },
            { value: 'LAYOFF', label: 'Layoff' },
            { value: 'TERMINATION', label: 'Termination' },
            { value: 'END_OF_CONTRACT', label: 'End of Contract' },
            { value: 'RETIREMENT', label: 'Retirement' },
          ]}
        />
        <Select
          placeholder="Semua Status"
          style={{ width: 200 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as SeparationStatus)}
          options={[
            { value: 'DRAFT', label: 'Draft' },
            { value: 'PENDING_APPROVAL_L1', label: 'Pending L1 Approval' },
            { value: 'PENDING_APPROVAL_L2', label: 'Pending L2 Approval' },
            { value: 'APPROVED', label: 'Approved' },
            { value: 'EXECUTED', label: 'Executed' },
            { value: 'REJECTED', label: 'Rejected' },
            { value: 'CANCELLED', label: 'Cancelled' },
          ]}
        />
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
            gridTemplateColumns: '2fr 1.2fr 1fr 1.2fr 1fr',
            gap: 14,
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
          <div>Tipe</div>
          <div>Status</div>
          <div>Effective Date</div>
          <div>Initiated By</div>
        </div>

        {query.isLoading && (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        )}

        {query.data && filtered.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span style={{ color: 'var(--ide-ink2)' }}>
                {search ? `Tidak ada match "${search}"` : 'Belum ada separation'}
              </span>
            }
            style={{ padding: '40px 20px' }}
          />
        )}

        {filtered.map((item) => (
          <SeparationRow key={item.id} item={item} onClick={() => navigate(`/separations/${item.id}`)} />
        ))}
      </div>

      <InitiateModal
        open={initiateOpen}
        onClose={() => setInitiateOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['separations'] })}
      />
    </div>
  );
}
