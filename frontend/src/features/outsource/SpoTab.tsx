/**
 * SpoTab — Client Complaints + SP-O Outsource (TSK-148).
 *
 * Two sub-sections in one tab:
 *  - Client Complaints: log + resolve, severity tag, SP-O count badge.
 *  - SP-O Issuance: list semua SP-O dengan level (SP-O1/O2/O3) auto-assigned.
 *
 * Flow:
 *  1. Operation logs client complaint (severity HIGH/CRITICAL → trigger SP-O).
 *  2. Create SP-O linked ke complaint, level auto-assigned from placement history.
 *  3. SP-O2 → 2-week evaluation period set.
 *  4. SP-O3 → triggers_replacement flag = true (Operation harus replace karyawan).
 */

import {
  AlertOutlined,
  CheckOutlined,
  PlusOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  createComplaint,
  createSpo,
  listComplaints,
  listPlacements,
  listSpo,
  resolveComplaint,
  severityColor,
  spoLevelColor,
  type ClientComplaint,
  type ComplaintSeverity,
  type SpOOutsource,
} from '@/api/outsource';

const { Text, Title } = Typography;

const SEVERITIES: ComplaintSeverity[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

function ComplaintsSection() {
  const queryClient = useQueryClient();
  const [resolvedFilter, setResolvedFilter] = useState<boolean | undefined>(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [spoOpen, setSpoOpen] = useState(false);
  const [activeComplaint, setActiveComplaint] = useState<ClientComplaint | null>(null);
  const [form] = Form.useForm();
  const [spoForm] = Form.useForm();

  const placementsQ = useQuery({
    queryKey: ['placements-for-spo'],
    queryFn: () => listPlacements({ is_active: true }),
  });

  const compQ = useQuery({
    queryKey: ['complaints', resolvedFilter],
    queryFn: () => listComplaints({ resolved: resolvedFilter }),
  });

  const createMut = useMutation({
    mutationFn: createComplaint,
    onSuccess: () => {
      message.success('Complaint dilaporkan');
      queryClient.invalidateQueries({ queryKey: ['complaints'] });
      setCreateOpen(false); form.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal log complaint'),
  });

  const resolveMut = useMutation({
    mutationFn: (id: string) => resolveComplaint(id),
    onSuccess: () => {
      message.success('Complaint resolved');
      queryClient.invalidateQueries({ queryKey: ['complaints'] });
    },
  });

  const spoMut = useMutation({
    mutationFn: createSpo,
    onSuccess: (data) => {
      message.success(`${data.level} di-issue` + (data.triggers_replacement ? ' — REPLACEMENT REQUIRED' : ''));
      queryClient.invalidateQueries({ queryKey: ['complaints'] });
      queryClient.invalidateQueries({ queryKey: ['spo'] });
      setSpoOpen(false); spoForm.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal issue SP-O'),
  });

  const items = compQ.data ?? [];

  const columns: ColumnsType<ClientComplaint> = [
    {
      title: 'Date', dataIndex: 'complaint_date', key: 'date', width: 110,
      render: (v: string) => dayjs(v).format('DD MMM YY'),
    },
    {
      title: 'Karyawan / Client', key: 'plac',
      render: (_, r) => (
        <div>
          <div style={{ fontWeight: 600 }}>{r.placement_employee_name}</div>
          <Text type="secondary" style={{ fontSize: 11 }}>
            {r.placement_employee_nik} → {r.placement_client_code}
          </Text>
        </div>
      ),
    },
    {
      title: 'Severity', dataIndex: 'severity', key: 'sev', width: 100,
      render: (v: ComplaintSeverity) => (
        <Tag style={{ background: 'transparent', borderColor: severityColor(v), color: severityColor(v) }}>
          {v}
        </Tag>
      ),
    },
    {
      title: 'Description', dataIndex: 'description', key: 'desc',
      ellipsis: { showTitle: true },
      render: (v: string) => <Tooltip title={v}><Text style={{ fontSize: 12 }}>{v}</Text></Tooltip>,
    },
    {
      title: 'SP-O', dataIndex: 'spo_count', key: 'spo', width: 70, align: 'center',
      render: (n: number) =>
        n > 0 ? <Tag color="purple">{n}</Tag> : <Text type="secondary" style={{ fontSize: 11 }}>—</Text>,
    },
    {
      title: 'Status', key: 'status', width: 110,
      render: (_, r) => (
        r.resolved_at
          ? <Tag color="green">Resolved {dayjs(r.resolved_at).format('DD MMM')}</Tag>
          : <Tag color="orange">Open</Tag>
      ),
    },
    {
      title: 'Logged By', dataIndex: 'logged_by_nik', key: 'logger', width: 110,
      render: (v: string | null) => <Text style={{ fontSize: 11 }}>{v ?? '—'}</Text>,
    },
    {
      title: 'Actions', key: 'act', width: 220, align: 'center',
      render: (_, r) => (
        <Space size={4}>
          {!r.resolved_at && (
            <Tooltip title="Mark resolved">
              <Button size="small" icon={<CheckOutlined />} onClick={() => resolveMut.mutate(r.id)} />
            </Tooltip>
          )}
          <Button
            size="small" danger icon={<WarningOutlined />}
            onClick={() => {
              setActiveComplaint(r);
              spoForm.setFieldsValue({
                placement_id: r.placement_id,
                triggered_by_complaint_id: r.id,
                issued_date: dayjs().format('YYYY-MM-DD'),
                reason: `Triggered by complaint: ${r.description.substring(0, 100)}`,
              });
              setSpoOpen(true);
            }}
          >
            Issue SP-O
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>Show:</Text>
          <Select
            value={resolvedFilter} onChange={setResolvedFilter}
            style={{ width: 140 }}
            options={[
              { value: false, label: 'Open only' },
              { value: true, label: 'Resolved' },
              { value: undefined as any, label: 'All' },
            ]}
          />
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Log Complaint
        </Button>
      </div>

      {compQ.isLoading ? <Spin /> :
        items.length === 0 ? <Empty description="Belum ada complaint" /> :
          <Table rowKey="id" columns={columns} dataSource={items} size="small" />}

      <Modal title="Log Client Complaint" open={createOpen}
        onCancel={() => { setCreateOpen(false); form.resetFields(); }}
        footer={null} destroyOnClose width={560}
      >
        <Form form={form} layout="vertical"
          initialValues={{ complaint_date: dayjs().format('YYYY-MM-DD'), severity: 'MEDIUM' }}
          onFinish={(v) => createMut.mutate(v)}
        >
          <Form.Item label="Placement" name="placement_id" rules={[{ required: true }]}>
            <Select
              showSearch optionFilterProp="label" placeholder="Pilih placement aktif"
              options={(placementsQ.data?.items ?? []).map((p) => ({
                value: p.id,
                label: `${p.employee_nik} ${p.employee_name} → ${p.client_code}`,
              }))}
            />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <Form.Item label="Date" name="complaint_date" rules={[{ required: true }]}>
              <Input placeholder="YYYY-MM-DD" />
            </Form.Item>
            <Form.Item label="Severity" name="severity">
              <Select options={SEVERITIES.map((s) => ({ value: s, label: s }))} />
            </Form.Item>
          </div>
          <Form.Item label="Description" name="description" rules={[{ required: true, min: 10 }]}>
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }}
              placeholder="Detail keluhan dari client (min 10 char)" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending} block>
            Log Complaint
          </Button>
        </Form>
      </Modal>

      <Modal title={`Issue SP-O — ${activeComplaint?.placement_employee_name}`}
        open={spoOpen} onCancel={() => { setSpoOpen(false); spoForm.resetFields(); }}
        footer={null} destroyOnClose width={560}
      >
        <Form form={spoForm} layout="vertical" onFinish={(v) => spoMut.mutate(v)}>
          <Form.Item name="placement_id" hidden><Input /></Form.Item>
          <Form.Item name="triggered_by_complaint_id" hidden><Input /></Form.Item>
          <div style={{ background: 'rgba(255,149,0,0.08)', padding: 10, borderRadius: 6, marginBottom: 14 }}>
            <Text style={{ fontSize: 12 }}>
              <AlertOutlined /> Level akan auto-assigned dari history placement ini:
              <br />
              No prior → <strong>SP-O1</strong> (warning) ·
              Has SP-O1 → <strong>SP-O2</strong> (2-week eval) ·
              Has SP-O2 → <strong>SP-O3</strong> (replacement required)
            </Text>
          </div>
          <Form.Item label="Issued Date" name="issued_date" rules={[{ required: true }]}>
            <Input placeholder="YYYY-MM-DD" />
          </Form.Item>
          <Form.Item label="Reason" name="reason" rules={[{ required: true, min: 10 }]}>
            <Input.TextArea autoSize={{ minRows: 3, maxRows: 6 }} />
          </Form.Item>
          <Button type="primary" danger htmlType="submit" loading={spoMut.isPending} block>
            Issue SP-O
          </Button>
        </Form>
      </Modal>
    </div>
  );
}

function SpoSection() {
  const q = useQuery({
    queryKey: ['spo'],
    queryFn: () => listSpo(),
  });

  const items = q.data ?? [];

  const columns: ColumnsType<SpOOutsource> = [
    {
      title: 'Level', dataIndex: 'level', key: 'level', width: 90,
      render: (v: any) => (
        <Tag style={{
          background: spoLevelColor(v), color: 'white', fontWeight: 700,
          borderColor: spoLevelColor(v),
        }}>{v}</Tag>
      ),
    },
    {
      title: 'Issued', dataIndex: 'issued_date', key: 'iss', width: 110,
      render: (v: string) => dayjs(v).format('DD MMM YY'),
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
      title: 'Reason', dataIndex: 'reason', key: 'reason',
      ellipsis: { showTitle: true },
      render: (v: string) => <Tooltip title={v}><Text style={{ fontSize: 12 }}>{v}</Text></Tooltip>,
    },
    {
      title: 'Eval End', dataIndex: 'evaluation_end_date', key: 'eval', width: 110,
      render: (v: string | null) => v ? (
        <Tooltip title="SP-O2 2-week evaluation deadline">
          <Text style={{ fontSize: 11, color: dayjs(v).isBefore(dayjs()) ? '#FF3B30' : 'var(--ide-ink2, #6e6e73)' }}>
            {dayjs(v).format('DD MMM YY')}
          </Text>
        </Tooltip>
      ) : '—',
    },
    {
      title: 'Replacement', dataIndex: 'triggers_replacement', key: 'rep', width: 130, align: 'center',
      render: (v: boolean) => v ? (
        <Tag color="purple" style={{ fontWeight: 700 }}>🔁 REQUIRED</Tag>
      ) : <Text type="secondary" style={{ fontSize: 11 }}>—</Text>,
    },
  ];

  return (
    <div>
      <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 12 }}>
        SP-O history per placement. Auto-assigned: SP-O1 → SP-O2 (2-week eval) → SP-O3 (replacement required).
      </Text>
      {q.isLoading ? <Spin /> :
        items.length === 0 ? <Empty description="Belum ada SP-O di-issue" /> :
          <Table rowKey="id" columns={columns} dataSource={items} size="small" />}
    </div>
  );
}

export function SpoTab() {
  return (
    <div>
      <Title level={5} style={{ marginBottom: 12 }}>Client Complaints &amp; SP-O Outsource</Title>
      <Tabs
        defaultActiveKey="complaints"
        size="small"
        items={[
          { key: 'complaints', label: '📢 Complaints', children: <ComplaintsSection /> },
          { key: 'spo', label: '⚠️ SP-O History', children: <SpoSection /> },
        ]}
      />
    </div>
  );
}
