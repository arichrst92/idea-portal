/**
 * TimesheetsTab — TSK-103+104.
 *
 * List timesheets per placement + month. Click → drawer with daily attendance
 * grid (calendar-style). Submit/Approve/Reject workflow.
 */

import {
  CalendarOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PlusOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Drawer,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useMemo, useState } from 'react';

import {
  approveTimesheet,
  createTimesheet,
  deleteTimesheetItem,
  getTimesheet,
  listPlacements,
  listTimesheets,
  rejectTimesheet,
  submitTimesheet,
  timesheetStatusColor,
  upsertTimesheetItem,
  type Timesheet,
  type TimesheetStatus,
} from '@/api/outsource';

const { Text, Title } = Typography;

const MONTHS_ID = [
  'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
  'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
];

export function TimesheetsTab() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<TimesheetStatus | undefined>();
  const [yearFilter, setYearFilter] = useState<number>(dayjs().year());
  const [monthFilter, setMonthFilter] = useState<number | undefined>();
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [activeTsId, setActiveTsId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const tsQ = useQuery({
    queryKey: ['timesheets', statusFilter, yearFilter, monthFilter],
    queryFn: () => listTimesheets({
      status: statusFilter, year: yearFilter, month: monthFilter,
    }),
  });

  const placementsQ = useQuery({
    queryKey: ['placements-for-ts'],
    queryFn: () => listPlacements({ is_active: true }),
  });

  const createMut = useMutation({
    mutationFn: createTimesheet,
    onSuccess: () => {
      message.success('Timesheet dibuat');
      queryClient.invalidateQueries({ queryKey: ['timesheets'] });
      setCreateOpen(false); createForm.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal create timesheet'),
  });

  const items = tsQ.data ?? [];

  const columns: ColumnsType<Timesheet> = [
    {
      title: 'Period', key: 'period', width: 120,
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.period_label}</Text>
        </Space>
      ),
    },
    {
      title: 'Karyawan / Client', key: 'plac',
      render: (_, r) => (
        <div>
          <div style={{ fontWeight: 600 }}>{r.placement_employee_name}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {r.placement_employee_nik} → {r.placement_client_code} ({r.placement_role})
          </Text>
        </div>
      ),
    },
    {
      title: 'Workdays', dataIndex: 'workdays_count', key: 'wd',
      align: 'center', width: 100,
      render: (v: number) => (
        <Text strong style={{ fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 14 }}>
          {v}
        </Text>
      ),
    },
    {
      title: 'Status', dataIndex: 'status', key: 'st', width: 120,
      render: (s: TimesheetStatus) => {
        const c = timesheetStatusColor(s);
        return <Tag className={c.className}>{c.label}</Tag>;
      },
    },
    {
      title: 'Submitted', dataIndex: 'submitted_at', key: 'sub', width: 110,
      render: (v: string | null) => v ? dayjs(v).format('DD MMM YY') : '—',
    },
    {
      title: 'Approved', dataIndex: 'approved_at', key: 'app', width: 110,
      render: (v: string | null) => v ? dayjs(v).format('DD MMM YY') : '—',
    },
    {
      title: 'Action', key: 'act', width: 100, align: 'center',
      render: (_, r) => (
        <Button size="small" onClick={() => { setActiveTsId(r.id); setDrawerOpen(true); }}>
          Detail
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>Filter:</Text>
          <Select
            allowClear placeholder="All status" style={{ width: 140 }}
            value={statusFilter} onChange={setStatusFilter}
            options={[
              { value: 'DRAFT', label: 'Draft' },
              { value: 'SUBMITTED', label: 'Submitted' },
              { value: 'APPROVED', label: 'Approved' },
              { value: 'REJECTED', label: 'Rejected' },
            ]}
          />
          <InputNumber
            min={2020} max={2099} style={{ width: 100 }}
            value={yearFilter} onChange={(v) => setYearFilter(v ?? dayjs().year())}
          />
          <Select
            allowClear placeholder="All months" style={{ width: 140 }}
            value={monthFilter} onChange={setMonthFilter}
            options={MONTHS_ID.map((m, i) => ({ value: i + 1, label: m }))}
          />
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          New Timesheet
        </Button>
      </div>

      {tsQ.isLoading ? <Spin /> :
        items.length === 0 ? <Empty description="Belum ada timesheet" /> :
          <Table rowKey="id" columns={columns} dataSource={items} size="small" pagination={{ pageSize: 20 }} />}

      <Modal title="New Timesheet" open={createOpen}
        onCancel={() => { setCreateOpen(false); createForm.resetFields(); }}
        footer={null} destroyOnClose
      >
        <Form
          form={createForm} layout="vertical"
          initialValues={{ year: dayjs().year(), month: dayjs().month() + 1 }}
          onFinish={(v) => createMut.mutate(v)}
        >
          <Form.Item label="Placement" name="placement_id" rules={[{ required: true }]}>
            <Select
              showSearch optionFilterProp="label" placeholder="Pilih placement aktif"
              options={(placementsQ.data?.items ?? []).map((p) => ({
                value: p.id,
                label: `${p.employee_nik} → ${p.client_code} (${p.role_at_client})`,
              }))}
            />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Year" name="year" rules={[{ required: true }]}>
              <InputNumber min={2020} max={2099} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Month" name="month" rules={[{ required: true }]}>
              <Select options={MONTHS_ID.map((m, i) => ({ value: i + 1, label: m }))} />
            </Form.Item>
          </div>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Create (Draft)
          </Button>
        </Form>
      </Modal>

      <TimesheetDetailDrawer
        tsId={activeTsId}
        open={drawerOpen}
        onClose={() => { setDrawerOpen(false); setActiveTsId(null); }}
      />
    </div>
  );
}

function TimesheetDetailDrawer({
  tsId, open, onClose,
}: {
  tsId: string | null; open: boolean; onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [rejectForm] = Form.useForm();
  const [rejectOpen, setRejectOpen] = useState(false);

  const q = useQuery({
    queryKey: ['timesheet', tsId],
    queryFn: () => getTimesheet(tsId!),
    enabled: !!tsId && open,
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['timesheet', tsId] });
    queryClient.invalidateQueries({ queryKey: ['timesheets'] });
  };

  const upsertMut = useMutation({
    mutationFn: (data: { work_date: string; is_present: boolean }) =>
      upsertTimesheetItem(tsId!, data),
    onSuccess: invalidate,
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal save'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteTimesheetItem(id),
    onSuccess: invalidate,
  });

  const submitMut = useMutation({
    mutationFn: () => submitTimesheet(tsId!),
    onSuccess: () => { message.success('Timesheet submitted'); invalidate(); },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal submit'),
  });

  const approveMut = useMutation({
    mutationFn: () => approveTimesheet(tsId!),
    onSuccess: () => { message.success('Timesheet approved'); invalidate(); onClose(); },
  });

  const rejectMut = useMutation({
    mutationFn: (reason: string) => rejectTimesheet(tsId!, reason),
    onSuccess: () => {
      message.success('Timesheet rejected — kembali ke employee');
      invalidate(); setRejectOpen(false); rejectForm.resetFields();
    },
  });

  const s = q.data;

  // Build calendar grid for the month
  const calendarDays = useMemo(() => {
    if (!s) return [];
    const firstDay = dayjs(`${s.year}-${String(s.month).padStart(2, '0')}-01`);
    const lastDay = firstDay.endOf('month');
    const days: { date: string; dayNum: number; weekday: number; item: any }[] = [];
    for (let d = 1; d <= lastDay.date(); d++) {
      const dateObj = firstDay.date(d);
      const dateStr = dateObj.format('YYYY-MM-DD');
      const item = s.items.find((i) => i.work_date === dateStr);
      days.push({
        date: dateStr,
        dayNum: d,
        weekday: dateObj.day(),
        item,
      });
    }
    return days;
  }, [s]);

  const isEditable = s && (s.status === 'DRAFT' || s.status === 'REJECTED');

  return (
    <>
      <Drawer
        title={s ? `${s.period_label} — ${s.placement_employee_name}` : 'Timesheet'}
        open={open} onClose={onClose} width={720}
        extra={s && (
          <Space>
            {s.status === 'DRAFT' || s.status === 'REJECTED' ? (
              <Button type="primary" icon={<SendOutlined />}
                loading={submitMut.isPending}
                onClick={() => submitMut.mutate()}
                disabled={s.workdays_count === 0}>
                Submit
              </Button>
            ) : null}
            {s.status === 'SUBMITTED' && (
              <>
                <Button icon={<CheckCircleOutlined />} style={{ color: '#34C759' }}
                  loading={approveMut.isPending}
                  onClick={() => approveMut.mutate()}>
                  Approve
                </Button>
                <Button danger icon={<CloseCircleOutlined />}
                  onClick={() => setRejectOpen(true)}>
                  Reject
                </Button>
              </>
            )}
          </Space>
        )}
      >
        {q.isLoading ? <Spin /> : s && (
          <>
            {/* Info card */}
            <div style={{
              background: 'rgba(0,113,227,0.05)', padding: 12, borderRadius: 8,
              marginBottom: 16,
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>Karyawan</Text>
                  <div>{s.placement_employee_name}</div>
                  <Text type="secondary" style={{ fontSize: 11 }}>{s.placement_employee_nik}</Text>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>Client / Role</Text>
                  <div><strong>{s.placement_client_code}</strong></div>
                  <Text type="secondary" style={{ fontSize: 11 }}>{s.placement_role}</Text>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 11 }}>Workdays</Text>
                  <div style={{ fontSize: 22, fontWeight: 700, color: '#34C759' }}>
                    {s.workdays_count}
                  </div>
                </div>
              </div>
            </div>

            <Tag className={timesheetStatusColor(s.status).className}>
              {timesheetStatusColor(s.status).label}
            </Tag>
            {s.submitted_at && (
              <Text type="secondary" style={{ marginLeft: 8, fontSize: 11 }}>
                Submitted {dayjs(s.submitted_at).format('DD MMM YYYY')}
              </Text>
            )}
            {s.approved_at && (
              <Text type="success" style={{ marginLeft: 8, fontSize: 11 }}>
                · Approved {dayjs(s.approved_at).format('DD MMM YYYY')}
              </Text>
            )}

            <Title level={5} style={{ marginTop: 16 }}>
              <CalendarOutlined /> Daily Attendance
            </Title>
            {isEditable ? (
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
                Klik kotak hari untuk toggle present/absent. Workdays = sum present.
              </Text>
            ) : (
              <Text type="secondary" style={{ fontSize: 11, display: 'block', marginBottom: 8 }}>
                Read-only — status {s.status}.
              </Text>
            )}

            {/* Calendar grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(7, 1fr)',
              gap: 6, marginTop: 8,
            }}>
              {['Min', 'Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab'].map((d) => (
                <div key={d} style={{
                  textAlign: 'center', fontSize: 10, fontWeight: 700,
                  color: 'var(--ide-ink3, #6e6e73)', padding: 4,
                }}>{d}</div>
              ))}
              {/* Empty cells for offset */}
              {calendarDays[0] && Array.from({ length: calendarDays[0].weekday }).map((_, i) => (
                <div key={`empty-${i}`} />
              ))}
              {calendarDays.map((d) => {
                const present = d.item?.is_present;
                const hasItem = !!d.item;
                const isWeekend = d.weekday === 0 || d.weekday === 6;
                return (
                  <button
                    key={d.date}
                    disabled={!isEditable || upsertMut.isPending}
                    onClick={() => {
                      if (hasItem && d.item) {
                        // Toggle: if present → absent, if absent → delete
                        if (present) {
                          upsertMut.mutate({ work_date: d.date, is_present: false });
                        } else {
                          deleteMut.mutate(d.item.id);
                        }
                      } else {
                        upsertMut.mutate({ work_date: d.date, is_present: true });
                      }
                    }}
                    style={{
                      aspectRatio: '1',
                      border: '1px solid',
                      borderColor: hasItem
                        ? (present ? '#34C759' : '#FF3B30')
                        : 'rgba(0,0,0,0.1)',
                      background: hasItem
                        ? (present ? 'rgba(52,199,89,0.15)' : 'rgba(255,59,48,0.1)')
                        : isWeekend ? 'rgba(0,0,0,0.03)' : '#fff',
                      borderRadius: 6,
                      cursor: isEditable ? 'pointer' : 'not-allowed',
                      fontSize: 11, fontWeight: 600,
                      color: hasItem ? (present ? '#34C759' : '#FF3B30') : 'var(--ide-ink2, #6e6e73)',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 2,
                    }}
                  >
                    <span>{d.dayNum}</span>
                    {hasItem && (
                      <span style={{ fontSize: 9 }}>{present ? '✓' : '✗'}</span>
                    )}
                  </button>
                );
              })}
            </div>

            <Space size={20} style={{ marginTop: 12, fontSize: 11 }}>
              <Space size={4}>
                <span style={{ width: 10, height: 10, background: 'rgba(52,199,89,0.4)', display: 'inline-block', borderRadius: 2 }} />
                <Text type="secondary">Present ({s.present_count})</Text>
              </Space>
              <Space size={4}>
                <span style={{ width: 10, height: 10, background: 'rgba(255,59,48,0.3)', display: 'inline-block', borderRadius: 2 }} />
                <Text type="secondary">Absent ({s.absent_count})</Text>
              </Space>
            </Space>
          </>
        )}
      </Drawer>

      <Modal title="Reject Timesheet" open={rejectOpen}
        onCancel={() => { setRejectOpen(false); rejectForm.resetFields(); }}
        footer={null} destroyOnClose
      >
        <Form form={rejectForm} layout="vertical"
          onFinish={(v) => rejectMut.mutate(v.rejection_reason)}
        >
          <Form.Item label="Rejection Reason" name="rejection_reason" rules={[{ required: true, min: 5 }]}>
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 5 }}
              placeholder="Alasan reject — akan kembalikan ke employee untuk perbaikan" />
          </Form.Item>
          <Button type="primary" danger htmlType="submit" loading={rejectMut.isPending} block>
            Reject
          </Button>
        </Form>
      </Modal>
    </>
  );
}
