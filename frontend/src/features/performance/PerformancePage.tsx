/**
 * Performance Page — TSK-021.
 * Combined view: Assessment scoring + OKR + Warning Letters tabs.
 */

import { PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  DatePicker,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Progress,
  Select,
  Spin,
  Tabs,
  Tag,
  message,
} from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';

import { listDepartments, listEmployees } from '@/api/organization';
import {
  type Assessment,
  checkThreshold,
  createConfig,
  createObjective,
  createPeriod,
  issueWarningLetter,
  listAssessments,
  listConfigs,
  listObjectives,
  listPeriods,
  listWarningLetters,
  type Period,
  spLevelColor,
  submitAssessment,
  thresholdColor,
  updateKeyResult,
} from '@/api/assessment';

const { TextArea } = Input;

function formatDate(value: string | null): string {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('id-ID', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

// ─── ASSESSMENTS TAB ─────────────────────────────────────────────

function AssessmentsTab() {
  const queryClient = useQueryClient();
  const [periodFilter, setPeriodFilter] = useState<string | undefined>();
  const [submitOpen, setSubmitOpen] = useState(false);

  const periodsQuery = useQuery({ queryKey: ['periods'], queryFn: listPeriods });
  const assessQuery = useQuery({
    queryKey: ['assessments', periodFilter],
    queryFn: () => listAssessments({ period_id: periodFilter, page_size: 100 }),
  });

  const items = assessQuery.data?.items || [];
  const greenCount = items.filter((a) => a.threshold_flag === 'GREEN').length;
  const yellowCount = items.filter((a) => a.threshold_flag === 'YELLOW').length;
  const orangeCount = items.filter((a) => a.threshold_flag === 'ORANGE').length;
  const redCount = items.filter((a) => a.threshold_flag === 'RED').length;

  return (
    <div>
      <div
        style={{
          display: 'flex',
          gap: 10,
          marginBottom: 14,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <Select
          placeholder="All Periods"
          style={{ width: 200 }}
          allowClear
          value={periodFilter}
          onChange={setPeriodFilter}
          options={(periodsQuery.data || []).map((p) => ({
            value: p.id,
            label: `${p.year}-${String(p.month).padStart(2, '0')}${p.is_closed ? ' (closed)' : ''}`,
          }))}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setSubmitOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
        >
          Submit Assessment
        </Button>
        <PeriodAdminWidget />
      </div>

      {/* KPI Distribution */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-green)' }}>
            {greenCount}
          </div>
          <div className="ide-kpi-lbl">Green (≥70)</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: '#FFD60A' }}>
            {yellowCount}
          </div>
          <div className="ide-kpi-lbl">Yellow (60-69)</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-orange)' }}>
            {orangeCount}
          </div>
          <div className="ide-kpi-lbl">Orange (50-59)</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-red)' }}>
            {redCount}
          </div>
          <div className="ide-kpi-lbl">Red (&lt;50)</div>
        </div>
      </div>

      {/* Table */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1.6fr 1fr 0.8fr 0.8fr 1fr 0.8fr',
            gap: 12,
            padding: '12px 20px',
            background: 'var(--ide-bg)',
            borderBottom: '1px solid var(--ide-border)',
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: 0.8,
          }}
        >
          <div>Karyawan</div>
          <div>Period</div>
          <div style={{ textAlign: 'right' }}>OKR Score</div>
          <div style={{ textAlign: 'right' }}>Weighted</div>
          <div style={{ textAlign: 'right' }}>Final</div>
          <div>Flag</div>
        </div>

        {assessQuery.isLoading && (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        )}

        {assessQuery.data && items.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="Belum ada assessment"
            style={{ padding: '40px 20px' }}
          />
        )}

        {items.map((a) => {
          const color = thresholdColor(a.threshold_flag);
          return (
            <div
              key={a.id}
              style={{
                display: 'grid',
                gridTemplateColumns: '1.6fr 1fr 0.8fr 0.8fr 1fr 0.8fr',
                gap: 12,
                padding: '14px 20px',
                borderBottom: '1px solid var(--ide-border2)',
                fontSize: 13,
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{ fontWeight: 700 }}>{a.employee_name}</div>
                <div
                  style={{
                    fontSize: 11,
                    color: 'var(--ide-ink3)',
                    fontFamily: 'var(--ide-font-mono)',
                  }}
                >
                  {a.employee_nik} · {a.department_name}
                </div>
              </div>
              <div style={{ fontSize: 12, color: 'var(--ide-ink2)' }}>{a.period_label}</div>
              <div
                style={{
                  textAlign: 'right',
                  fontFamily: 'var(--ide-font-mono)',
                  fontWeight: 600,
                }}
              >
                {a.okr_score ? Number(a.okr_score).toFixed(1) : '—'}
              </div>
              <div
                style={{
                  textAlign: 'right',
                  fontFamily: 'var(--ide-font-mono)',
                  fontWeight: 600,
                }}
              >
                {a.weighted_score ? Number(a.weighted_score).toFixed(1) : '—'}
              </div>
              <div
                style={{
                  textAlign: 'right',
                  fontFamily: 'var(--ide-font-mono)',
                  fontSize: 16,
                  fontWeight: 800,
                  color: color.hex,
                }}
              >
                {a.final_score ? Number(a.final_score).toFixed(2) : '—'}
              </div>
              <div>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: 20,
                    background: color.soft,
                    color: color.hex,
                  }}
                >
                  ● {color.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <SubmitAssessmentModal
        open={submitOpen}
        onClose={() => setSubmitOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['assessments'] })}
      />
    </div>
  );
}

function PeriodAdminWidget() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);

  const mutation = useMutation({
    mutationFn: ({ year, month }: { year: number; month: number }) => createPeriod(year, month),
    onSuccess: () => {
      message.success('Period dibuat');
      queryClient.invalidateQueries({ queryKey: ['periods'] });
      setCreating(false);
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal create period'),
  });

  return (
    <>
      <Button onClick={() => setCreating(true)}>+ New Period</Button>
      <Modal
        title="Create Assessment Period"
        open={creating}
        onCancel={() => setCreating(false)}
        onOk={() => {
          const now = new Date();
          mutation.mutate({ year: now.getFullYear(), month: now.getMonth() + 1 });
        }}
        confirmLoading={mutation.isPending}
      >
        <p>Buat period untuk bulan ini ({new Date().getFullYear()}-{String(new Date().getMonth() + 1).padStart(2, '0')})?</p>
      </Modal>
    </>
  );
}

function SubmitAssessmentModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const empQuery = useQuery({
    queryKey: ['employees-assess'],
    queryFn: () => listEmployees({ page_size: 200 }),
    enabled: open,
  });
  const periodsQuery = useQuery({ queryKey: ['periods'], queryFn: listPeriods, enabled: open });
  const configsQuery = useQuery({ queryKey: ['configs'], queryFn: listConfigs, enabled: open });

  const selectedEmpId = Form.useWatch('employee_id', form);
  const selectedEmp = empQuery.data?.items.find((e) => e.id === selectedEmpId);
  const config = configsQuery.data?.find(
    (c) => c.department_name === selectedEmp?.department_name,
  );
  const items = config?.items || [];

  const mutation = useMutation({
    mutationFn: submitAssessment,
    onSuccess: () => {
      message.success('Assessment submitted');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal submit'),
  });

  return (
    <Modal
      title="Submit Monthly Assessment"
      open={open}
      onCancel={onClose}
      width={620}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          type="primary"
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            const weighted_items = items.map((it) => ({
              item_code: it.code,
              score: v[`item_${it.code}`] || 0,
            }));
            mutation.mutate({
              employee_id: v.employee_id,
              period_id: v.period_id,
              okr_score: v.okr_score,
              weighted_items,
              notes: v.notes,
            });
          }}
        >
          Submit
        </Button>,
      ]}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item label="Karyawan" name="employee_id" rules={[{ required: true }]}>
          <Select
            showSearch
            optionFilterProp="label"
            placeholder="Pilih karyawan"
            options={(empQuery.data?.items || []).map((e) => ({
              value: e.id,
              label: `${e.nik} · ${e.full_name} (${e.department_name || 'no dept'})`,
            }))}
          />
        </Form.Item>
        <Form.Item label="Period" name="period_id" rules={[{ required: true }]}>
          <Select
            placeholder="Pilih period"
            options={(periodsQuery.data || []).map((p) => ({
              value: p.id,
              label: `${p.year}-${String(p.month).padStart(2, '0')}${p.is_closed ? ' (closed)' : ''}`,
              disabled: p.is_closed,
            }))}
          />
        </Form.Item>

        {selectedEmp && !config && (
          <Alert
            type="warning"
            message={`Dept ${selectedEmp.department_name} belum punya assessment config. Setup config dulu.`}
            style={{ marginBottom: 14 }}
          />
        )}

        {config && (
          <>
            <Alert
              type="info"
              message={`Bobot: OKR ${config.okr_weight_pct}% + Weighted ${config.weighted_weight_pct}%`}
              style={{ marginBottom: 14 }}
            />
            <Form.Item
              label="OKR Score (0-100)"
              name="okr_score"
              rules={[{ required: true, type: 'number', min: 0, max: 100 }]}
            >
              <InputNumber style={{ width: '100%' }} min={0} max={100} step={0.5} />
            </Form.Item>

            <div style={{ fontWeight: 700, marginBottom: 8 }}>
              Weighted Items (komponen)
            </div>
            {items.map((it) => (
              <Form.Item
                key={it.id}
                label={`${it.name} (bobot ${it.weight_pct}%)`}
                name={`item_${it.code}`}
                rules={[{ required: true, type: 'number', min: 0, max: 100 }]}
              >
                <InputNumber
                  style={{ width: '100%' }}
                  min={0}
                  max={100}
                  step={0.5}
                  placeholder="Score 0-100"
                />
              </Form.Item>
            ))}

            <Form.Item label="Notes (opsional)" name="notes">
              <TextArea rows={3} />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  );
}

// ─── OKR TAB ─────────────────────────────────────────────────────

function OkrTab() {
  const queryClient = useQueryClient();
  const [empFilter, setEmpFilter] = useState<string | undefined>();
  const [createOpen, setCreateOpen] = useState(false);

  const empQuery = useQuery({
    queryKey: ['employees-okr'],
    queryFn: () => listEmployees({ page_size: 200 }),
  });
  const objQuery = useQuery({
    queryKey: ['objectives', empFilter],
    queryFn: () => listObjectives({ employee_id: empFilter }),
  });

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <Select
          placeholder="All Karyawan"
          style={{ width: 280 }}
          allowClear
          showSearch
          optionFilterProp="label"
          value={empFilter}
          onChange={setEmpFilter}
          options={(empQuery.data?.items || []).map((e) => ({
            value: e.id,
            label: `${e.nik} · ${e.full_name}`,
          }))}
        />
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
        >
          Set OKR
        </Button>
      </div>

      {objQuery.isLoading && <Spin />}

      {objQuery.data && objQuery.data.length === 0 && (
        <Empty description="Belum ada OKR" style={{ padding: 40 }} />
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
          gap: 14,
        }}
      >
        {(objQuery.data || []).map((obj) => {
          const avg = obj.avg_progress ? Number(obj.avg_progress) : 0;
          return (
            <div
              key={obj.id}
              style={{
                background: 'var(--ide-surface)',
                border: '1px solid var(--ide-border)',
                borderRadius: 'var(--ide-r)',
                padding: 16,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: 8,
                }}
              >
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{obj.employee_name}</div>
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--ide-ink3)',
                      fontFamily: 'var(--ide-font-mono)',
                    }}
                  >
                    Q{obj.quarter} {obj.year}
                  </div>
                </div>
                <Tag color="blue">{avg.toFixed(0)}%</Tag>
              </div>

              <div
                style={{
                  fontSize: 13,
                  color: 'var(--ide-ink)',
                  marginBottom: 12,
                  fontWeight: 600,
                }}
              >
                {obj.objective}
              </div>

              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: 'var(--ide-ink3)',
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                  marginBottom: 6,
                }}
              >
                Key Results
              </div>

              {obj.key_results.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--ide-ink3)' }}>
                  No key results
                </div>
              ) : (
                obj.key_results.map((kr) => (
                  <KeyResultRow
                    key={kr.id}
                    kr={kr}
                    onUpdate={() => queryClient.invalidateQueries({ queryKey: ['objectives'] })}
                  />
                ))
              )}
            </div>
          );
        })}
      </div>

      <CreateOkrModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['objectives'] })}
      />
    </div>
  );
}

function KeyResultRow({ kr, onUpdate }: { kr: any; onUpdate: () => void }) {
  const pct = Number(kr.progress_pct);

  const mutation = useMutation({
    mutationFn: (new_pct: number) => updateKeyResult(kr.id, { progress_pct: new_pct }),
    onSuccess: () => {
      message.success('KR updated');
      onUpdate();
    },
  });

  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 12, marginBottom: 4 }}>{kr.description}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <Progress percent={pct} size="small" style={{ flex: 1 }} />
        <InputNumber
          size="small"
          min={0}
          max={100}
          value={pct}
          onChange={(v) => v !== null && mutation.mutate(v)}
          style={{ width: 70 }}
        />
      </div>
    </div>
  );
}

function CreateOkrModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const empQuery = useQuery({
    queryKey: ['employees-okr-create'],
    queryFn: () => listEmployees({ page_size: 200 }),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: createObjective,
    onSuccess: () => {
      message.success('OKR objective created');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal create OKR'),
  });

  return (
    <Modal
      title="Set OKR Objective"
      open={open}
      onCancel={onClose}
      width={620}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          type="primary"
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            const krs = (v.key_results || '')
              .split('\n')
              .map((s: string) => s.trim())
              .filter(Boolean)
              .map((d: string) => ({ description: d }));
            mutation.mutate({
              employee_id: v.employee_id,
              year: v.year,
              quarter: v.quarter,
              objective: v.objective,
              key_results: krs,
            });
          }}
        >
          Submit
        </Button>,
      ]}
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        initialValues={{
          year: new Date().getFullYear(),
          quarter: Math.ceil((new Date().getMonth() + 1) / 3),
        }}
      >
        <Form.Item label="Karyawan" name="employee_id" rules={[{ required: true }]}>
          <Select
            showSearch
            optionFilterProp="label"
            options={(empQuery.data?.items || []).map((e) => ({
              value: e.id,
              label: `${e.nik} · ${e.full_name}`,
            }))}
          />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="Year" name="year" rules={[{ required: true }]}>
            <InputNumber style={{ width: '100%' }} min={2020} max={2099} />
          </Form.Item>
          <Form.Item label="Quarter" name="quarter" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 1, label: 'Q1' },
                { value: 2, label: 'Q2' },
                { value: 3, label: 'Q3' },
                { value: 4, label: 'Q4' },
              ]}
            />
          </Form.Item>
        </div>
        <Form.Item
          label="Objective"
          name="objective"
          rules={[
            { required: true, message: 'Wajib' },
            { min: 10, message: 'Min 10 karakter' },
          ]}
        >
          <TextArea
            rows={2}
            placeholder="Contoh: Increase API uptime ke 99.9% di Q3"
          />
        </Form.Item>
        <Form.Item
          label="Key Results (satu per baris)"
          name="key_results"
          extra="Setiap baris = 1 key result. Min 1."
        >
          <TextArea
            rows={4}
            placeholder={'Implement monitoring stack\nSetup pager rotation\nWeekly SLA review'}
          />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── SP / Warning Letter TAB ─────────────────────────────────────

function WarningLetterTab() {
  const queryClient = useQueryClient();
  const [empFilter, setEmpFilter] = useState<string | undefined>();
  const [issueOpen, setIssueOpen] = useState(false);
  const [threshOpen, setThreshOpen] = useState(false);

  const empQuery = useQuery({
    queryKey: ['employees-sp'],
    queryFn: () => listEmployees({ page_size: 200 }),
  });
  const spQuery = useQuery({
    queryKey: ['warning-letters', empFilter],
    queryFn: () => listWarningLetters(empFilter),
  });

  return (
    <div>
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <Select
          placeholder="All Karyawan"
          style={{ width: 280 }}
          allowClear
          showSearch
          optionFilterProp="label"
          value={empFilter}
          onChange={setEmpFilter}
          options={(empQuery.data?.items || []).map((e) => ({
            value: e.id,
            label: `${e.nik} · ${e.full_name}`,
          }))}
        />
        <Button onClick={() => setThreshOpen(true)} disabled={!empFilter}>
          Check Threshold
        </Button>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setIssueOpen(true)}
          style={{ background: 'var(--ide-red)', borderColor: 'var(--ide-red)' }}
        >
          Issue SP
        </Button>
      </div>

      {spQuery.isLoading && <Spin />}
      {spQuery.data && spQuery.data.length === 0 && (
        <Empty description="Belum ada Surat Peringatan" style={{ padding: 40 }} />
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 14 }}>
        {(spQuery.data || []).map((sp) => {
          const color = spLevelColor(sp.level);
          return (
            <div
              key={sp.id}
              style={{
                background: 'var(--ide-surface)',
                border: `2px solid ${color.color}`,
                borderRadius: 'var(--ide-r)',
                padding: 16,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  marginBottom: 8,
                }}
              >
                <div
                  style={{
                    fontSize: 22,
                    fontWeight: 800,
                    fontFamily: 'var(--ide-font-mono)',
                    color: color.color,
                  }}
                >
                  {sp.level}
                </div>
                <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>
                  {formatDate(sp.issued_date)}
                </div>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>
                {sp.employee_name}
              </div>
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--ide-ink3)',
                  fontFamily: 'var(--ide-font-mono)',
                  marginBottom: 10,
                }}
              >
                {sp.employee_nik}
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: 'var(--ide-ink2)',
                  background: color.bg,
                  padding: '8px 10px',
                  borderRadius: 'var(--ide-rs)',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {sp.reason}
              </div>
            </div>
          );
        })}
      </div>

      <IssueSpModal
        open={issueOpen}
        onClose={() => setIssueOpen(false)}
        onSuccess={() => queryClient.invalidateQueries({ queryKey: ['warning-letters'] })}
      />
      <ThresholdModal
        employeeId={empFilter}
        open={threshOpen}
        onClose={() => setThreshOpen(false)}
      />
    </div>
  );
}

function IssueSpModal({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const empQuery = useQuery({
    queryKey: ['employees-sp-issue'],
    queryFn: () => listEmployees({ page_size: 200 }),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: issueWarningLetter,
    onSuccess: () => {
      message.success('SP issued');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (err: any) =>
      message.error(err?.response?.data?.detail?.message || 'Gagal issue SP'),
  });

  return (
    <Modal
      title="Issue Surat Peringatan"
      open={open}
      onCancel={onClose}
      width={560}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          danger
          type="primary"
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            mutation.mutate({
              employee_id: v.employee_id,
              level: v.level,
              issued_date: dayjs(v.issued_date).format('YYYY-MM-DD'),
              reason: v.reason,
            });
          }}
        >
          Issue
        </Button>,
      ]}
      destroyOnClose
    >
      <Alert
        type="warning"
        message="SP harus escalating (SP1 → SP2 → SP3). Tidak bisa skip level."
        style={{ marginBottom: 14 }}
      />
      <Form form={form} layout="vertical" initialValues={{ issued_date: dayjs() }}>
        <Form.Item label="Karyawan" name="employee_id" rules={[{ required: true }]}>
          <Select
            showSearch
            optionFilterProp="label"
            options={(empQuery.data?.items || []).map((e) => ({
              value: e.id,
              label: `${e.nik} · ${e.full_name}`,
            }))}
          />
        </Form.Item>
        <Form.Item label="Level" name="level" rules={[{ required: true }]}>
          <Select
            options={[
              { value: 'SP1', label: 'SP1 (First warning)' },
              { value: 'SP2', label: 'SP2 (Second warning)' },
              { value: 'SP3', label: 'SP3 (Final warning → triggers layoff)' },
            ]}
          />
        </Form.Item>
        <Form.Item label="Issued Date" name="issued_date" rules={[{ required: true }]}>
          <DatePicker style={{ width: '100%' }} format="DD MMM YYYY" />
        </Form.Item>
        <Form.Item
          label="Reason (min 20 karakter)"
          name="reason"
          rules={[
            { required: true },
            { min: 20, message: 'Min 20 karakter' },
          ]}
        >
          <TextArea rows={4} placeholder="Jelaskan pelanggaran / kinerja rendah..." />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function ThresholdModal({
  employeeId,
  open,
  onClose,
}: {
  employeeId: string | undefined;
  open: boolean;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ['threshold', employeeId],
    queryFn: () => checkThreshold(employeeId!),
    enabled: open && !!employeeId,
  });

  return (
    <Modal title="Threshold Check" open={open} onCancel={onClose} footer={null} width={560}>
      {query.isLoading && <Spin />}
      {query.data && (
        <div>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>{query.data.employee_name}</div>
            <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>
              {query.data.employee_nik} · {query.data.department_name}
            </div>
          </div>

          {query.data.action_required ? (
            <Alert
              type="error"
              message={`⚠ ACTION REQUIRED: ${query.data.consecutive_low_months} bulan berturut < threshold. Suggested: ${query.data.suggested_sp_level}`}
              style={{ marginBottom: 14 }}
            />
          ) : (
            <Alert
              type="success"
              message={`${query.data.consecutive_low_months} bulan rendah berturut — belum perlu SP`}
              style={{ marginBottom: 14 }}
            />
          )}

          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: 'var(--ide-ink3)',
              textTransform: 'uppercase',
              marginBottom: 8,
            }}
          >
            Recent Scores
          </div>
          {query.data.recent_scores.map((s, i) => {
            const color = thresholdColor(s.flag);
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '8px 12px',
                  borderBottom: '1px solid var(--ide-border2)',
                }}
              >
                <span style={{ fontSize: 13 }}>{s.period}</span>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                  <span
                    style={{
                      fontFamily: 'var(--ide-font-mono)',
                      fontWeight: 700,
                      color: color.hex,
                    }}
                  >
                    {s.final_score?.toFixed(1) || '—'}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: 20,
                      background: color.soft,
                      color: color.hex,
                    }}
                  >
                    {color.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}

// ─── Main Page ───────────────────────────────────────────────────

export default function PerformancePage() {
  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
          Performance Management
        </h2>
        <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
          OKR, Monthly Assessment, dan Surat Peringatan dalam satu dashboard.
        </p>
      </div>

      <Tabs
        defaultActiveKey="assessments"
        items={[
          { key: 'assessments', label: 'Assessments', children: <AssessmentsTab /> },
          { key: 'okr', label: 'OKR', children: <OkrTab /> },
          { key: 'sp', label: 'Surat Peringatan (SP)', children: <WarningLetterTab /> },
        ]}
      />
    </div>
  );
}
