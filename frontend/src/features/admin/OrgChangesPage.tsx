/**
 * OrgChangesPage — TSK-197 + TSK-198 (shared history page).
 *
 * Admin view untuk semua org changes — promosi, mutasi, role, salary —
 * dengan filter by type + pagination. Per US-OP-012 AC-05 + US-OP-013 AC-05.
 */

import {
  ArrowUpOutlined,
  HistoryOutlined,
  SwapOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Empty, Pagination, Segmented, Spin, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { apiClient } from '@/api/client';

const { Title, Text } = Typography;

interface OrgChangeItem {
  id: string;
  employee_id: string;
  change_type: string;
  effective_date: string;
  before_snapshot: Record<string, any> | null;
  after_snapshot: Record<string, any> | null;
  reason: string | null;
  approved_by_user_id: string | null;
  initiated_by_user_id: string | null;
  created_at: string;
  employee_name: string | null;
  employee_nik: string | null;
}

interface ListResponse {
  items: OrgChangeItem[];
  total: number;
  page: number;
  page_size: number;
}

const TYPE_META: Record<string, { label: string; color: string; icon: any }> = {
  promosi: { label: 'Promosi', color: 'gold', icon: <ArrowUpOutlined /> },
  mutasi: { label: 'Mutasi', color: 'blue', icon: <SwapOutlined /> },
  role: { label: 'Role', color: 'purple', icon: <UserSwitchOutlined /> },
  salary: { label: 'Salary', color: 'green', icon: <ArrowUpOutlined /> },
};

export default function OrgChangesPage() {
  const navigate = useNavigate();
  const [typeFilter, setTypeFilter] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 25;

  const query = useQuery({
    queryKey: ['org-changes', typeFilter, page],
    queryFn: async () => {
      const params: Record<string, any> = { page, page_size: PAGE_SIZE };
      if (typeFilter) params.change_type = typeFilter;
      const r = await apiClient.get<ListResponse>('/api/v1/org-changes', { params });
      return r.data;
    },
  });

  const renderSnapshot = (snap: Record<string, any> | null): string => {
    if (!snap) return '—';
    const items: string[] = [];
    if (snap.position) items.push(`Pos: ${snap.position}`);
    if (snap.department) items.push(`Dept: ${snap.department}`);
    if (snap.level !== undefined) items.push(`L${snap.level}`);
    if (snap.salary !== undefined) items.push(`Rp ${Number(snap.salary).toLocaleString('id-ID')}`);
    return items.length > 0 ? items.join(' · ') : JSON.stringify(snap).slice(0, 60);
  };

  const columns: ColumnsType<OrgChangeItem> = [
    {
      title: 'Tanggal Efektif',
      dataIndex: 'effective_date',
      width: 130,
      render: (v: string) => dayjs(v).format('DD MMM YYYY'),
    },
    {
      title: 'Karyawan',
      key: 'employee',
      width: 220,
      render: (_, r) => (
        <div
          style={{ cursor: r.employee_nik ? 'pointer' : 'default' }}
          onClick={() => r.employee_nik && navigate(`/employees/${r.employee_nik}`)}
        >
          <Text strong>{r.employee_name ?? '—'}</Text>
          <div style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'monospace' }}>
            {r.employee_nik ?? '—'}
          </div>
        </div>
      ),
    },
    {
      title: 'Tipe',
      dataIndex: 'change_type',
      width: 110,
      render: (v: string) => {
        const meta = TYPE_META[v] ?? { label: v, color: 'default', icon: null };
        return (
          <Tag color={meta.color} icon={meta.icon}>
            {meta.label}
          </Tag>
        );
      },
    },
    {
      title: 'Before',
      dataIndex: 'before_snapshot',
      render: (v) => <Text style={{ fontSize: 12 }}>{renderSnapshot(v)}</Text>,
    },
    {
      title: 'After',
      dataIndex: 'after_snapshot',
      render: (v) => (
        <Text strong style={{ fontSize: 12 }}>
          {renderSnapshot(v)}
        </Text>
      ),
    },
    {
      title: 'Alasan',
      dataIndex: 'reason',
      ellipsis: true,
      render: (v: string | null) => (
        <Text type="secondary" style={{ fontSize: 12 }}>
          {v ?? '—'}
        </Text>
      ),
    },
  ];

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <Title level={3} style={{ margin: 0 }}>
          <HistoryOutlined /> Org Changes History
        </Title>
        <Text type="secondary">
          History semua perubahan organisasi: promosi, mutasi, role assignment, salary adjust.
          Per US-OP-012 + US-OP-013 — immutable audit trail.
        </Text>
      </div>

      <Segmented
        value={typeFilter ?? 'all'}
        onChange={(v) => {
          setTypeFilter(v === 'all' ? undefined : (v as string));
          setPage(1);
        }}
        options={[
          { label: 'Semua', value: 'all' },
          { label: 'Promosi', value: 'promosi' },
          { label: 'Mutasi', value: 'mutasi' },
          { label: 'Role', value: 'role' },
          { label: 'Salary', value: 'salary' },
        ]}
        style={{ marginBottom: 16 }}
      />

      {query.isLoading ? (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <Spin>
            <div style={{ minHeight: 24 }} />
          </Spin>
        </div>
      ) : query.data && query.data.items.length > 0 ? (
        <>
          <Table
            rowKey="id"
            columns={columns}
            dataSource={query.data.items}
            size="middle"
            pagination={false}
          />
          <div style={{ marginTop: 16, textAlign: 'center' }}>
            <Pagination
              current={page}
              pageSize={PAGE_SIZE}
              total={query.data.total}
              onChange={setPage}
              showSizeChanger={false}
            />
          </div>
        </>
      ) : (
        <Empty
          description={
            typeFilter
              ? `Tidak ada org change tipe "${typeFilter}"`
              : 'Belum ada org change tercatat'
          }
          style={{ padding: 60 }}
        />
      )}
    </div>
  );
}
