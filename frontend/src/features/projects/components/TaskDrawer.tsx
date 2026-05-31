/**
 * TaskDrawer — full task detail drawer.
 *
 * Tabs: Detail (edit form + subtask list) | Comments (markdown thread).
 * Subtasks accessible inline with quick-add + status toggle.
 * Comments accessible langsung dari sini (tab).
 */

import {
  CheckSquareOutlined,
  CommentOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button, Drawer, Form, Input, InputNumber, Popconfirm, Select, Space, Tabs, Tag, Tooltip, Typography} from 'antd';
import { message } from '@/lib/notify';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  createSubtask,
  createSubtaskComment,
  createTaskComment,
  deleteSubtask,
  deleteSubtaskComment,
  deleteTask,
  deleteTaskComment,
  listSubtaskComments,
  listSubtasks,
  listTaskComments,
  TASK_STATUSES,
  taskStatusColor,
  updateSubtask,
  updateSubtaskComment,
  updateTask,
  updateTaskComment,
  type Subtask,
  type Task,
  type TaskPriority,
} from '@/api/projects';
import { listEmployees } from '@/api/organization';
import { useAuthStore } from '@/store/auth';

import { CommentThread } from './CommentThread';

const { Text, Title } = Typography;

const PRIORITIES: TaskPriority[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

interface TaskDrawerProps {
  task: Task | null;
  open: boolean;
  onClose: () => void;
}

function SubtaskRow({
  s,
  onToggle,
  onDelete,
  onOpenComments,
}: {
  s: Subtask;
  onToggle: () => void;
  onDelete: () => void;
  onOpenComments: () => void;
}) {
  const done = s.status === 'DONE';
  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        padding: 8,
        background: done ? 'rgba(52,199,89,0.05)' : 'rgba(0,0,0,0.02)',
        borderRadius: 6,
        alignItems: 'center',
      }}
    >
      <input type="checkbox" checked={done} onChange={onToggle} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <Text
            style={{
              fontFamily: 'ui-monospace, Menlo, monospace',
              fontSize: 10,
              color: 'var(--ide-blue, #0071E3)',
              fontWeight: 700,
            }}
          >
            {s.slug}
          </Text>
          <Text
            style={{
              fontSize: 12,
              textDecoration: done ? 'line-through' : 'none',
              color: done ? 'var(--ide-ink3, #6e6e73)' : 'var(--ide-ink1, #1d1d1f)',
            }}
          >
            {s.title}
          </Text>
        </div>
        <Space size={6} style={{ marginTop: 2, color: 'var(--ide-ink3, #6e6e73)', fontSize: 10 }}>
          {s.story_points !== null && <span>{s.story_points} pts</span>}
          {s.assignee_nik && <span>@{s.assignee_nik}</span>}
          {s.due_date && <span>{dayjs(s.due_date).format('DD MMM')}</span>}
          {s.comment_count > 0 && <span>💬 {s.comment_count}</span>}
        </Space>
      </div>
      <Tooltip title="Comments">
        <Button type="text" size="small" icon={<CommentOutlined />} onClick={onOpenComments} />
      </Tooltip>
      <Popconfirm title="Hapus subtask?" onConfirm={onDelete}>
        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
      </Popconfirm>
    </div>
  );
}

function SubtaskCommentDrawer({
  subtask,
  open,
  onClose,
}: {
  subtask: Subtask | null;
  open: boolean;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);

  const query = useQuery({
    queryKey: ['subtask-comments', subtask?.id],
    queryFn: () => listSubtaskComments(subtask!.id),
    enabled: !!subtask && open,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['subtask-comments', subtask?.id] });
    queryClient.invalidateQueries({ queryKey: ['subtasks', subtask?.task_id] });
  };

  return (
    <Drawer
      title={subtask ? `${subtask.slug} · Komentar` : 'Komentar'}
      open={open}
      onClose={onClose}
      width={460}
    >
      {subtask && (
        <>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {subtask.title}
          </Text>
          <div style={{ marginTop: 16 }}>
            <CommentThread
              comments={query.data ?? []}
              currentUserId={currentUser?.id ?? null}
              loading={query.isLoading}
              onCreate={async (body) => {
                await createSubtaskComment(subtask.id, body);
                invalidate();
              }}
              onUpdate={async (cid, body) => {
                await updateSubtaskComment(cid, body);
                invalidate();
              }}
              onDelete={async (cid) => {
                await deleteSubtaskComment(cid);
                invalidate();
                message.success('Komentar dihapus');
              }}
            />
          </div>
        </>
      )}
    </Drawer>
  );
}

export function TaskDrawer({ task, open, onClose }: TaskDrawerProps) {
  const queryClient = useQueryClient();
  const currentUser = useAuthStore((s) => s.user);
  const [form] = Form.useForm();
  const [subForm] = Form.useForm();
  const [subCommentDrawerOpen, setSubCommentDrawerOpen] = useState(false);
  const [activeSubtaskForComment, setActiveSubtaskForComment] = useState<Subtask | null>(null);

  const subtasksQuery = useQuery({
    queryKey: ['subtasks', task?.id],
    queryFn: () => listSubtasks(task!.id),
    enabled: !!task && open,
  });

  const commentsQuery = useQuery({
    queryKey: ['task-comments', task?.id],
    queryFn: () => listTaskComments(task!.id),
    enabled: !!task && open,
  });

  const employeesQuery = useQuery({
    queryKey: ['employees-list'],
    queryFn: () => listEmployees({ page: 1, page_size: 100 }),
    enabled: open,
  });

  const updateTaskMut = useMutation({
    mutationFn: (data: any) => updateTask(task!.id, data),
    onSuccess: () => {
      message.success('Task disimpan');
      queryClient.invalidateQueries({ queryKey: ['tasks', task?.project_id] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal update task'),
  });

  const deleteTaskMut = useMutation({
    mutationFn: () => deleteTask(task!.id),
    onSuccess: () => {
      message.success('Task dihapus');
      queryClient.invalidateQueries({ queryKey: ['tasks', task?.project_id] });
      onClose();
    },
  });

  const createSubtaskMut = useMutation({
    mutationFn: (data: any) => createSubtask(task!.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subtasks', task?.id] });
      queryClient.invalidateQueries({ queryKey: ['tasks', task?.project_id] });
      subForm.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create subtask'),
  });

  const updateSubtaskMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateSubtask(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subtasks', task?.id] });
    },
  });

  const deleteSubtaskMut = useMutation({
    mutationFn: (id: string) => deleteSubtask(id),
    onSuccess: () => {
      message.success('Subtask dihapus');
      queryClient.invalidateQueries({ queryKey: ['subtasks', task?.id] });
      queryClient.invalidateQueries({ queryKey: ['tasks', task?.project_id] });
    },
  });

  const invalidateComments = () => {
    queryClient.invalidateQueries({ queryKey: ['task-comments', task?.id] });
    queryClient.invalidateQueries({ queryKey: ['tasks', task?.project_id] });
  };

  if (!task) return null;

  return (
    <>
      <Drawer
        title={
          <Space>
            <Text
              style={{
                fontFamily: 'ui-monospace, Menlo, monospace',
                fontSize: 14,
                color: 'var(--ide-blue, #0071E3)',
                fontWeight: 700,
              }}
            >
              {task.slug}
            </Text>
            <Tag color={taskStatusColor(task.status) as any}>{task.status}</Tag>
          </Space>
        }
        extra={
          <Popconfirm title="Hapus task ini?" onConfirm={() => deleteTaskMut.mutate()}>
            <Button danger icon={<DeleteOutlined />}>
              Hapus
            </Button>
          </Popconfirm>
        }
        open={open}
        onClose={onClose}
        width={620}
      >
        <Title level={5} style={{ marginTop: 0 }}>
          {task.title}
        </Title>
        {task.phase_name && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            {task.phase_name} {task.epic_name && `→ ${task.epic_name}`}
          </Text>
        )}

        <Tabs
          defaultActiveKey="detail"
          style={{ marginTop: 16 }}
          items={[
            {
              key: 'detail',
              label: 'Detail',
              children: (
                <div>
                  <Form
                    form={form}
                    layout="vertical"
                    size="small"
                    initialValues={{
                      title: task.title,
                      description: task.description,
                      status: task.status,
                      priority: task.priority,
                      story_points: task.story_points ?? undefined,
                      assignee_id: task.assignee_id ?? undefined,
                      due_date: task.due_date ?? undefined,
                    }}
                    onValuesChange={(_changed, all) => {
                      // auto-save on blur via debounced submit
                      updateTaskMut.mutate(all);
                    }}
                  >
                    <Form.Item label="Title" name="title">
                      <Input />
                    </Form.Item>
                    <Form.Item label="Description" name="description">
                      <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
                    </Form.Item>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                      <Form.Item label="Status" name="status">
                        <Select
                          options={TASK_STATUSES.map((s) => ({ value: s, label: s }))}
                        />
                      </Form.Item>
                      <Form.Item label="Priority" name="priority">
                        <Select options={PRIORITIES.map((p) => ({ value: p, label: p }))} />
                      </Form.Item>
                      <Form.Item label="Story Points" name="story_points">
                        <InputNumber min={0} max={99} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item label="Assignee" name="assignee_id">
                        <Select
                          allowClear
                          showSearch
                          optionFilterProp="label"
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
                  </Form>

                  {/* Subtasks */}
                  <div style={{ marginTop: 16 }}>
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: 8,
                      }}
                    >
                      <Text strong>
                        <CheckSquareOutlined /> Subtasks ({task.completed_subtask_count}/
                        {task.subtask_count})
                      </Text>
                    </div>
                    <Form
                      form={subForm}
                      layout="inline"
                      size="small"
                      onFinish={(v) => createSubtaskMut.mutate(v)}
                    >
                      <Form.Item name="title" rules={[{ required: true }]} style={{ flex: 1 }}>
                        <Input placeholder="Subtask title (Enter to add)" />
                      </Form.Item>
                      <Form.Item>
                        <Button
                          type="primary"
                          htmlType="submit"
                          icon={<PlusOutlined />}
                          loading={createSubtaskMut.isPending}
                        />
                      </Form.Item>
                    </Form>
                    <Space direction="vertical" size={6} style={{ width: '100%', marginTop: 10 }}>
                      {(subtasksQuery.data ?? []).map((s) => (
                        <SubtaskRow
                          key={s.id}
                          s={s}
                          onToggle={() =>
                            updateSubtaskMut.mutate({
                              id: s.id,
                              data: { status: s.status === 'DONE' ? 'TODO' : 'DONE' },
                            })
                          }
                          onDelete={() => deleteSubtaskMut.mutate(s.id)}
                          onOpenComments={() => {
                            setActiveSubtaskForComment(s);
                            setSubCommentDrawerOpen(true);
                          }}
                        />
                      ))}
                    </Space>
                  </div>
                </div>
              ),
            },
            {
              key: 'comments',
              label: (
                <span>
                  <CommentOutlined /> Komentar ({task.comment_count})
                </span>
              ),
              children: (
                <CommentThread
                  comments={commentsQuery.data ?? []}
                  currentUserId={currentUser?.id ?? null}
                  loading={commentsQuery.isLoading}
                  onCreate={async (body) => {
                    await createTaskComment(task.id, body);
                    invalidateComments();
                  }}
                  onUpdate={async (cid, body) => {
                    await updateTaskComment(cid, body);
                    invalidateComments();
                  }}
                  onDelete={async (cid) => {
                    await deleteTaskComment(cid);
                    invalidateComments();
                    message.success('Komentar dihapus');
                  }}
                />
              ),
            },
          ]}
        />
      </Drawer>

      <SubtaskCommentDrawer
        subtask={activeSubtaskForComment}
        open={subCommentDrawerOpen}
        onClose={() => setSubCommentDrawerOpen(false)}
      />
    </>
  );
}
