/**
 * Permission Matrix Page — TSK-004.
 *
 * Grid view: roles as columns, permissions as rows (grouped by resource).
 * Executive only (require Direktur Utama or Wakil Direktur Utama).
 * Toggle checkbox → call backend PATCH /admin/roles/{id}/permissions.
 *
 * Performance: optimistic update + invalidate query on success/error.
 */

import { LockOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { App as AntApp, Card, Checkbox, Result, Spin, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo } from 'react';

import {
  getPermissionMatrix,
  toggleRolePermission,
  type PermissionItem,
  type PermissionMatrix,
  type RoleItem,
} from '@/api/admin';
import { useAuthStore } from '@/store/auth';

const { Title, Text, Paragraph } = Typography;

interface MatrixRow {
  key: string;
  resource: string;
  action: string;
  code: string;
  description: string | null;
  // Per-role grant status, keyed by role.id
  grants: Record<string, boolean>;
}

function PermissionMatrixPage() {
  const queryClient = useQueryClient();
  const { notification } = AntApp.useApp();
  const user = useAuthStore((s) => s.user);

  const isExecutive = user?.roles.some(
    (r) => r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA',
  );

  const { data, isLoading, error } = useQuery<PermissionMatrix>({
    queryKey: ['admin', 'permissions', 'matrix'],
    queryFn: getPermissionMatrix,
    enabled: isExecutive,
  });

  const mutation = useMutation({
    mutationFn: ({ roleId, code, grant }: { roleId: string; code: string; grant: boolean }) =>
      toggleRolePermission(roleId, code, grant),
    onSuccess: (result) => {
      notification.success({ message: 'Permission updated', description: result.message });
      queryClient.invalidateQueries({ queryKey: ['admin', 'permissions', 'matrix'] });
    },
    onError: (err: unknown) => {
      const msg =
        typeof err === 'object' && err !== null && 'response' in err
          ? // @ts-expect-error — axios error shape
            err.response?.data?.detail?.message ?? 'Failed to update permission'
          : 'Failed to update permission';
      notification.error({ message: 'Update gagal', description: msg });
    },
  });

  // Build table rows: 1 row per permission, columns per role
  const rows = useMemo<MatrixRow[]>(() => {
    if (!data) return [];
    return data.permissions.map((p) => {
      const grants: Record<string, boolean> = {};
      data.roles.forEach((r) => {
        grants[r.id] = r.permission_ids.includes(p.id);
      });
      return {
        key: p.id,
        resource: p.resource,
        action: p.action,
        code: p.code,
        description: p.description,
        grants,
      };
    });
  }, [data]);

  // Columns: permission info + 1 column per role
  const columns = useMemo<ColumnsType<MatrixRow>>(() => {
    const baseCols: ColumnsType<MatrixRow> = [
      {
        title: 'Resource',
        dataIndex: 'resource',
        key: 'resource',
        fixed: 'left',
        width: 140,
        render: (resource: string) => <Tag color="blue">{resource}</Tag>,
        filters: data
          ? Array.from(new Set(data.permissions.map((p) => p.resource))).map((r) => ({
              text: r,
              value: r,
            }))
          : [],
        onFilter: (value, record) => record.resource === value,
      },
      {
        title: 'Action',
        dataIndex: 'action',
        key: 'action',
        width: 110,
        render: (action: string) => <Tag>{action}</Tag>,
      },
      {
        title: 'Code',
        dataIndex: 'code',
        key: 'code',
        width: 220,
        render: (code: string) => <Text code style={{ fontSize: 11 }}>{code}</Text>,
      },
    ];

    const roleCols: ColumnsType<MatrixRow> = (data?.roles ?? []).map((r: RoleItem) => ({
      title: (
        <div style={{ textAlign: 'center', fontSize: 11, lineHeight: 1.3 }}>
          <div style={{ fontWeight: 700 }}>{r.code}</div>
          <div style={{ color: '#86868B', fontWeight: 400 }}>L{r.level}</div>
        </div>
      ),
      dataIndex: ['grants', r.id],
      key: r.id,
      align: 'center' as const,
      width: 90,
      render: (granted: boolean, record: MatrixRow) => (
        <Checkbox
          checked={granted}
          disabled={mutation.isPending || (r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA')}
          onChange={(e) => {
            mutation.mutate({ roleId: r.id, code: record.code, grant: e.target.checked });
          }}
        />
      ),
    }));

    return [...baseCols, ...roleCols];
  }, [data, mutation]);

  if (!isExecutive) {
    return (
      <div style={{ padding: 40 }}>
        <Result
          status="403"
          icon={<LockOutlined />}
          title="403 — Executive only"
          subTitle="Halaman ini hanya untuk Direktur Utama atau Wakil Direktur Utama."
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div style={{ padding: 80, textAlign: 'center' }}>
        <Spin size="large" tip="Loading permission matrix..." />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ padding: 40 }}>
        <Result
          status="error"
          title="Gagal load permission matrix"
          subTitle={String(error)}
        />
      </div>
    );
  }

  return (
    <div style={{ padding: '24px 32px' }}>
      <Title level={2} style={{ marginBottom: 4 }}>
        🔐 Permission Matrix
      </Title>
      <Paragraph type="secondary">
        Manage role × permission mappings. Centang/uncheck untuk grant/revoke.
        Perubahan langsung di-audit log dengan persona explicit (NC-EX-005).
      </Paragraph>

      <Card style={{ marginBottom: 16 }} size="small">
        <Text type="secondary" style={{ fontSize: 12 }}>
          ℹ️ Permission Direktur Utama & Wakil Direktur Utama di-lock (disabled checkbox)
          untuk mencegah lock-out scenario. Total {data.permissions.length} permissions ×{' '}
          {data.roles.length} roles.
        </Text>
      </Card>

      <Table<MatrixRow>
        columns={columns}
        dataSource={rows}
        rowKey="key"
        pagination={false}
        scroll={{ x: 'max-content', y: 600 }}
        size="small"
        sticky
      />
    </div>
  );
}

export default PermissionMatrixPage;
