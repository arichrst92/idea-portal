/**
 * ProbationReviewPage — TSK-044.
 *
 * HR/Supervisor view: list semua probation assessment, decide PENDING ones.
 */

import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  DatePicker,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Select,
  Spin,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import { useState } from 'react';

import { apiClient } from '@/api/client';
import { message } from '@/lib/notify';

const { Title, Text } = Typography;

interface Probation {
  id: string;
  employee_id: string;
  employee_name: string | null;
  employee_nik: string | null;
  probation_start: string;
  probation_end: string;
  decision: 'PENDING' | 'PASS' | 'EXTEND' | 'TERMINATE';
  score: string | null;
  notes: string | null;
  extended_to: string | null;
  reviewer_user_id: string | null;
  decided_at: string | null;
  created_at: string;
  days_until_end: number | null;
}

const DECISION_COLOR: Record<string, string> = {
  PENDING: 'orange',
  PASS: 'green',
  EXTEND: 'blue',
  TERMINATE: 'red',
};

export default function ProbationReviewPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<string>('PENDING');
  const [decideTarget, setDecideTarget] = useState<Probation | null>(null);
  const [form] = Form.useForm();

  const query = useQuery({
    queryKey: ['probations', filter],
    queryFn: async () => {
      const r = await apiClient.get<Probation[]>('/api/v1/probation', {
        params: filter !== 'ALL' ? { decision_filter: filter } : {},
      });
      return r.data;
    },
  });

  const decideMut = useMutation({
    mutationFn: async (data: {
      probation_id: string;
      decision: string;
      score?: number | null;
      notes?: string;
      extended_to?: string;
    }) => {
      const r = await apiClient.post(`/api/v1/probation/${data.probation_id}/decide`, {
        decision: data.decision,
        score: data.score ?? null,
        notes: data.notes ?? null,
        extended_to: data.extended_to ?? null,
      });
      return r.data;
    },
    onSuccess: () => {
      message.success('Decision recorded');
      setDecideTarget(null);
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ['probations'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal record decision'),
  });

  const watchDecision = Form.useWatch('decision', form);

  const columns: ColumnsType<Probation> = [
    {
      title: 'Karyawan',
      key: 'emp',
      width: 220,
      render: (_, r) => (
        <div>
          <Text strong>{r.employee_name ?? '—'}</Text>
          <div style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'monospace' }}>
            {r.employee_nik ?? '—'}
          </div>
        </div>
      ),
    },
    {
      title: 'Periode Probation',
      key: 'period',
      width: 200,
      render: (_, r) => (
        <div>
          <div style={{ fontSize: 12 }}>
            {dayjs(r.probation_start).format('DD MMM YYYY')} →{' '}
            {dayjs(r.probation_end).format('DD MMM YYYY')}
          </div>
          {r.days_until_end !== null && (
            <Tag
              color={
                r.days_until_end < 0
                  ? 'red'
                  : r.days_until_end <= 7
                  ? 'orange'
                  : 'default'
              }
              style={{ marginTop: 4, fontSize: 10 }}
            >
              {r.days_until_end < 0
                ? `Overdue ${Math.abs(r.days_until_end)}d`
                : `H-${r.days_until_end}`}
            </Tag>
          )}
        </div>
      ),
    },
    {
      title: 'Decision',
      dataIndex: 'decision',
      width: 110,
      render: (v: string) => <Tag color={DECISION_COLOR[v]}>{v}</Tag>,
    },
    {
      title: 'Score',
      dataIndex: 'score',
      width: 80,
      align: 'center',
      render: (v: string | null) =>
        v ? (
          <Text strong style={{ color: parseFloat(v) >= 60 ? 'var(--ide-green)' : 'var(--ide-red)' }}>
            {parseFloat(v).toFixed(1)}
          </Text>
        ) : (
          '—'
        ),
    },
    {
      title: 'Decided',
      dataIndex: 'decided_at',
      width: 160,
      render: (v: string | null) => (v ? dayjs(v).format('DD MMM YYYY HH:mm') : '—'),
    },
    {
      title: 'Notes',
      dataIndex: 'notes',
      ellipsis: true,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: 'Action',
      key: 'action',
      width: 120,
      render: (_, r) =>
        r.decision === 'PENDING' ? (
          <Button size="small" type="primary" onClick={() => setDecideTarget(r)}>
            Decide
          </Button>
        ) : null,
    },
  ];

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <Title level={3} style={{ margin: 0 }}>
          <ClockCircleOutlined /> Probation Reviews
        </Title>
        <Text type="secondary">
          Per knowledge.md sec.11: probation 3 bulan. Supervisor + HR decide PASS /
          EXTEND / TERMINATE H-7 sebelum probation_end_date.
        </Text>
      </div>

      <Segmented
        value={filter}
        onChange={(v) => setFilter(v as string)}
        options={[
          { label: 'Pending', value: 'PENDING' },
          { label: 'Pass', value: 'PASS' },
          { label: 'Extend', value: 'EXTEND' },
          { label: 'Terminate', value: 'TERMINATE' },
          { label: 'Semua', value: 'ALL' },
        ]}
        style={{ marginBottom: 16 }}
      />

      {query.isLoading ? (
        <Spin>
          <div style={{ minHeight: 24 }} />
        </Spin>
      ) : query.data && query.data.length > 0 ? (
        <Table rowKey="id" columns={columns} dataSource={query.data} size="middle" />
      ) : (
        <Empty description="Tidak ada probation assessment dalam filter ini" />
      )}

      <Modal
        title="Submit Probation Decision"
        open={!!decideTarget}
        onCancel={() => setDecideTarget(null)}
        footer={null}
        destroyOnHidden
      >
        {decideTarget && (
          <>
            <Text strong>{decideTarget.employee_name}</Text>{' '}
            <Text type="secondary">({decideTarget.employee_nik})</Text>
            <div style={{ fontSize: 12, color: 'var(--ide-ink2)', margin: '6px 0 14px' }}>
              Probation: {dayjs(decideTarget.probation_start).format('DD MMM YYYY')} →{' '}
              {dayjs(decideTarget.probation_end).format('DD MMM YYYY')}
            </div>
            <Form
              form={form}
              layout="vertical"
              onFinish={(v) =>
                decideMut.mutate({
                  probation_id: decideTarget.id,
                  decision: v.decision,
                  score: v.score,
                  notes: v.notes,
                  extended_to:
                    v.decision === 'EXTEND' && v.extended_to
                      ? v.extended_to.format('YYYY-MM-DD')
                      : undefined,
                })
              }
            >
              <Form.Item
                label="Decision"
                name="decision"
                rules={[{ required: true, message: 'Pilih decision' }]}
              >
                <Select
                  options={[
                    {
                      value: 'PASS',
                      label: '✓ PASS — lulus probation, status → ACTIVE',
                    },
                    {
                      value: 'EXTEND',
                      label: '↻ EXTEND — perpanjang probation',
                    },
                    {
                      value: 'TERMINATE',
                      label: '✗ TERMINATE — putus hubungan kerja',
                    },
                  ]}
                />
              </Form.Item>
              <Form.Item label="Score (0-100, opsional)" name="score">
                <InputNumber min={0} max={100} style={{ width: '100%' }} />
              </Form.Item>
              {watchDecision === 'EXTEND' && (
                <Form.Item
                  label="Extend Probation Sampai"
                  name="extended_to"
                  rules={[{ required: true, message: 'Tanggal extension wajib' }]}
                >
                  <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
                </Form.Item>
              )}
              <Form.Item label="Notes" name="notes">
                <Input.TextArea
                  rows={3}
                  placeholder="Justifikasi decision, area improvement, dll..."
                />
              </Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                block
                loading={decideMut.isPending}
                icon={
                  watchDecision === 'PASS' ? (
                    <CheckCircleOutlined />
                  ) : watchDecision === 'TERMINATE' ? (
                    <CloseCircleOutlined />
                  ) : (
                    <ClockCircleOutlined />
                  )
                }
                danger={watchDecision === 'TERMINATE'}
              >
                Submit Decision
              </Button>
            </Form>
          </>
        )}
      </Modal>
    </div>
  );
}
