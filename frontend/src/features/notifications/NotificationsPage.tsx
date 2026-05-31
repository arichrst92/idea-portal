/**
 * NotificationsPage — TSK-057.
 *
 * Full list semua notifikasi user: pagination + filter unread + mark read/all.
 * Visual port dari pattern AppleAlert (compact card list).
 */

import { BellOutlined, CheckOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Empty, Pagination, Segmented, Spin, Typography } from 'antd';
import dayjs from 'dayjs';
import relativeTime from 'dayjs/plugin/relativeTime';
import 'dayjs/locale/id';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  NOTIFICATION_TYPE_META,
  type Notification,
} from '@/api/notifications';
import { message } from '@/lib/notify';

dayjs.extend(relativeTime);
dayjs.locale('id');

const { Title, Text } = Typography;

const PAGE_SIZE = 20;

function NotificationCard({
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
        gap: 16,
        padding: 16,
        background: unread ? 'rgba(0,113,227,0.04)' : 'var(--ide-bg-card, white)',
        border: '1px solid var(--ide-border2, #E8E8ED)',
        borderLeft: unread
          ? '3px solid var(--ide-blue, #0071E3)'
          : '1px solid var(--ide-border2, #E8E8ED)',
        borderRadius: 8,
        cursor: 'pointer',
        marginBottom: 8,
        transition: 'all 0.12s',
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = 'var(--ide-bg, #F5F5F7)')
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.background = unread
          ? 'rgba(0,113,227,0.04)'
          : 'var(--ide-bg-card, white)')
      }
    >
      <div
        style={{
          width: 40,
          height: 40,
          borderRadius: 20,
          background: meta.color + '22',
          color: meta.color,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          flexShrink: 0,
        }}
      >
        {meta.icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 12,
            marginBottom: 4,
          }}
        >
          <Text
            strong
            style={{
              fontSize: 14,
              color: 'var(--ide-ink, #1d1d1f)',
            }}
          >
            {notif.title}
          </Text>
          <Text
            type="secondary"
            style={{
              fontSize: 11,
              flexShrink: 0,
              whiteSpace: 'nowrap',
            }}
          >
            {dayjs(notif.created_at).format('DD MMM YYYY · HH:mm')}
          </Text>
        </div>
        {notif.body && (
          <Text
            style={{
              fontSize: 13,
              color: 'var(--ide-ink2, #6e6e73)',
              display: 'block',
              marginBottom: 4,
            }}
          >
            {notif.body}
          </Text>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span
            style={{
              fontSize: 10,
              padding: '2px 8px',
              borderRadius: 4,
              background: meta.color + '22',
              color: meta.color,
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: 0.5,
            }}
          >
            {meta.label}
          </span>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {dayjs(notif.created_at).fromNow()}
          </Text>
          {unread && (
            <span
              style={{
                fontSize: 10,
                padding: '2px 6px',
                borderRadius: 4,
                background: 'var(--ide-blue, #0071E3)',
                color: 'white',
                fontWeight: 600,
              }}
            >
              BARU
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function NotificationsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<'all' | 'unread'>('all');
  const [page, setPage] = useState(1);

  const listQ = useQuery({
    queryKey: ['notifications-list', filter, page],
    queryFn: () =>
      listNotifications({
        unread_only: filter === 'unread',
        page,
        page_size: PAGE_SIZE,
      }),
  });

  const markReadMut = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list-recent'] });
    },
  });

  const markAllMut = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list-recent'] });
      message.success(
        data.marked_count > 0
          ? `${data.marked_count} notifikasi ditandai sudah dibaca`
          : 'Tidak ada notifikasi unread'
      );
    },
  });

  const handleClick = (n: Notification) => {
    if (n.read_at === null) {
      markReadMut.mutate(n.id);
    }
    if (n.link_url) {
      navigate(n.link_url);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 880, margin: '0 auto' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <BellOutlined
            style={{
              fontSize: 24,
              color: 'var(--ide-blue, #0071E3)',
            }}
          />
          <Title level={3} style={{ margin: 0 }}>
            Notifikasi
          </Title>
          {listQ.data && (
            <Text type="secondary">
              {listQ.data.unread_count} unread · {listQ.data.total} total
            </Text>
          )}
        </div>
        <Button
          icon={<CheckOutlined />}
          onClick={() => markAllMut.mutate()}
          loading={markAllMut.isPending}
          disabled={(listQ.data?.unread_count ?? 0) === 0}
        >
          Tandai semua sudah dibaca
        </Button>
      </div>

      <Segmented
        value={filter}
        onChange={(v) => {
          setFilter(v as 'all' | 'unread');
          setPage(1);
        }}
        options={[
          { label: 'Semua', value: 'all' },
          { label: `Unread${listQ.data ? ` (${listQ.data.unread_count})` : ''}`, value: 'unread' },
        ]}
        style={{ marginBottom: 16 }}
      />

      {listQ.isLoading ? (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <Spin />
        </div>
      ) : listQ.data && listQ.data.items.length > 0 ? (
        <>
          {listQ.data.items.map((n) => (
            <NotificationCard
              key={n.id}
              notif={n}
              onClick={() => handleClick(n)}
            />
          ))}
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <Pagination
              current={page}
              pageSize={PAGE_SIZE}
              total={listQ.data.total}
              onChange={setPage}
              showSizeChanger={false}
            />
          </div>
        </>
      ) : (
        <Empty
          description={
            filter === 'unread'
              ? 'Tidak ada notifikasi unread'
              : 'Belum ada notifikasi'
          }
          style={{ padding: 60 }}
        />
      )}
    </div>
  );
}
