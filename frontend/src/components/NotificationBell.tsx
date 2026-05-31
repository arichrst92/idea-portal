/**
 * NotificationBell — TSK-057.
 *
 * Bell icon di AppShell header dengan badge unread count.
 * Click → dropdown panel 10 notifikasi terakhir + "Mark all as read".
 * Click satu notifikasi → mark read + navigate ke link_url.
 *
 * Poll unread-count setiap 30s.
 */

import { BellOutlined, CheckOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Dropdown, Empty, Spin, Typography } from 'antd';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/id';
import { useNavigate } from 'react-router-dom';

import {
  getUnreadCount,
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  NOTIFICATION_TYPE_META,
  type Notification,
} from '@/api/notifications';
import { message } from '@/lib/notify';

dayjs.extend(relativeTime);
dayjs.locale('id');

const { Text } = Typography;

const POLL_MS = 30_000;

function NotificationRow({
  notif,
  onClick,
}: {
  notif: Notification;
  onClick: () => void;
}) {
  const meta = NOTIFICATION_TYPE_META[notif.type] ?? NOTIFICATION_TYPE_META.SYSTEM;
  const unread = notif.read_at === null;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex',
        gap: 12,
        padding: '12px 16px',
        borderBottom: '1px solid var(--ide-border2, #E8E8ED)',
        cursor: 'pointer',
        background: unread ? 'rgba(0,113,227,0.04)' : 'transparent',
        transition: 'background 0.12s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--ide-bg, #F5F5F7)')}
      onMouseLeave={(e) =>
        (e.currentTarget.style.background = unread ? 'rgba(0,113,227,0.04)' : 'transparent')
      }
    >
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: 16,
          background: meta.color + '22',
          color: meta.color,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16,
          flexShrink: 0,
        }}
      >
        {meta.icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
          <Text strong style={{ fontSize: 13, color: 'var(--ide-ink, #1d1d1f)' }}>
            {notif.title}
          </Text>
          {unread && (
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 4,
                background: 'var(--ide-blue, #0071E3)',
                flexShrink: 0,
                marginTop: 6,
              }}
            />
          )}
        </div>
        {notif.body && (
          <div
            style={{
              fontSize: 12,
              color: 'var(--ide-ink2, #6e6e73)',
              marginTop: 2,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
            }}
          >
            {notif.body}
          </div>
        )}
        <Text type="secondary" style={{ fontSize: 11 }}>
          {dayjs(notif.created_at).fromNow()}
        </Text>
      </div>
    </div>
  );
}

export function NotificationBell() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // Unread count — poll
  const unreadQ = useQuery({
    queryKey: ['notifications-unread-count'],
    queryFn: getUnreadCount,
    refetchInterval: POLL_MS,
    refetchOnWindowFocus: true,
  });
  const unread = unreadQ.data?.unread_count ?? 0;

  // List — only fetch on dropdown open (via enabled)
  const listQ = useQuery({
    queryKey: ['notifications-list-recent'],
    queryFn: () => listNotifications({ page: 1, page_size: 10 }),
    staleTime: 10_000,
  });

  const markReadMut = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list-recent'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
    },
  });

  const markAllMut = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list-recent'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
      if (data.marked_count > 0) {
        message.success(`${data.marked_count} notifikasi ditandai sudah dibaca`);
      }
    },
  });

  const handleNotifClick = (n: Notification) => {
    if (n.read_at === null) {
      markReadMut.mutate(n.id);
    }
    if (n.link_url) {
      navigate(n.link_url);
    }
  };

  const dropdownContent = (
    <div
      style={{
        width: 380,
        maxWidth: '90vw',
        background: 'var(--ide-bg-card, white)',
        borderRadius: 8,
        boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
        border: '1px solid var(--ide-border2, #E8E8ED)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '1px solid var(--ide-border2, #E8E8ED)',
        }}
      >
        <Text strong>Notifikasi</Text>
        <Button
          size="small"
          type="link"
          icon={<CheckOutlined />}
          onClick={() => markAllMut.mutate()}
          loading={markAllMut.isPending}
          disabled={unread === 0}
        >
          Tandai semua
        </Button>
      </div>

      {/* List */}
      <div style={{ maxHeight: 440, overflowY: 'auto' }}>
        {listQ.isLoading ? (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        ) : listQ.data && listQ.data.items.length > 0 ? (
          listQ.data.items.map((n) => (
            <NotificationRow
              key={n.id}
              notif={n}
              onClick={() => handleNotifClick(n)}
            />
          ))
        ) : (
          <div style={{ padding: 32 }}>
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="Belum ada notifikasi"
            />
          </div>
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          padding: '8px 16px',
          borderTop: '1px solid var(--ide-border2, #E8E8ED)',
          textAlign: 'center',
        }}
      >
        <Button
          size="small"
          type="link"
          onClick={() => navigate('/notifications')}
        >
          Lihat semua
        </Button>
      </div>
    </div>
  );

  return (
    <Dropdown
      popupRender={() => dropdownContent}
      trigger={['click']}
      placement="bottomRight"
      onOpenChange={(open) => {
        if (open) {
          queryClient.invalidateQueries({ queryKey: ['notifications-list-recent'] });
        }
      }}
    >
      <Badge count={unread} size="small" offset={[-2, 2]}>
        <Button
          type="text"
          icon={<BellOutlined />}
          aria-label={`Notifikasi (${unread} unread)`}
          title="Notifikasi"
        />
      </Badge>
    </Dropdown>
  );
}
