/**
 * KanbanCard — informative task card untuk kanban board.
 *
 * Menampilkan: slug, title, priority dot, story points, assignee avatar,
 * subtask progress, comment count, epic tag, due date warning.
 * Click → open TaskDrawer with full detail + comments.
 */

import {
  BranchesOutlined,
  CalendarOutlined,
  CommentOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Avatar, Space, Tag, Tooltip, Typography } from 'antd';
import dayjs from 'dayjs';

import { priorityColor, type Task, type TaskPriority } from '@/api/projects';

const { Text } = Typography;

const PRIORITY_LABEL: Record<TaskPriority, string> = {
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
  CRITICAL: 'Critical',
};

function avatarSeedColor(seed: string | null) {
  if (!seed) return '#6e6e73';
  const palette = ['#0071E3', '#34C759', '#FF9500', '#AF52DE', '#32ADE6', '#FF3B30'];
  return palette[seed.charCodeAt(0) % palette.length];
}

interface KanbanCardProps {
  task: Task;
  onClick: () => void;
}

export function KanbanCard({ task, onClick }: KanbanCardProps) {
  const dueSoon =
    task.due_date && dayjs(task.due_date).diff(dayjs(), 'day') <= 3 && task.status !== 'DONE';
  const overdue =
    task.due_date && dayjs(task.due_date).isBefore(dayjs(), 'day') && task.status !== 'DONE';

  const initial = task.assignee_nik
    ? task.assignee_nik.substring(0, 2).toUpperCase()
    : '?';

  return (
    <div
      onClick={onClick}
      style={{
        background: '#fff',
        border: '1px solid rgba(0,0,0,0.08)',
        borderRadius: 10,
        padding: 12,
        cursor: 'pointer',
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        transition: 'all 0.15s',
        marginBottom: 8,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)';
        e.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.04)';
        e.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {/* Top row: slug + priority dot */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <Space size={6}>
          <Text
            style={{
              fontFamily: 'ui-monospace, Menlo, monospace',
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--ide-blue, #0071E3)',
            }}
          >
            {task.slug}
          </Text>
          <Tooltip title={`Priority: ${PRIORITY_LABEL[task.priority]}`}>
            <span
              style={{
                display: 'inline-block',
                width: 8, height: 8, borderRadius: '50%',
                background: priorityColor(task.priority),
              }}
            />
          </Tooltip>
        </Space>
        {task.story_points !== null && task.story_points !== undefined && (
          <Tooltip title={`${task.story_points} story points`}>
            <span
              style={{
                fontSize: 10, fontWeight: 700,
                padding: '2px 7px',
                borderRadius: 10,
                background: 'rgba(0,113,227,0.1)',
                color: 'var(--ide-blue, #0071E3)',
              }}
            >
              {task.story_points}
            </span>
          </Tooltip>
        )}
      </div>

      {/* Title */}
      <div
        style={{
          fontSize: 13,
          fontWeight: 600,
          lineHeight: 1.35,
          color: 'var(--ide-ink1, #1d1d1f)',
          marginBottom: 8,
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          overflow: 'hidden',
        }}
      >
        {task.title}
      </div>

      {/* Epic tag */}
      {task.epic_name && (
        <Tag
          color="purple"
          style={{ fontSize: 10, marginBottom: 8, borderRadius: 4 }}
        >
          <BranchesOutlined /> {task.epic_name}
        </Tag>
      )}

      {/* Footer: subtask progress · comments · due · assignee */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: 4,
        }}
      >
        <Space size={10} style={{ color: 'var(--ide-ink3, #6e6e73)', fontSize: 11 }}>
          {task.subtask_count > 0 && (
            <Tooltip title="Subtasks">
              <span>
                ☑ {task.completed_subtask_count}/{task.subtask_count}
              </span>
            </Tooltip>
          )}
          {task.comment_count > 0 && (
            <Tooltip title="Comments">
              <span>
                <CommentOutlined /> {task.comment_count}
              </span>
            </Tooltip>
          )}
          {task.due_date && (
            <Tooltip title={`Due ${dayjs(task.due_date).format('DD MMM YYYY')}`}>
              <span
                style={{
                  color: overdue
                    ? 'var(--ide-red, #FF3B30)'
                    : dueSoon
                      ? 'var(--ide-orange, #FF9500)'
                      : undefined,
                  fontWeight: overdue || dueSoon ? 600 : 400,
                }}
              >
                <CalendarOutlined /> {dayjs(task.due_date).format('DD MMM')}
              </span>
            </Tooltip>
          )}
        </Space>
        <Tooltip title={task.assignee_name ?? task.assignee_nik ?? 'Unassigned'}>
          {task.assignee_nik ? (
            <Avatar
              size={22}
              style={{
                background: avatarSeedColor(task.assignee_nik),
                fontSize: 9, fontWeight: 700,
              }}
            >
              {initial}
            </Avatar>
          ) : (
            <Avatar size={22} icon={<UserOutlined />} style={{ background: '#d9d9d9' }} />
          )}
        </Tooltip>
      </div>
    </div>
  );
}
