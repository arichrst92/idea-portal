/**
 * CommentThread — markdown comment list + add form.
 *
 * Generic component dipakai untuk Task maupun Subtask comments.
 * Props: comments array, currentUserId, onCreate, onUpdate, onDelete.
 */

import { DeleteOutlined, EditOutlined, EyeOutlined, SendOutlined } from '@ant-design/icons';
import {
  Avatar,
  Button,
  Empty,
  Input,
  Popconfirm,
  Space,
  Tabs,
  Tooltip,
  Typography,
} from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import type { Comment } from '@/api/projects';

const { Text } = Typography;

interface CommentThreadProps {
  comments: Comment[];
  currentUserId: string | null;
  loading?: boolean;
  onCreate: (body: string) => Promise<void> | void;
  onUpdate: (commentId: string, body: string) => Promise<void> | void;
  onDelete: (commentId: string) => Promise<void> | void;
}

function avatarColor(seed: string | null) {
  if (!seed) return 'var(--ide-ink3, #6e6e73)';
  const palette = ['#0071E3', '#34C759', '#FF9500', '#AF52DE', '#32ADE6', '#FF3B30'];
  const idx = seed.charCodeAt(0) % palette.length;
  return palette[idx];
}

function CommentItem({
  c,
  isAuthor,
  onUpdate,
  onDelete,
}: {
  c: Comment;
  isAuthor: boolean;
  onUpdate: (id: string, body: string) => Promise<void> | void;
  onDelete: (id: string) => Promise<void> | void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(c.body);
  const [saving, setSaving] = useState(false);

  const initial = (c.author_nik ?? c.author_name ?? '?').substring(0, 2).toUpperCase();

  return (
    <div
      style={{
        display: 'flex',
        gap: 10,
        padding: '12px 0',
        borderBottom: '1px solid rgba(0,0,0,0.06)',
      }}
    >
      <Avatar
        size={32}
        style={{ background: avatarColor(c.author_nik), flexShrink: 0, fontSize: 11 }}
      >
        {initial}
      </Avatar>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <Space size={6}>
            <Text strong style={{ fontSize: 12 }}>
              {c.author_name ?? c.author_nik ?? 'Anon'}
            </Text>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {dayjs(c.created_at).format('DD MMM HH:mm')}
              {c.updated_at !== c.created_at && ' (edited)'}
            </Text>
          </Space>
          {isAuthor && !editing && (
            <Space size={4}>
              <Tooltip title="Edit">
                <Button
                  type="text" size="small" icon={<EditOutlined />}
                  onClick={() => {
                    setDraft(c.body);
                    setEditing(true);
                  }}
                />
              </Tooltip>
              <Popconfirm title="Hapus komentar?" onConfirm={() => onDelete(c.id)}>
                <Button type="text" size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            </Space>
          )}
        </div>
        {editing ? (
          <Space direction="vertical" size={6} style={{ width: '100%' }}>
            <Input.TextArea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              autoSize={{ minRows: 2, maxRows: 8 }}
            />
            <Space size={6}>
              <Button
                size="small"
                type="primary"
                loading={saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    await onUpdate(c.id, draft);
                    setEditing(false);
                  } finally {
                    setSaving(false);
                  }
                }}
                disabled={!draft.trim() || draft.trim() === c.body}
              >
                Simpan
              </Button>
              <Button size="small" onClick={() => setEditing(false)}>
                Cancel
              </Button>
            </Space>
          </Space>
        ) : (
          <div style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--ide-ink1, #1d1d1f)' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{c.body}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

function CommentComposer({
  onSubmit,
}: {
  onSubmit: (body: string) => Promise<void> | void;
}) {
  const [body, setBody] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [tab, setTab] = useState<'write' | 'preview'>('write');

  const submit = async () => {
    if (!body.trim()) return;
    setSubmitting(true);
    try {
      await onSubmit(body.trim());
      setBody('');
      setTab('write');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      style={{
        marginTop: 12,
        padding: 10,
        border: '1px solid rgba(0,0,0,0.1)',
        borderRadius: 8,
      }}
    >
      <Tabs
        size="small"
        activeKey={tab}
        onChange={(k) => setTab(k as 'write' | 'preview')}
        items={[
          {
            key: 'write',
            label: <span><EditOutlined /> Tulis</span>,
            children: (
              <Input.TextArea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Tulis komentar… mendukung markdown (**bold**, *italic*, [link](url), code)"
                autoSize={{ minRows: 3, maxRows: 8 }}
              />
            ),
          },
          {
            key: 'preview',
            label: <span><EyeOutlined /> Preview</span>,
            children: (
              <div
                style={{
                  minHeight: 80,
                  padding: 8,
                  background: 'rgba(0,0,0,0.02)',
                  borderRadius: 4,
                  fontSize: 13,
                  lineHeight: 1.5,
                }}
              >
                {body.trim() ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{body}</ReactMarkdown>
                ) : (
                  <Text type="secondary" style={{ fontSize: 12 }}>Belum ada konten</Text>
                )}
              </div>
            ),
          },
        ]}
      />
      <div style={{ marginTop: 8, display: 'flex', justifyContent: 'flex-end' }}>
        <Button
          type="primary"
          icon={<SendOutlined />}
          loading={submitting}
          disabled={!body.trim()}
          onClick={submit}
        >
          Kirim komentar
        </Button>
      </div>
    </div>
  );
}

export function CommentThread({
  comments,
  currentUserId,
  loading,
  onCreate,
  onUpdate,
  onDelete,
}: CommentThreadProps) {
  return (
    <div>
      {loading ? (
        <Text type="secondary">Memuat komentar...</Text>
      ) : comments.length === 0 ? (
        <Empty
          description="Belum ada komentar"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          style={{ padding: '12px 0' }}
        />
      ) : (
        <div>
          {comments.map((c) => (
            <CommentItem
              key={c.id}
              c={c}
              isAuthor={!!currentUserId && c.author_user_id === currentUserId}
              onUpdate={onUpdate}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
      <CommentComposer onSubmit={onCreate} />
    </div>
  );
}
