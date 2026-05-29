/**
 * Projects List Page — TSK-022.
 */

import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  DatePicker,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Select,
  Spin,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  createProject,
  listProjects,
  projectStatusColor,
  projectTypeColor,
  type ProjectListItem,
  type ProjectStatus,
  type ProjectType,
} from '@/api/projects';

const { TextArea } = Input;

function formatDate(value: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

function formatIDR(value: string | null): string {
  if (!value) return '—';
  const n = parseFloat(value);
  if (!isFinite(n)) return value;
  return `Rp ${n.toLocaleString('id-ID')}`;
}

// ─── Create Modal ────────────────────────────────────────────────

function CreateProjectModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const mutation = useMutation({
    mutationFn: createProject,
    onSuccess: () => {
      message.success('Project dibuat sebagai DRAFT');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal create project'),
  });

  return (
    <Modal
      title="Create Project"
      open={open}
      onCancel={onClose}
      width={560}
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
              code: v.code,
              name: v.name,
              type: v.type,
              description: v.description,
              start_date: v.start_date ? dayjs(v.start_date).format('YYYY-MM-DD') : undefined,
              end_date: v.end_date ? dayjs(v.end_date).format('YYYY-MM-DD') : undefined,
              contract_value: v.contract_value ? String(v.contract_value) : undefined,
              currency: v.currency || 'IDR',
            });
          }}
        >
          Create
        </Button>,
      ]}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={{ type: 'CLIENT', currency: 'IDR' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 12 }}>
          <Form.Item
            label="Code"
            name="code"
            rules={[{ required: true, min: 2 }]}
          >
            <Input placeholder="PRJ-001" style={{ fontFamily: 'var(--ide-font-mono)' }} />
          </Form.Item>
          <Form.Item label="Project Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="E-commerce Platform v2" />
          </Form.Item>
        </div>
        <Form.Item label="Type" name="type" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'CLIENT', label: 'Client (Revenue)' },
              { value: 'INTERNAL', label: 'Internal (OPEX/CAPEX)' },
              { value: 'RND', label: 'R&D' },
            ]}
          />
        </Form.Item>
        <Form.Item label="Description" name="description">
          <TextArea rows={3} placeholder="Scope, objectives, deliverables..." />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="Start Date" name="start_date">
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item label="End Date" name="end_date">
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
        </div>
        <Form.Item label="Contract Value (IDR)" name="contract_value">
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

// ─── Row ─────────────────────────────────────────────────────────

function ProjectRow({ p, onClick }: { p: ProjectListItem; onClick: () => void }) {
  const typeTag = projectTypeColor(p.type);
  const statusTag = projectStatusColor(p.status);
  const progress = p.overall_progress_pct ? Number(p.overall_progress_pct) : 0;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '0.6fr 2fr 0.8fr 0.8fr 1.2fr 1.2fr 0.8fr',
        gap: 12,
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
      <div
        style={{
          fontFamily: 'var(--ide-font-mono)',
          fontSize: 12,
          fontWeight: 700,
          color: 'var(--ide-blue)',
        }}
      >
        {p.code}
      </div>
      <div>
        <div style={{ fontWeight: 700, color: 'var(--ide-ink)' }}>{p.name}</div>
        {p.client_name && (
          <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>
            Client: {p.client_name}
          </div>
        )}
      </div>
      <div>
        <span className={`ide-tag ${typeTag.className}`}>{typeTag.label}</span>
      </div>
      <div>
        <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
      </div>
      <div>
        <Progress percent={Math.round(progress)} size="small" />
        <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginTop: 2 }}>
          {p.member_count} member{p.member_count !== 1 ? 's' : ''}
        </div>
      </div>
      <div style={{ fontSize: 11, color: 'var(--ide-ink2)' }}>
        {formatDate(p.start_date)}
        <div style={{ color: 'var(--ide-ink3)' }}>→ {formatDate(p.end_date)}</div>
      </div>
      <div
        style={{
          textAlign: 'right',
          fontFamily: 'var(--ide-font-mono)',
          fontSize: 11,
          color: 'var(--ide-ink)',
        }}
      >
        {formatIDR(p.contract_value)}
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function ProjectsListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<ProjectType | undefined>();
  const [statusFilter, setStatusFilter] = useState<ProjectStatus | undefined>();
  const [createOpen, setCreateOpen] = useState(false);

  const query = useQuery({
    queryKey: ['projects', typeFilter, statusFilter],
    queryFn: () =>
      listProjects({
        type: typeFilter,
        status: statusFilter,
        page_size: 100,
      }),
  });

  const items = query.data?.items || [];
  const filtered = search
    ? items.filter(
        (p) =>
          p.name.toLowerCase().includes(search.toLowerCase()) ||
          p.code.toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  // KPI
  const active = items.filter((p) => p.status === 'ACTIVE').length;
  const draft = items.filter((p) => p.status === 'DRAFT').length;
  const completed = items.filter((p) => p.status === 'COMPLETED').length;
  const totalValue = items.reduce(
    (acc, p) => acc + (p.contract_value ? parseFloat(p.contract_value) : 0),
    0,
  );

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
            Projects
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
            Client / Internal / R&D dengan milestone tracking. Invoice di Finance.
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)', fontWeight: 600 }}
        >
          Create Project
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
          <div className="ide-kpi-lbl">Total Projects</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-green)' }}>
            {active}
          </div>
          <div className="ide-kpi-lbl">Active</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-ink3)' }}>
            {draft} / {completed}
          </div>
          <div className="ide-kpi-lbl">Draft / Completed</div>
        </div>
        <div className="ide-kpi">
          <div
            className="ide-kpi-val"
            style={{ color: 'var(--ide-blue)', fontSize: 16 }}
          >
            {totalValue > 0 ? `Rp ${(totalValue / 1_000_000_000).toFixed(1)}B` : '—'}
          </div>
          <div className="ide-kpi-lbl">Total Contract Value</div>
        </div>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--ide-ink3)' }} />}
          placeholder="Cari code / nama project..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="All Types"
          style={{ width: 160 }}
          allowClear
          value={typeFilter}
          onChange={(v) => setTypeFilter(v as ProjectType)}
          options={[
            { value: 'CLIENT', label: 'Client' },
            { value: 'INTERNAL', label: 'Internal' },
            { value: 'RND', label: 'R&D' },
          ]}
        />
        <Select
          placeholder="All Status"
          style={{ width: 180 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as ProjectStatus)}
          options={[
            { value: 'DRAFT', label: 'Draft' },
            { value: 'ACTIVE', label: 'Active' },
            { value: 'ON_HOLD', label: 'On Hold' },
            { value: 'COMPLETED', label: 'Completed' },
            { value: 'TERMINATED', label: 'Terminated' },
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
            gridTemplateColumns: '0.6fr 2fr 0.8fr 0.8fr 1.2fr 1.2fr 0.8fr',
            gap: 12,
            padding: '12px 20px',
            background: 'var(--ide-bg)',
            borderBottom: '1px solid var(--ide-border)',
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: 0.8,
          }}
        >
          <div>Code</div>
          <div>Project</div>
          <div>Type</div>
          <div>Status</div>
          <div>Progress</div>
          <div>Timeline</div>
          <div style={{ textAlign: 'right' }}>Contract</div>
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
                {search ? `Tidak ada match "${search}"` : 'Belum ada project'}
              </span>
            }
            style={{ padding: '40px 20px' }}
          />
        )}

        {filtered.map((p) => (
          <ProjectRow key={p.id} p={p} onClick={() => navigate(`/projects/${p.id}`)} />
        ))}
      </div>

      <CreateProjectModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['projects'] })}
      />
    </div>
  );
}
