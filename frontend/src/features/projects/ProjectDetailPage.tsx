/**
 * Project Detail Page — TSK-022 + TSK-022B + TSK-022C.
 *
 * Tabs:
 *  - Overview          — meta + KPI + progress
 *  - Hierarchy         — Phase > Epic accordion with task grouping
 *  - Board (Kanban)    — flat board across all tasks, informative KanbanCard,
 *                        click → TaskDrawer (with comments tab)
 *  - Members           — tim project
 */

import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  PlusOutlined,
  StopOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Collapse, Empty, Form, Input, InputNumber, Modal, Progress, Select, Space, Spin, Tabs, Tag, Tooltip, Typography} from 'antd';
import { message } from '@/lib/notify';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { listEmployees } from '@/api/organization';
import {
  activateProject,
  closeProject,
  createEpic,
  createPhase,
  createTask,
  deleteEpic,
  deletePhase,
  getProject,
  listMembers,
  listPhases,
  listProjectEpics,
  listTasks,
  projectStatusColor,
  projectTypeColor,
  TASK_STATUSES,
  updatePhase,
  type Phase,
  type Task,
  type TaskStatus,
} from '@/api/projects';

import { ChangeRequestsTab } from './components/ChangeRequestsTab';
import { DocumentsTab } from './components/DocumentsTab';
import { GanttTab } from './components/GanttTab';
import { KanbanBoard } from './components/KanbanBoard';
import { KanbanCard } from './components/KanbanCard';
import { TaskDrawer } from './components/TaskDrawer';

const { Title, Text, Paragraph } = Typography;

const formatDate = (s: string | null) => (s ? dayjs(s).format('DD MMM YYYY') : '—');

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [closeOpen, setCloseOpen] = useState(false);
  const [closeStatus, setCloseStatus] = useState<'COMPLETED' | 'TERMINATED'>('COMPLETED');

  const projectQuery = useQuery({
    queryKey: ['project', id],
    queryFn: () => getProject(id!),
    enabled: !!id,
  });

  const activateMut = useMutation({
    mutationFn: () => activateProject(id!),
    onSuccess: () => {
      message.success('Project activated');
      queryClient.invalidateQueries({ queryKey: ['project', id] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal activate'),
  });

  const closeMut = useMutation({
    mutationFn: ({ status, reason }: { status: 'COMPLETED' | 'TERMINATED'; reason: string }) =>
      closeProject(id!, status, reason),
    onSuccess: () => {
      message.success('Project closed');
      queryClient.invalidateQueries({ queryKey: ['project', id] });
      setCloseOpen(false);
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal close'),
  });

  if (!id) return <Empty description="Project ID missing" />;
  if (projectQuery.isLoading) return <Spin tip="Loading..." style={{ margin: 40 }} />;
  if (!projectQuery.data) return <Empty description="Project not found" />;

  const project = projectQuery.data;
  const typeColor = projectTypeColor(project.type);
  const statusColor = projectStatusColor(project.status);

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1400, margin: '0 auto' }}>
      <Space style={{ marginBottom: 14 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/projects')}>
          Back
        </Button>
      </Space>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <Space size={10} style={{ marginBottom: 6 }}>
          <Text style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 16, fontWeight: 700, color: 'var(--ide-blue, #0071E3)' }}>
            {project.code}
          </Text>
          <Tag className={typeColor.className}>{typeColor.label}</Tag>
          <Tag className={statusColor.className}>{statusColor.label}</Tag>
        </Space>
        <Title level={3} style={{ margin: '4px 0' }}>{project.name}</Title>
        {project.description && (
          <Paragraph type="secondary" style={{ marginBottom: 4 }}>
            {project.description}
          </Paragraph>
        )}
        <Space size={16} style={{ fontSize: 13, color: 'var(--ide-ink3, #6e6e73)' }}>
          {project.pm_nik && <span>PM: {project.pm_nik}</span>}
          {project.client_name && <span>Client: {project.client_name}</span>}
          <span>{formatDate(project.start_date)} → {formatDate(project.end_date)}</span>
          {project.contract_value && (
            <span>
              Contract: Rp {Number(project.contract_value).toLocaleString('id-ID')} {project.currency}
            </span>
          )}
        </Space>
      </div>

      {/* Actions */}
      <Space style={{ marginBottom: 20 }} wrap>
        {project.status === 'DRAFT' && (
          <Button
            type="primary" icon={<ThunderboltOutlined />}
            loading={activateMut.isPending}
            onClick={() => activateMut.mutate()}
          >
            Activate
          </Button>
        )}
        {(project.status === 'ACTIVE' || project.status === 'ON_HOLD') && (
          <>
            <Button
              icon={<CheckCircleFilled />}
              onClick={() => { setCloseStatus('COMPLETED'); setCloseOpen(true); }}
            >
              Complete
            </Button>
            <Button
              danger icon={<StopOutlined />}
              onClick={() => { setCloseStatus('TERMINATED'); setCloseOpen(true); }}
            >
              Terminate
            </Button>
          </>
        )}
      </Space>

      {/* KPI Strip */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <KPIBox label="Phases" value={`${project.completed_phases}/${project.phase_count}`} />
        <KPIBox label="Members" value={project.member_count} />
        <KPIBox label="Progress" value={`${Math.round(Number(project.overall_progress_pct ?? 0))}%`} />
        <KPIBox
          label="Contract Value"
          value={project.contract_value
            ? `Rp ${Number(project.contract_value).toLocaleString('id-ID')}`
            : '—'}
        />
      </div>

      {/* Tabs */}
      <Tabs
        defaultActiveKey="hierarchy"
        items={[
          { key: 'hierarchy', label: 'Hierarchy', children: <HierarchyTab projectId={id} /> },
          { key: 'board', label: 'Board (Kanban)', children: <KanbanTab projectId={id} /> },
          { key: 'gantt', label: 'Gantt', children: <GanttTab projectId={id} /> },
          { key: 'documents', label: 'Documents', children: <DocumentsTab projectId={id} /> },
          { key: 'cr', label: 'Change Requests', children: <ChangeRequestsTab projectId={id} /> },
          { key: 'members', label: 'Members', children: <MembersTab projectId={id} /> },
        ]}
      />

      {/* Close Modal */}
      <Modal
        title={closeStatus === 'COMPLETED' ? 'Complete Project' : 'Terminate Project'}
        open={closeOpen}
        onCancel={() => setCloseOpen(false)}
        footer={null}
        destroyOnHidden
      >
        <Form layout="vertical" onFinish={(v) => closeMut.mutate({ status: closeStatus, reason: v.reason })}>
          <Form.Item label="Reason" name="reason" rules={[{ required: true, min: 10 }]}>
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={closeMut.isPending}>
            Confirm
          </Button>
        </Form>
      </Modal>
    </div>
  );
}

function KPIBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div
      style={{
        background: '#fff', border: '1px solid rgba(0,0,0,0.06)',
        borderRadius: 10, padding: 14,
      }}
    >
      <Text type="secondary" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.4 }}>
        {label}
      </Text>
      <div style={{ fontSize: 20, fontWeight: 700, marginTop: 2 }}>{value}</div>
    </div>
  );
}

// ─── HIERARCHY TAB ───────────────────────────────────────────────

function HierarchyTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [phaseOpen, setPhaseOpen] = useState(false);
  const [epicOpen, setEpicOpen] = useState(false);
  const [epicPhaseId, setEpicPhaseId] = useState<string | null>(null);
  const [taskOpen, setTaskOpen] = useState(false);
  const [taskEpicId, setTaskEpicId] = useState<string | null>(null);

  const phasesQuery = useQuery({
    queryKey: ['phases', projectId],
    queryFn: () => listPhases(projectId),
  });
  const epicsQuery = useQuery({
    queryKey: ['epics', projectId],
    queryFn: () => listProjectEpics(projectId),
  });
  const tasksQuery = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => listTasks(projectId),
  });
  const employeesQuery = useQuery({
    queryKey: ['employees-list'],
    queryFn: () => listEmployees({ page: 1, page_size: 100 }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['phases', projectId] });
    queryClient.invalidateQueries({ queryKey: ['epics', projectId] });
    queryClient.invalidateQueries({ queryKey: ['tasks', projectId] });
    queryClient.invalidateQueries({ queryKey: ['project', projectId] });
  };

  const createPhaseMut = useMutation({
    mutationFn: (data: any) => createPhase(projectId, data),
    onSuccess: () => { message.success('Phase dibuat'); invalidate(); setPhaseOpen(false); },
  });
  const updatePhaseMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updatePhase(id, data),
    onSuccess: () => { invalidate(); message.success('Phase updated'); },
  });
  const deletePhaseMut = useMutation({
    mutationFn: (pid: string) => deletePhase(pid),
    onSuccess: () => { invalidate(); message.success('Phase dihapus'); },
  });
  const createEpicMut = useMutation({
    mutationFn: ({ phaseId, data }: { phaseId: string; data: any }) => createEpic(phaseId, data),
    onSuccess: () => { invalidate(); setEpicOpen(false); message.success('Epic dibuat'); },
  });
  const deleteEpicMut = useMutation({
    mutationFn: (eid: string) => deleteEpic(eid),
    onSuccess: () => { invalidate(); message.success('Epic dihapus'); },
  });
  const createTaskMut = useMutation({
    mutationFn: (data: any) => createTask(projectId, data),
    onSuccess: () => { invalidate(); setTaskOpen(false); message.success('Task dibuat'); },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create task'),
  });

  const phases = phasesQuery.data ?? [];
  const epics = epicsQuery.data ?? [];
  const tasks = tasksQuery.data ?? [];

  const tasksByEpic = (epicId: string) => tasks.filter((t) => t.epic_id === epicId);
  const orphanTasks = tasks.filter((t) => t.epic_id === null);

  return (
    <div>
      <div style={{ marginBottom: 14, display: 'flex', justifyContent: 'space-between' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Project › Phase › Epic › Task (klik task untuk buka detail + comments)
        </Text>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setPhaseOpen(true)}>
          Add Phase
        </Button>
      </div>

      {phases.length === 0 ? (
        <Empty description="Belum ada Phase. Mulai dengan menambahkan Phase pertama." />
      ) : (
        <Collapse
          defaultActiveKey={phases.map((p) => p.id)}
          items={phases.map((p) => ({
            key: p.id,
            label: <PhaseHeader phase={p} onUpdate={updatePhaseMut.mutate} onDelete={() => deletePhaseMut.mutate(p.id)} />,
            children: (
              <PhaseContent
                phase={p}
                epics={epics.filter((e) => e.phase_id === p.id)}
                tasksByEpic={tasksByEpic}
                onAddEpic={() => { setEpicPhaseId(p.id); setEpicOpen(true); }}
                onDeleteEpic={(eid) => deleteEpicMut.mutate(eid)}
                onAddTask={(epicId) => { setTaskEpicId(epicId); setTaskOpen(true); }}
              />
            ),
          }))}
        />
      )}

      {orphanTasks.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>Tasks tanpa epic:</Text>
          <div style={{ marginTop: 6 }}>
            {orphanTasks.map((t) => (
              <KanbanCard key={t.id} task={t} onClick={() => {}} />
            ))}
          </div>
        </div>
      )}

      {/* Create Phase Modal */}
      <Modal
        title="Add Phase" open={phaseOpen} onCancel={() => setPhaseOpen(false)} footer={null} destroyOnHidden
      >
        <Form layout="vertical" onFinish={(v) => createPhaseMut.mutate(v)}>
          <Form.Item label="Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="Phase 1 — MVP" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Form.Item label="Target Date (YYYY-MM-DD)" name="target_date">
            <Input placeholder="2026-12-31" />
          </Form.Item>
          <Form.Item label="Order Index" name="order_index" initialValue={0}>
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createPhaseMut.isPending}>Create</Button>
        </Form>
      </Modal>

      {/* Create Epic Modal */}
      <Modal
        title="Add Epic" open={epicOpen} onCancel={() => setEpicOpen(false)} footer={null} destroyOnHidden
      >
        <Form layout="vertical" onFinish={(v) => createEpicMut.mutate({ phaseId: epicPhaseId!, data: v })}>
          <Form.Item label="Name" name="name" rules={[{ required: true }]}>
            <Input placeholder="Auth & RBAC" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 4 }} />
          </Form.Item>
          <Form.Item label="Color (CSS)" name="color">
            <Input placeholder="#AF52DE" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createEpicMut.isPending}>Create</Button>
        </Form>
      </Modal>

      {/* Create Task Modal */}
      <Modal
        title="Add Task" open={taskOpen} onCancel={() => setTaskOpen(false)} footer={null} destroyOnHidden
      >
        <Form
          layout="vertical"
          initialValues={{ status: 'BACKLOG', priority: 'MEDIUM', epic_id: taskEpicId ?? undefined }}
          onFinish={(v) => createTaskMut.mutate({ ...v, epic_id: taskEpicId ?? v.epic_id })}
        >
          <Form.Item label="Title" name="title" rules={[{ required: true }]}>
            <Input placeholder="Implement login form" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 5 }} />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Status" name="status">
              <Select options={TASK_STATUSES.map((s) => ({ value: s, label: s }))} />
            </Form.Item>
            <Form.Item label="Priority" name="priority">
              <Select
                options={['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((p) => ({ value: p, label: p }))}
              />
            </Form.Item>
            <Form.Item label="Story Points" name="story_points">
              <InputNumber min={0} max={99} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Assignee" name="assignee_id">
              <Select
                allowClear showSearch optionFilterProp="label"
                options={(employeesQuery.data?.items ?? []).map((e: any) => ({
                  value: e.id,
                  label: `${e.nik} — ${e.full_name}`,
                }))}
              />
            </Form.Item>
            <Form.Item label="Due Date (YYYY-MM-DD)" name="due_date">
              <Input placeholder="2026-12-31" />
            </Form.Item>
          </div>
          <Button type="primary" htmlType="submit" loading={createTaskMut.isPending}>Create</Button>
        </Form>
      </Modal>
    </div>
  );
}

function PhaseHeader({
  phase, onUpdate, onDelete,
}: {
  phase: Phase;
  onUpdate: (args: { id: string; data: any }) => void;
  onDelete: () => void;
}) {
  const isOverdue = phase.is_overdue;
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
      <Space>
        <Text strong>{phase.name}</Text>
        <Tag color={phase.status === 'COMPLETED' ? 'green' : phase.status === 'IN_PROGRESS' ? 'blue' : 'default'}>
          {phase.status}
        </Tag>
        {phase.target_date && (
          <Text type="secondary" style={{ fontSize: 11, color: isOverdue ? 'var(--ide-red, #FF3B30)' : undefined }}>
            Target: {formatDate(phase.target_date)} {isOverdue && '(OVERDUE)'}
          </Text>
        )}
      </Space>
      <Space>
        <Progress percent={Math.round(Number(phase.progress_pct))} size="small" style={{ width: 100 }} />
        <Tooltip title="Mark complete">
          <Button
            type="text" size="small" icon={<CheckCircleFilled />}
            onClick={(e) => {
              e.stopPropagation();
              onUpdate({ id: phase.id, data: { status: 'COMPLETED', progress_pct: 100 } });
            }}
            disabled={phase.status === 'COMPLETED'}
          />
        </Tooltip>
        <Button type="text" size="small" danger onClick={(e) => { e.stopPropagation(); onDelete(); }}>
          Delete
        </Button>
      </Space>
    </div>
  );
}

function PhaseContent({
  phase, epics, tasksByEpic, onAddEpic, onDeleteEpic, onAddTask,
}: {
  phase: Phase;
  epics: { id: string; name: string; color: string | null; task_count: number; completed_task_count: number }[];
  tasksByEpic: (epicId: string) => Task[];
  onAddEpic: () => void;
  onDeleteEpic: (eid: string) => void;
  onAddTask: (epicId: string | null) => void;
}) {
  const [taskDrawerOpen, setTaskDrawerOpen] = useState(false);
  const [activeTask, setActiveTask] = useState<Task | null>(null);

  return (
    <div>
      {phase.description && (
        <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 10 }}>
          {phase.description}
        </Paragraph>
      )}
      <div style={{ marginBottom: 10 }}>
        <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={onAddEpic}>
          Add Epic
        </Button>
      </div>

      {epics.length === 0 ? (
        <Text type="secondary" style={{ fontSize: 12 }}>Belum ada epic di phase ini.</Text>
      ) : (
        <Space direction="vertical" size={12} style={{ width: '100%' }}>
          {epics.map((e) => (
            <div
              key={e.id}
              style={{
                background: 'rgba(0,0,0,0.02)', padding: 12, borderRadius: 8,
                borderLeft: `3px solid ${e.color ?? 'var(--ide-purple, #AF52DE)'}`,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                <Space>
                  <Text strong>{e.name}</Text>
                  <Text type="secondary" style={{ fontSize: 11 }}>
                    {e.completed_task_count}/{e.task_count} tasks
                  </Text>
                </Space>
                <Space>
                  <Button size="small" icon={<PlusOutlined />} onClick={() => onAddTask(e.id)}>
                    Add Task
                  </Button>
                  <Button size="small" danger onClick={() => onDeleteEpic(e.id)}>Delete</Button>
                </Space>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 8 }}>
                {tasksByEpic(e.id).map((t) => (
                  <KanbanCard
                    key={t.id} task={t}
                    onClick={() => { setActiveTask(t); setTaskDrawerOpen(true); }}
                  />
                ))}
              </div>
            </div>
          ))}
        </Space>
      )}

      <TaskDrawer
        task={activeTask} open={taskDrawerOpen}
        onClose={() => { setTaskDrawerOpen(false); setActiveTask(null); }}
      />
    </div>
  );
}

// ─── KANBAN TAB (drag-drop board, TSK-064 polish) ────────────────

function KanbanTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const query = useQuery({
    queryKey: ['tasks', projectId],
    queryFn: () => listTasks(projectId),
  });

  const updateMut = useMutation({
    mutationFn: async ({ id, status }: { id: string; status: TaskStatus }) => {
      const { updateTask } = await import('@/api/projects');
      return updateTask(id, { status });
    },
    // Optimistic update — instant UI feedback
    onMutate: async ({ id, status }) => {
      await queryClient.cancelQueries({ queryKey: ['tasks', projectId] });
      const previous = queryClient.getQueryData<Task[]>(['tasks', projectId]);
      queryClient.setQueryData<Task[]>(['tasks', projectId], (old) =>
        (old ?? []).map((t) => (t.id === id ? { ...t, status } : t)),
      );
      return { previous };
    },
    onError: (e: any, _vars, ctx) => {
      // Rollback on error
      if (ctx?.previous) {
        queryClient.setQueryData(['tasks', projectId], ctx.previous);
      }
      message.error(e?.response?.data?.detail?.message ?? 'Gagal update status');
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks', projectId] });
    },
  });

  const tasks = query.data ?? [];

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12 }}>
        {tasks.length} tasks total · drag card antar column untuk update status · klik card untuk detail
      </Text>
      <div style={{ marginTop: 12 }}>
        <KanbanBoard
          tasks={tasks}
          onCardClick={(t) => { setActiveTask(t); setDrawerOpen(true); }}
          onStatusChange={(id, status) => updateMut.mutate({ id, status })}
        />
      </div>
      <TaskDrawer
        task={activeTask} open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setActiveTask(null); }}
      />
    </div>
  );
}

// ─── MEMBERS TAB ────────────────────────────────────────────────

function MembersTab({ projectId }: { projectId: string }) {
  const query = useQuery({
    queryKey: ['members', projectId],
    queryFn: () => listMembers(projectId),
  });
  const members = query.data ?? [];

  return (
    <div>
      {members.length === 0 && <Empty description="Belum ada member" />}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
        {members.map((m) => (
          <div
            key={m.id}
            style={{
              background: '#fff', border: '1px solid rgba(0,0,0,0.08)',
              borderRadius: 10, padding: 12,
            }}
          >
            <div style={{ fontWeight: 700 }}>{m.employee_name}</div>
            <div style={{ fontSize: 11, color: 'var(--ide-ink3, #6e6e73)' }}>
              {m.employee_nik} · {m.role ?? 'No role'}
            </div>
            <div style={{ marginTop: 8, fontSize: 12 }}>
              <Tag color="blue">{m.allocation_pct}% allocation</Tag>
            </div>
            <div style={{ fontSize: 10, color: 'var(--ide-ink3, #6e6e73)', marginTop: 4 }}>
              {formatDate(m.start_date)} → {formatDate(m.end_date)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
