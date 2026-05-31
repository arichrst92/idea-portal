/**
 * AttendanceTab — TSK-047 (EP-05).
 *
 * Operation input monthly attendance per karyawan untuk 1 periode.
 *
 * Flow:
 *  1. Pilih periode (dropdown — only DRAFT yang editable).
 *  2. Tabel daftar karyawan + cell editable (days_present, days_absent_paid,
 *     days_absent_unpaid, overtime_hours, notes).
 *  3. Save changes button → bulk upsert ke backend.
 *  4. Completeness indicator (X/Y employees submitted).
 *  5. Period non-DRAFT → table read-only.
 *
 * Edge cases per NC-OP-007/008:
 *   - Sum days > working_days → backend reject 422 → toast error.
 *   - Period locked → backend reject 409 → banner warning.
 */

import {
  ClockCircleOutlined,
  SaveOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Empty,
  InputNumber,
  Input,
  Progress,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { useMemo, useState } from 'react';

import {
  bulkUpsertAttendance,
  listAttendance,
  listPeriods,
  periodLabel,
  periodStatusColor,
  type AttendanceRow,
  type AttendanceUpsertRow,
} from '@/api/payroll';
import { message } from '@/lib/notify';

const { Text } = Typography;

interface EditableRow extends AttendanceRow {
  // Local-only — original values to detect dirty rows
  _dirty?: boolean;
}

export function AttendanceTab() {
  const queryClient = useQueryClient();
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | undefined>();
  const [editBuffer, setEditBuffer] = useState<Record<string, EditableRow>>({});

  // ─── Queries ────────────────────────────────────────────────────

  const periodsQ = useQuery({
    queryKey: ['payroll-periods'],
    queryFn: listPeriods,
  });

  const attendanceQ = useQuery({
    queryKey: ['attendance', selectedPeriodId],
    queryFn: () => listAttendance(selectedPeriodId!),
    enabled: !!selectedPeriodId,
  });

  // ─── Mutations ──────────────────────────────────────────────────

  const saveMut = useMutation({
    mutationFn: (rows: AttendanceUpsertRow[]) =>
      bulkUpsertAttendance(selectedPeriodId!, rows),
    onSuccess: (data) => {
      message.success(`${data.length} record attendance disimpan`);
      setEditBuffer({});
      queryClient.invalidateQueries({ queryKey: ['attendance', selectedPeriodId] });
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail?.message ?? 'Gagal simpan attendance';
      message.error(detail);
    },
  });

  // ─── Derived ────────────────────────────────────────────────────

  const data = attendanceQ.data;
  const isLocked = data?.period_status !== 'DRAFT';
  const dirtyCount = Object.keys(editBuffer).length;
  const completenessPct = useMemo(() => {
    if (!data || data.total_active_employees === 0) return 0;
    return Math.round((data.submitted_count / data.total_active_employees) * 100);
  }, [data]);

  // Combine API rows + edit buffer (buffer wins for display)
  const displayRows = useMemo<EditableRow[]>(() => {
    if (!data) return [];
    return data.items.map((r) => editBuffer[r.id] ?? r);
  }, [data, editBuffer]);

  // ─── Handlers ───────────────────────────────────────────────────

  const updateCell = (rowId: string, field: keyof AttendanceRow, value: any) => {
    if (isLocked) return;
    const original = data?.items.find((r) => r.id === rowId);
    if (!original) return;
    setEditBuffer((prev) => ({
      ...prev,
      [rowId]: {
        ...(prev[rowId] ?? original),
        [field]: value,
        _dirty: true,
      },
    }));
  };

  const handleSave = () => {
    if (dirtyCount === 0) {
      message.info('Tidak ada perubahan untuk disimpan');
      return;
    }
    const rows: AttendanceUpsertRow[] = Object.values(editBuffer).map((r) => ({
      employee_id: r.employee_id,
      days_present: r.days_present,
      days_absent_paid: r.days_absent_paid,
      days_absent_unpaid: r.days_absent_unpaid,
      overtime_hours: parseFloat(String(r.overtime_hours)) || 0,
      notes: r.notes,
    }));
    saveMut.mutate(rows);
  };

  const handleDiscard = () => {
    setEditBuffer({});
    message.info('Perubahan dibatalkan');
  };

  // ─── Columns ────────────────────────────────────────────────────

  const columns: ColumnsType<EditableRow> = [
    {
      title: 'NIK',
      dataIndex: 'employee_nik',
      width: 100,
      render: (v) => (
        <Text style={{ fontFamily: 'var(--ide-font-mono)', fontSize: 12 }}>{v ?? '—'}</Text>
      ),
    },
    {
      title: 'Nama',
      dataIndex: 'employee_name',
      width: 180,
      render: (v) => <Text strong>{v ?? '—'}</Text>,
    },
    {
      title: 'Dept',
      dataIndex: 'department_name',
      width: 120,
      render: (v) => <Text type="secondary">{v ?? '—'}</Text>,
    },
    {
      title: <Tooltip title="Hari kerja masuk">Hadir</Tooltip>,
      dataIndex: 'days_present',
      width: 90,
      align: 'right',
      render: (v: number, row) => (
        <InputNumber
          value={v}
          min={0}
          max={31}
          size="small"
          style={{ width: '100%' }}
          disabled={isLocked}
          onChange={(val) => updateCell(row.id, 'days_present', val ?? 0)}
        />
      ),
    },
    {
      title: <Tooltip title="Hari cuti berbayar (paid leave)">Cuti</Tooltip>,
      dataIndex: 'days_absent_paid',
      width: 90,
      align: 'right',
      render: (v: number, row) => (
        <InputNumber
          value={v}
          min={0}
          max={31}
          size="small"
          style={{ width: '100%' }}
          disabled={isLocked}
          onChange={(val) => updateCell(row.id, 'days_absent_paid', val ?? 0)}
        />
      ),
    },
    {
      title: <Tooltip title="Hari alpha (tidak berbayar)">Alpha</Tooltip>,
      dataIndex: 'days_absent_unpaid',
      width: 90,
      align: 'right',
      render: (v: number, row) => (
        <InputNumber
          value={v}
          min={0}
          max={31}
          size="small"
          style={{ width: '100%' }}
          disabled={isLocked}
          onChange={(val) => updateCell(row.id, 'days_absent_unpaid', val ?? 0)}
        />
      ),
    },
    {
      title: <Tooltip title="Jam lembur (overtime)">OT (jam)</Tooltip>,
      dataIndex: 'overtime_hours',
      width: 100,
      align: 'right',
      render: (v: string, row) => (
        <InputNumber
          value={parseFloat(String(v)) || 0}
          min={0}
          max={300}
          step={0.5}
          precision={2}
          size="small"
          style={{ width: '100%' }}
          disabled={isLocked}
          onChange={(val) => updateCell(row.id, 'overtime_hours', String(val ?? 0))}
        />
      ),
    },
    {
      title: 'Catatan',
      dataIndex: 'notes',
      ellipsis: true,
      render: (v: string | null, row) => (
        <Input
          value={v ?? ''}
          size="small"
          placeholder="Optional"
          disabled={isLocked}
          onChange={(e) => updateCell(row.id, 'notes', e.target.value || null)}
        />
      ),
    },
    {
      title: 'Status',
      width: 70,
      render: (_: any, row) => {
        if (row._dirty) {
          return <Tag color="orange">Edited</Tag>;
        }
        return <Tag color="green">Saved</Tag>;
      },
    },
  ];

  // ─── Render ─────────────────────────────────────────────────────

  return (
    <div style={{ padding: 16 }}>
      {/* Period selector + completeness */}
      <div
        style={{
          display: 'flex',
          gap: 16,
          alignItems: 'center',
          marginBottom: 16,
          padding: 16,
          background: 'var(--ide-bg, #F5F5F7)',
          borderRadius: 8,
        }}
      >
        <Space direction="vertical" size={2} style={{ minWidth: 280 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            Periode Payroll
          </Text>
          <Select
            value={selectedPeriodId}
            onChange={setSelectedPeriodId}
            placeholder="Pilih periode..."
            loading={periodsQ.isLoading}
            style={{ width: '100%' }}
            options={(periodsQ.data ?? []).map((p) => ({
              value: p.id,
              label: (
                <Space>
                  {periodLabel(p)}
                  <Tag className={`ide-tag ${periodStatusColor(p.status).className}`}>
                    {periodStatusColor(p.status).label}
                  </Tag>
                </Space>
              ),
            }))}
          />
        </Space>

        {data && (
          <>
            <div style={{ flex: 1 }}>
              <Space size={6} style={{ marginBottom: 4 }}>
                <Text type="secondary" style={{ fontSize: 11 }}>
                  Progress Submit
                </Text>
                <Text style={{ fontSize: 12 }}>
                  <strong>{data.submitted_count}</strong> / {data.total_active_employees} karyawan
                </Text>
              </Space>
              <Progress
                percent={completenessPct}
                size="small"
                status={completenessPct === 100 ? 'success' : 'active'}
              />
            </div>

            <div style={{ textAlign: 'right' }}>
              <Text type="secondary" style={{ fontSize: 11 }}>
                Hari kerja bulan ini
              </Text>
              <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ide-blue)' }}>
                <ClockCircleOutlined /> {data.calendar_working_days}
              </div>
            </div>
          </>
        )}
      </div>

      {/* Locked banner */}
      {data && isLocked && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message={`Periode ${periodLabel({ year: data.period_year, month: data.period_month })} status ${data.period_status}`}
          description="Attendance tidak bisa diubah lagi setelah periode di-lock (NC-OP-008-02). Tetap bisa dilihat read-only."
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Action bar — dirty buffer */}
      {dirtyCount > 0 && !isLocked && (
        <Alert
          type="info"
          showIcon
          message={`${dirtyCount} perubahan belum disimpan`}
          action={
            <Space>
              <Button size="small" onClick={handleDiscard}>
                Batalkan
              </Button>
              <Button
                size="small"
                type="primary"
                icon={<SaveOutlined />}
                loading={saveMut.isPending}
                onClick={handleSave}
              >
                Simpan {dirtyCount} record
              </Button>
            </Space>
          }
          style={{ marginBottom: 16 }}
        />
      )}

      {/* Table */}
      {!selectedPeriodId ? (
        <Empty description="Pilih periode payroll untuk mulai input attendance" />
      ) : attendanceQ.isLoading ? (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <Spin>
            <div style={{ minHeight: 24 }} />
          </Spin>
        </div>
      ) : (
        <Table
          rowKey="id"
          columns={columns}
          dataSource={displayRows}
          pagination={{ pageSize: 25, showSizeChanger: false }}
          size="small"
          locale={{
            emptyText: (
              <Empty
                description={
                  <span>
                    Belum ada attendance untuk periode ini.
                    <br />
                    <Text type="secondary" style={{ fontSize: 11 }}>
                      {data?.missing_count ?? 0} karyawan aktif menunggu data.
                    </Text>
                  </span>
                }
              />
            ),
          }}
        />
      )}
    </div>
  );
}
