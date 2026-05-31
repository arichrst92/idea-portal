/**
 * Onboarding Assignment Detail — TSK-016.
 * Checklist grouped by category, interactive checkbox per task.
 * Visual reference: GUI html/IDEA_OnboardingKaryawan.html.
 */

import {
  ArrowLeftOutlined,
  CheckOutlined,
  CloseOutlined,
  ExclamationOutlined,
  LinkOutlined,
  MinusOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Dropdown, Empty, Form, Input, Modal, Spin} from 'antd';
import { message } from '@/lib/notify';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  CATEGORY_META,
  ROLE_LABELS,
  assignmentStatusColor,
  getAssignment,
  updateCompletion,
  type TaskCompletion,
  type TaskCompletionStatus,
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

function CheckCircle({
  status,
  onClick,
}: {
  status: TaskCompletionStatus;
  onClick: () => void;
}) {
  let bg = 'transparent';
  let border = '2px solid var(--ide-border)';
  let icon: React.ReactNode = null;
  let color = '#fff';

  switch (status) {
    case 'DONE':
      bg = 'var(--ide-green)';
      border = '2px solid var(--ide-green)';
      icon = <CheckOutlined style={{ fontSize: 12 }} />;
      break;
    case 'BLOCKED':
      bg = 'var(--ide-orange)';
      border = '2px solid var(--ide-orange)';
      icon = <ExclamationOutlined style={{ fontSize: 12 }} />;
      break;
    case 'SKIPPED':
      bg = 'var(--ide-ink3)';
      border = '2px solid var(--ide-ink3)';
      icon = <MinusOutlined style={{ fontSize: 11 }} />;
      break;
    default:
      bg = 'transparent';
      border = '2px solid var(--ide-border)';
      color = 'transparent';
  }

  return (
    <div
      onClick={onClick}
      style={{
        width: 24,
        height: 24,
        borderRadius: '50%',
        border,
        background: bg,
        color,
        flexShrink: 0,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.15s',
      }}
      title={`Status: ${status}`}
    >
      {icon}
    </div>
  );
}

function TaskRow({
  completion,
  onUpdate,
}: {
  completion: TaskCompletion;
  onUpdate: (
    id: string,
    status: TaskCompletionStatus,
    options?: { blocker_reason?: string; notes?: string },
  ) => void;
}) {
  const isDone = completion.status === 'DONE';
  const items = [
    {
      key: 'DONE',
      label: '✓ Mark as Done',
      onClick: () => onUpdate(completion.id, 'DONE'),
    },
    {
      key: 'PENDING',
      label: '○ Reset to Pending',
      onClick: () => onUpdate(completion.id, 'PENDING'),
    },
    {
      key: 'SKIPPED',
      label: '— Skip Task',
      onClick: () => onUpdate(completion.id, 'SKIPPED'),
    },
    {
      key: 'BLOCKED',
      label: '⚠ Mark Blocked',
      onClick: () => {
        const reason = prompt('Apa yang memblokir task ini? (min 5 karakter)');
        if (reason && reason.trim().length >= 5) {
          onUpdate(completion.id, 'BLOCKED', { blocker_reason: reason.trim() });
        } else if (reason !== null) {
          message.warning('Min 5 karakter');
        }
      },
    },
  ];

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: 12,
        padding: '12px 14px',
        borderBottom: '1px solid var(--ide-border2)',
        background: isDone ? 'var(--ide-green-soft)' : 'transparent',
        transition: 'background 0.12s',
      }}
    >
      <Dropdown menu={{ items }} trigger={['click']}>
        <div style={{ display: 'inline-block' }}>
          <CheckCircle status={completion.status} onClick={() => {}} />
        </div>
      </Dropdown>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            fontSize: 13,
            fontWeight: isDone ? 500 : 600,
            color: isDone ? 'var(--ide-ink2)' : 'var(--ide-ink)',
            textDecoration: isDone ? 'line-through' : 'none',
          }}
        >
          {completion.task_title}
          {completion.task_is_required === false && (
            <span
              style={{
                fontSize: 10,
                fontWeight: 600,
                marginLeft: 6,
                color: 'var(--ide-ink3)',
                background: 'var(--ide-bg)',
                padding: '1px 6px',
                borderRadius: 10,
              }}
            >
              optional
            </span>
          )}
        </div>

        <div
          style={{
            display: 'flex',
            gap: 10,
            fontSize: 11,
            color: 'var(--ide-ink3)',
            marginTop: 4,
            alignItems: 'center',
          }}
        >
          {completion.task_assigned_role && (
            <span>
              👤 {ROLE_LABELS[completion.task_assigned_role]}
            </span>
          )}
          {completion.due_date && (
            <span>📅 Due {formatDate(completion.due_date)}</span>
          )}
          {completion.task_reference_url && (
            <a
              href={completion.task_reference_url}
              target="_blank"
              rel="noreferrer"
              style={{ color: 'var(--ide-blue)' }}
            >
              <LinkOutlined /> Reference
            </a>
          )}
          {completion.completed_at && (
            <span>✅ {formatDate(completion.completed_at)}</span>
          )}
        </div>

        {completion.status === 'BLOCKED' && completion.blocker_reason && (
          <div
            style={{
              marginTop: 6,
              fontSize: 11,
              color: 'var(--ide-orange)',
              background: 'var(--ide-orange-soft)',
              padding: '4px 8px',
              borderRadius: 'var(--ide-rs)',
            }}
          >
            ⚠ Blocker: {completion.blocker_reason}
          </div>
        )}
      </div>
    </div>
  );
}

export default function OnboardingDetailPage() {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['onboarding-assignment', id],
    queryFn: () => getAssignment(id),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: ({
      completionId,
      payload,
    }: {
      completionId: string;
      payload: { status: TaskCompletionStatus; blocker_reason?: string; notes?: string };
    }) => updateCompletion(completionId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['onboarding-assignment', id] });
      queryClient.invalidateQueries({ queryKey: ['onboarding-assignments'] });
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail?.message || 'Gagal update task');
    },
  });

  const handleUpdate = (
    completionId: string,
    status: TaskCompletionStatus,
    options?: { blocker_reason?: string; notes?: string },
  ) => {
    mutation.mutate({
      completionId,
      payload: { status, blocker_reason: options?.blocker_reason, notes: options?.notes },
    });
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
        <Empty description="Assignment tidak ditemukan" />
        <Button onClick={() => navigate('/onboarding')} style={{ marginTop: 12 }}>
          Kembali
        </Button>
      </div>
    );
  }

  const assignment = query.data;
  const statusTag = assignmentStatusColor(assignment.status);
  const progressColor =
    assignment.progress_percent >= 100
      ? 'var(--ide-green)'
      : assignment.progress_percent >= 50
        ? 'var(--ide-blue)'
        : 'var(--ide-orange)';

  return (
    <div className="ide-font" style={{ maxWidth: 980, margin: '0 auto' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/onboarding')}
        style={{ marginBottom: 14, fontWeight: 600 }}
      >
        Daftar Onboarding
      </Button>

      {/* Hero header */}
      <div
        style={{
          background: 'linear-gradient(135deg, var(--ide-blue) 0%, var(--ide-teal) 100%)',
          borderRadius: 'var(--ide-r)',
          padding: '24px 28px',
          color: '#fff',
          marginBottom: 18,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            right: -40,
            top: -40,
            width: 180,
            height: 180,
            background: 'rgba(255,255,255,0.1)',
            borderRadius: '50%',
          }}
        />
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            position: 'relative',
            gap: 16,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, opacity: 0.85, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              Onboarding for
            </div>
            <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: -0.5 }}>
              {assignment.employee_name}
            </div>
            <div style={{ fontSize: 13, opacity: 0.9, marginTop: 4 }}>
              {assignment.employee_nik} · {assignment.employee_department || 'No dept'}
            </div>
            <div style={{ fontSize: 12, opacity: 0.85, marginTop: 8 }}>
              Template: <strong>{assignment.template_name}</strong>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div
              style={{
                fontSize: 38,
                fontWeight: 800,
                fontFamily: 'var(--ide-font-mono)',
                letterSpacing: -1,
              }}
            >
              {assignment.progress_percent}%
            </div>
            <div style={{ fontSize: 11, opacity: 0.85, textTransform: 'uppercase' }}>
              {assignment.completed_tasks} / {assignment.total_tasks} tasks
            </div>
            <span
              className={`ide-tag ${statusTag.className}`}
              style={{
                background: 'rgba(255,255,255,0.2)',
                color: '#fff',
                marginTop: 6,
                fontWeight: 700,
              }}
            >
              {statusTag.label}
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div
          style={{
            marginTop: 18,
            height: 8,
            background: 'rgba(255,255,255,0.2)',
            borderRadius: 4,
            overflow: 'hidden',
            position: 'relative',
            zIndex: 1,
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${assignment.progress_percent}%`,
              background: 'rgba(255,255,255,0.9)',
              transition: 'width 0.3s',
            }}
          />
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 10,
            fontSize: 11,
            opacity: 0.85,
            position: 'relative',
            zIndex: 1,
          }}
        >
          <span>Started: {formatDate(assignment.started_at)}</span>
          <span>Target: {formatDate(assignment.target_completion_date)}</span>
        </div>
      </div>

      {/* Checklist grouped by category */}
      {Object.entries(assignment.completions_by_category).map(([category, completions]) => {
        const meta = CATEGORY_META[category as keyof typeof CATEGORY_META] || CATEGORY_META.OTHER;
        const doneCount = completions.filter((c) => c.status === 'DONE').length;
        const totalRequired = completions.filter((c) => c.task_is_required !== false).length;

        return (
          <div
            key={category}
            style={{
              background: 'var(--ide-surface)',
              border: '1px solid var(--ide-border)',
              borderRadius: 'var(--ide-r)',
              marginBottom: 14,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: '14px 20px',
                background: 'var(--ide-bg)',
                borderBottom: '1px solid var(--ide-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 16 }}>{meta.icon}</span>
                <span
                  style={{
                    fontSize: 13,
                    fontWeight: 700,
                    color: meta.color,
                    textTransform: 'uppercase',
                    letterSpacing: 0.5,
                  }}
                >
                  {meta.label}
                </span>
              </div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: 'var(--ide-ink3)',
                  fontFamily: 'var(--ide-font-mono)',
                }}
              >
                {doneCount} / {totalRequired}
              </span>
            </div>

            <div>
              {completions.map((c) => (
                <TaskRow key={c.id} completion={c} onUpdate={handleUpdate} />
              ))}
            </div>
          </div>
        );
      })}

      {Object.keys(assignment.completions_by_category).length === 0 && (
        <Empty description="Template ini belum punya tasks" />
      )}
    </div>
  );
}
