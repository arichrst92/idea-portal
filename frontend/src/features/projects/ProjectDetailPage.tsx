/**
 * Project Detail Page — TSK-022 (TSK-022C: tab Invoices dihapus, pindah ke Finance).
 * Tabs: Overview, Milestones, Tasks (kanban), Members.
 */

import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  ExclamationCircleOutlined,
  PlusOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
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
  Tabs,
  Tag,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { listEmployees } from '@/api/organization';
import {
  activateProject,
  closeProject,
  createMilestone,
  createTask,
  getProject,
  listMembers,
  listMilestones,
  listTasks,
  priorityColor,
  projectStatusColor,
  projectTypeColor,
  taskStatusColor,
  TASK_STATUSES,
  updateMilestone,
  updateTask,
  type Task,
  type TaskStatus,
} from '@/api/projects';
import { useAuthStore } from '@/store/auth';

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

// ─── MILESTONES TAB ─────────────────────────────────────────────

function MilestonesTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const query = useQuery({
    queryKey: ['milestones', projectId],
    queryFn: () => listMilestones(projectId),
  });

  const mutation = useMutation({
    mutationFn: ({ id, pct }: { id: string; pct: number }) =>
      updateMilestone(id, { progress_pct: pct, completed_at: pct === 100 ? dayjs().format('YYYY-MM-DD') : undefined }),
    onSuccess: () => {
      message.success('Milestone updated');
      queryClient.invalidateQueries({ queryKey: ['milestones', projectId] });
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
    },
  });

  const createMut = useMutation({
    mutationFn: (d: { name: string; target_date: string }) => createMilestone(projectId, d),
    onSuccess: () => {
      message.success('Milestone created');
      queryClient.invalidateQueries({ queryKey: ['milestones', projectId] });
    },
  });

  const milestones = query.data || [];

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Add Milestone
        </Button>
      </div>

      {query.isLoading && <Spin />}
      {milestones.length === 0 && <Empty description="Belum ada milestone" />}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {milestones.map((m) => {
          const pct = Number(m.progress_pct);
          return (
            <div
              key={m.id}
              style={{
                background: 'var(--ide-surface)',
                border: `1px solid ${m.is_overdue ? 'var(--ide-red)' : 'var(--ide-border)'}`,
                borderRadius: 'var(--ide-rm)',
                padding: 14,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: 8,
                }}
              >
                <div>
                  <div style={{ fontWeight: 700, fontSize: 14 }}>
                    {m.completed_at && (
                      <CheckCircleFilled
                        style={{ color: 'var(--ide-green)', marginRight: 6 }}
                      />
                    )}
                    {m.name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ide-ink3)', marginTop: 2 }}>
                    Target: {formatDate(m.target_date)}
                    {m.completed_at && ` · Completed ${formatDate(m.completed_at)}`}
                    {m.is_overdue && (
                      <span style={{ color: 'var(--ide-red)', fontWeight: 700 }}>
                        {' '}
                        · ⚠ OVERDUE
                      </span>
                    )}
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: 'var(--ide-font-mono)',
                    fontSize: 18,
                    fontWeight: 800,
                    color: pct >= 100 ? 'var(--ide-green)' : 'var(--ide-blue)',
                  }}
                >
                  {pct.toFixed(0)}%
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Progress percent={pct} size="small" style={{ flex: 1 }} />
                <InputNumber
                  size="small"
                  min={0}
                  max={100}
                  value={pct}
                  onChange={(v) => v !== null && mutation.mutate({ id: m.id, pct: v })}
                  style={{ width: 80 }}
                />
              </div>
            </div>
          );
        })}
      </div>

      <Modal
        title="Create Milestone"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        destroyOnClose
        onOk={async () => {
          const v = await (createOpen ? document.querySelector('#ms-form') : null);
          // Use form ref instead
        }}
        footer={null}
      >
        <Form
          layout="vertical"
          onFinish={(v) => {
            createMut.mutate({
              name: v.name,
              target_date: dayjs(v.target_date).format('YYYY-MM-DD'),
            });
            setCreateOpen(false);
          }}
        >
          <Form.Item label="Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="Phase 1 — Architecture design" />
          </Form.Item>
          <Form.Item label="Target Date" name="target_date" rules={[{ required: true }]}>
            <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={createMut.isPending}>
              Create
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

// ─── TASKS KANBAN ────────────────────────────────────────────────

function TaskCard({ task, onUpdate }: { task: Task; onUpdate: () => void }) {
  const color = taskStatusColor(task.status);
  const prio = priorityColor(task.priority);
  const updateMut = useMutation({
    mutationFn: (status: TaskStatus) => updateTask(task.id, { status }),
    onSuccess: onUpdate,
  });

  return (
    <div
      style={{
        background: 'var(--ide-surface)',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-rs)',
        padding: 10,
        marginBottom: 8,
        cursor: 'pointer',
        transition: 'all 0.12s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = color;
        e.currentTarget.style.boxShadow = 'var(--ide-shadow-sm)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--ide-border)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{task.title}</div>
      {task.assignee_name && (
        <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginBottom: 6 }}>
          {task.assignee_name}
        </div>
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span
          style={{
            fontSize: 9,
            fontWeight: 700,
            padding: '1px 6px',
            borderRadius: 4,
            color: '#fff',
            background: prio,
          }}
        >
          {task.priority}
        </span>
        <Select
          size="small"
          value={task.status}
          style={{ width: 110 }}
          onChange={(v) => updateMut.mutate(v)}
          options={TASK_STATUSES.map((s) => ({ value: s, label: s }))}
        />
      </div>
    </div>
  );
}

function TasksTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const query = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => listTasks(projectId),
  });
  const empQuery = useQuery({
    queryKey: ['emp-tasks'],
    queryFn: () => listEmployees({ page_size: 200 }),
  });

  const createMut = useMutation({
    mutationFn: (d: any) => createTask(projectId, d),
    onSuccess: () => {
      message.success('Task created');
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] });
    },
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['tasks', projectId] });
  const tasks = query.data || [];

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Add Task
        </Button>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, minmax(180px, 1fr))',
          gap: 10,
          overflowX: 'auto',
        }}
      >
        {TASK_STATUSES.map((s) => {
          const bucket = tasks.filter((t) => t.status === s);
          const color = taskStatusColor(s);
          return (
            <div
              key={s}
              style={{
                background: 'var(--ide-bg)',
                borderRadius: 'var(--ide-rm)',
                padding: 10,
                minHeight: 200,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  marginBottom: 10,
                  fontSize: 11,
                  fontWeight: 700,
                  color,
                  textTransform: 'uppercase',
                }}
              >
                <span>{s.replace(/_/g, ' ')}</span>
                <span>{bucket.length}</span>
              </div>
              {bucket.map((t) => (
                <TaskCard key={t.id} task={t} onUpdate={refresh} />
              ))}
            </div>
          );
        })}
      </div>

      <Modal
        title="Create Task"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form
          layout="vertical"
          onFinish={(v) => {
            createMut.mutate({
              title: v.title,
              description: v.description,
              assignee_id: v.assignee_id,
              status: v.status || 'BACKLOG',
              priority: v.priority || 'MEDIUM',
              due_date: v.due_date ? dayjs(v.due_date).format('YYYY-MM-DD') : undefined,
            });
            setCreateOpen(false);
          }}
          initialValues={{ status: 'BACKLOG', priority: 'MEDIUM' }}
        >
          <Form.Item label="Title" name="title" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item label="Assignee" name="assignee_id">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={(empQuery.data?.items || []).map((e) => ({
                value: e.id,
                label: `${e.nik} · ${e.full_name}`,
              }))}
            />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            <Form.Item label="Status" name="status">
              <Select options={TASK_STATUSES.map((s) => ({ value: s, label: s }))} />
            </Form.Item>
            <Form.Item label="Priority" name="priority">
              <Select
                options={[
                  { value: 'LOW', label: 'Low' },
                  { value: 'MEDIUM', label: 'Medium' },
                  { value: 'HIGH', label: 'High' },
                  { value: 'CRITICAL', label: 'Critical' },
                ]}
              />
            </Form.Item>
            <Form.Item label="Due" name="due_date">
              <DatePicker style={{ width: '100%' }} format="DD MMM" />
            </Form.Item>
          </div>
          <Button type="primary" htmlType="submit" loading={createMut.isPending}>
            Create
          </Button>
        </Form>
      </Modal>
    </div>
  );
}

// InvoicesTab REMOVED (TSK-022C). Invoice management dipindah ke Finance page
// (akan dibangun di TSK-023D — currently /finance hanya tampilkan reimbursement+procurement).

// ─── MEMBERS TAB ────────────────────────────────────────────────

function MembersTab({ projectId }: { projectId: string }) {
  const query = useQuery({
    queryKey: ['members', projectId],
    queryFn: () => listMembers(projectId),
  });
  const members = query.data || [];

  return (
    <div>
      {members.length === 0 && <Empty description="Belum ada member" />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
        {members.map((m) => (
          <div
            key={m.id}
            style={{
              background: 'var(--ide-surface)',
              border: '1px solid var(--ide-border)',
              borderRadius: 'var(--ide-rm)',
              padding: 12,
            }}
          >
            <div style={{ fontWeight: 700 }}>{m.employee_name}</div>
            <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>
              {m.employee_nik} · {m.role || 'No role'}
            </div>
            <div style={{ marginTop: 8, fontSize: 12 }}>
              <Tag color="blue">{m.allocation_pct}% allocation</Tag>
            </div>
            <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginTop: 4 }}>
              {formatDate(m.start_date)} → {formatDate(m.end_date)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Main Detail Page ───────────────────────────────────────────

export default function ProjectDetailPage() {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isExecutive =
    user?.roles.some(
      (r) => r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA',
    ) ?? false;

  const query = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id),
    enabled: !!id,
  });

  const activateMut = useMutation({
    mutationFn: () => activateProject(id),
    onSuccess: () => {
      message.success('Project activated');
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
  });

  const closeMut = useMutation({
    mutationFn: ({ new_status, reason }: any) => closeProject(id, new_status, reason),
    onSuccess: () => {
      message.success('Project closed');
      queryClient.invalidateQueries({ queryKey: ['project', id] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message || 'Gagal close'),
  });

  const handleClose = () => {
    Modal.confirm({
      title: 'Close Project',
      content: (
        <Form layout="vertical" id="close-form">
          <Form.Item label="New Status">
            <Select
              id="close-status"
              defaultValue="COMPLETED"
              options={[
                { value: 'COMPLETED', label: 'Completed (sukses)' },
                { value: 'TERMINATED', label: 'Terminated (dibatalkan)' },
              ]}
            />
          </Form.Item>
          <Form.Item label="Reason (min 10 char)">
            <TextArea id="close-reason" rows={3} />
          </Form.Item>
        </Form>
      ),
      okText: 'Close Project',
      okType: 'danger',
      onOk: () => {
        const status = (document.getElementById('close-status') as HTMLSelectElement)?.value || 'COMPLETED';
        const reason = (document.getElementById('close-reason') as HTMLTextAreaElement)?.value || '';
        if (reason.length < 10) {
          message.warning('Reason min 10 karakter');
          return Promise.reject();
        }
        return closeMut.mutateAsync({ new_status: status as any, reason });
      },
    });
  };

  if (query.isLoading) return <Spin size="large" style={{ display: 'block', margin: 40 }} />;
  if (!query.data) return <Empty description="Project tidak ditemukan" />;

  const p = query.data;
  const typeTag = projectTypeColor(p.type);
  const statusTag = projectStatusColor(p.status);
  const progress = p.overall_progress_pct ? Number(p.overall_progress_pct) : 0;

  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/projects')}
        style={{ marginBottom: 14 }}
      >
        Projects
      </Button>

      {/* Header */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          padding: '20px 24px',
          marginBottom: 14,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 14 }}>
          <div style={{ flex: 1 }}>
            <div
              style={{
                fontFamily: 'var(--ide-font-mono)',
                fontSize: 12,
                fontWeight: 700,
                color: 'var(--ide-blue)',
                marginBottom: 4,
              }}
            >
              {p.code}
            </div>
            <h2 style={{ fontSize: 24, fontWeight: 800, letterSpacing: -0.5 }}>{p.name}</h2>
            <div style={{ display: 'flex', gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              <span className={`ide-tag ${typeTag.className}`}>{typeTag.label}</span>
              <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
              {p.client_name && <span className="ide-tag ide-tag-blue">{p.client_name}</span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            {p.status === 'DRAFT' && (
              <Button
                type="primary"
                icon={<ThunderboltOutlined />}
                loading={activateMut.isPending}
                onClick={() => activateMut.mutate()}
                style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}
              >
                Activate
              </Button>
            )}
            {!['COMPLETED', 'TERMINATED'].includes(p.status) && (
              <Button danger icon={<StopOutlined />} onClick={handleClose}>
                Close {isExecutive && '(Override)'}
              </Button>
            )}
          </div>
        </div>

        {p.description && (
          <div
            style={{
              marginTop: 14,
              padding: '10px 12px',
              background: 'var(--ide-bg)',
              borderRadius: 'var(--ide-rs)',
              fontSize: 13,
              color: 'var(--ide-ink2)',
              whiteSpace: 'pre-wrap',
            }}
          >
            {p.description}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginTop: 14 }}>
          <div className="ide-kpi">
            <div className="ide-kpi-val" style={{ fontSize: 18 }}>
              {Math.round(progress)}%
            </div>
            <div className="ide-kpi-lbl">Overall Progress</div>
          </div>
          <div className="ide-kpi">
            <div className="ide-kpi-val">{p.member_count}</div>
            <div className="ide-kpi-lbl">Members</div>
          </div>
          <div className="ide-kpi">
            <div className="ide-kpi-val">
              {p.completed_milestones}/{p.milestone_count}
            </div>
            <div className="ide-kpi-lbl">Milestones Done</div>
          </div>
          <div className="ide-kpi">
            <div className="ide-kpi-val" style={{ fontSize: 14 }}>
              {formatIDR(p.contract_value)}
            </div>
            <div className="ide-kpi-lbl">Contract Value</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        defaultActiveKey="milestones"
        items={[
          {
            key: 'milestones',
            label: 'Milestones',
            children: <MilestonesTab projectId={id} />,
          },
          { key: 'tasks', label: 'Tasks (Kanban)', children: <TasksTab projectId={id} /> },
          { key: 'members', label: 'Members', children: <MembersTab projectId={id} /> },
        ]}
      />
    </div>
  );
}
