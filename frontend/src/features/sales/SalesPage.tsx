/**
 * Sales Page — TSK-024.
 * Tabs: Pipeline (kanban), Commissions, Targets.
 */

import { CrownOutlined, PlusOutlined, RightOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
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
import { useState } from 'react';

import { listDepartments, listEmployees } from '@/api/organization';
import {
  createLead,
  createTarget,
  getPipeline,
  listCommissions,
  listTargets,
  stageColor,
  transitionLead,
  type LeadListItem,
  type LeadStage,
  NEXT_STAGES,
} from '@/api/sales';

const { TextArea } = Input;

function formatIDR(value: string | null): string {
  if (!value) return '—';
  const n = parseFloat(value);
  if (!isFinite(n)) return value;
  return `Rp ${n.toLocaleString('id-ID')}`;
}

// ─── PIPELINE KANBAN TAB ────────────────────────────────────────

function LeadCard({ lead, onAction }: { lead: LeadListItem; onAction: () => void }) {
  const color = stageColor(lead.stage);
  const [transitOpen, setTransitOpen] = useState(false);

  const nextOptions = NEXT_STAGES[lead.stage];

  return (
    <>
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-rs)',
          padding: 10,
          marginBottom: 8,
          cursor: nextOptions.length > 0 ? 'pointer' : 'default',
          transition: 'all 0.12s',
        }}
        onClick={() => nextOptions.length > 0 && setTransitOpen(true)}
        onMouseEnter={(e) => {
          if (nextOptions.length > 0) {
            e.currentTarget.style.borderColor = color.hex;
            e.currentTarget.style.boxShadow = 'var(--ide-shadow-sm)';
          }
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'var(--ide-border)';
          e.currentTarget.style.boxShadow = 'none';
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--ide-ink)' }}>
            {lead.company_name}
          </div>
          {lead.is_direktur_driven && (
            <CrownOutlined style={{ color: 'var(--ide-purple)', fontSize: 12 }} title="Direktur-driven" />
          )}
        </div>
        {lead.pic_name && (
          <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>{lead.pic_name}</div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
          <span style={{ fontSize: 11, fontFamily: 'var(--ide-font-mono)', fontWeight: 700, color: color.hex }}>
            {formatIDR(lead.estimated_value)}
          </span>
          {lead.days_in_stage !== null && (
            <span style={{ fontSize: 10, color: 'var(--ide-ink3)' }}>{lead.days_in_stage}d</span>
          )}
        </div>
        {lead.assigned_to_nik && (
          <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginTop: 4, fontFamily: 'var(--ide-font-mono)' }}>
            👤 {lead.assigned_to_nik}
          </div>
        )}
      </div>

      <TransitModal
        lead={lead}
        open={transitOpen}
        onClose={() => setTransitOpen(false)}
        onSuccess={onAction}
      />
    </>
  );
}

function TransitModal({
  lead,
  open,
  onClose,
  onSuccess,
}: {
  lead: LeadListItem;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const newStage = Form.useWatch('new_stage', form);
  const showCommission =
    newStage === 'CLOSED_WON' &&
    !lead.is_direktur_driven &&
    lead.assigned_to_nik !== null;

  const mutation = useMutation({
    mutationFn: (d: { new_stage: LeadStage; commission_pct?: number; notes?: string }) =>
      transitionLead(lead.id, d),
    onSuccess: () => {
      message.success('Stage berubah');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal'),
  });

  return (
    <Modal
      title={`Transition Lead — ${lead.company_name}`}
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose}>Batal</Button>,
        <Button
          key="s"
          type="primary"
          loading={mutation.isPending}
          onClick={async () => {
            const v = await form.validateFields();
            mutation.mutate(v);
          }}
        >Lanjut</Button>,
      ]}
      destroyOnClose
    >
      <Form form={form} layout="vertical">
        <Form.Item label="Stage Baru" name="new_stage" rules={[{ required: true }]}>
          <Select
            options={NEXT_STAGES[lead.stage].map((s) => ({
              value: s,
              label: stageColor(s).label,
            }))}
          />
        </Form.Item>
        {showCommission && (
          <Form.Item
            label="Commission % (untuk auto-create SalesCommission)"
            name="commission_pct"
            rules={[{ required: true, type: 'number', min: 0, max: 100 }]}
            extra={`Lead value: ${formatIDR(lead.estimated_value)}. Commission akan auto-create dengan status PENDING.`}
          >
            <InputNumber min={0} max={100} step={0.5} style={{ width: '100%' }} />
          </Form.Item>
        )}
        <Form.Item label="Notes" name="notes">
          <TextArea rows={3} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

function PipelineTab() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const query = useQuery({ queryKey: ['pipeline'], queryFn: getPipeline });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['pipeline'] });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 14, alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 18, alignItems: 'baseline' }}>
          {query.data && (
            <>
              <div>
                <div style={{ fontSize: 10, color: 'var(--ide-ink3)', textTransform: 'uppercase' }}>
                  Total Pipeline
                </div>
                <div style={{ fontSize: 18, fontWeight: 800, fontFamily: 'var(--ide-font-mono)', color: 'var(--ide-blue)' }}>
                  {formatIDR(query.data.total_pipeline_value)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: 'var(--ide-ink3)', textTransform: 'uppercase' }}>
                  Closed Won YTD
                </div>
                <div style={{ fontSize: 18, fontWeight: 800, fontFamily: 'var(--ide-font-mono)', color: 'var(--ide-green)' }}>
                  {formatIDR(query.data.closed_won_value_ytd)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, color: 'var(--ide-ink3)', textTransform: 'uppercase' }}>
                  Total Leads
                </div>
                <div style={{ fontSize: 18, fontWeight: 800, fontFamily: 'var(--ide-font-mono)' }}>
                  {query.data.total_leads}
                </div>
              </div>
            </>
          )}
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateOpen(true)}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
        >
          Add Lead
        </Button>
      </div>

      {query.isLoading && <Spin />}

      {query.data && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(6, minmax(190px, 1fr))',
            gap: 10,
            overflowX: 'auto',
          }}
        >
          {query.data.stages.map((bucket) => {
            const color = stageColor(bucket.stage);
            return (
              <div
                key={bucket.stage}
                style={{
                  background: 'var(--ide-bg)',
                  borderRadius: 'var(--ide-rm)',
                  padding: 10,
                  minHeight: 250,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 700,
                      color: color.hex,
                      textTransform: 'uppercase',
                    }}
                  >
                    {bucket.label}
                  </span>
                  <span
                    style={{
                      fontSize: 10,
                      fontWeight: 700,
                      padding: '1px 7px',
                      borderRadius: 20,
                      background: color.soft,
                      color: color.hex,
                    }}
                  >
                    {bucket.count}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: 'var(--ide-ink3)', marginBottom: 10, fontFamily: 'var(--ide-font-mono)' }}>
                  {formatIDR(bucket.total_value)}
                </div>

                {bucket.leads.length === 0 ? (
                  <div style={{ fontSize: 11, color: 'var(--ide-ink3)', textAlign: 'center', padding: 12 }}>
                    Empty
                  </div>
                ) : (
                  bucket.leads.map((lead) => (
                    <LeadCard key={lead.id} lead={lead} onAction={refresh} />
                  ))
                )}
              </div>
            );
          })}
        </div>
      )}

      <CreateLeadModal open={createOpen} onClose={() => setCreateOpen(false)} onSuccess={refresh} />
    </div>
  );
}

function CreateLeadModal({ open, onClose, onSuccess }: { open: boolean; onClose: () => void; onSuccess: () => void }) {
  const [form] = Form.useForm();
  const empQuery = useQuery({ queryKey: ['emp-lead'], queryFn: () => listEmployees({ page_size: 200 }), enabled: open });

  const mutation = useMutation({
    mutationFn: createLead,
    onSuccess: () => { message.success('Lead created'); form.resetFields(); onSuccess(); onClose(); },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message || 'Gagal'),
  });

  return (
    <Modal
      title="Add New Lead"
      open={open}
      onCancel={onClose}
      width={560}
      footer={[<Button key="c" onClick={onClose}>Batal</Button>,
        <Button key="s" type="primary" loading={mutation.isPending} onClick={async () => {
          const v = await form.validateFields();
          mutation.mutate(v);
        }}>Submit</Button>]}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={{ is_direktur_driven: false }}>
        <Form.Item label="Company Name" name="company_name" rules={[{ required: true }]}>
          <Input placeholder="PT. ABC Indonesia" />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="PIC Name" name="pic_name">
            <Input />
          </Form.Item>
          <Form.Item label="PIC Email" name="pic_email">
            <Input type="email" />
          </Form.Item>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="PIC Phone" name="pic_phone">
            <Input />
          </Form.Item>
          <Form.Item label="Source" name="source">
            <Input placeholder="LinkedIn, referral, etc" />
          </Form.Item>
        </div>
        <Form.Item label="Services" name="services">
          <Input placeholder="Web development, mobile app, consulting" />
        </Form.Item>
        <Form.Item label="Estimated Value (IDR)" name="estimated_value">
          <InputNumber min={0} style={{ width: '100%', fontFamily: 'var(--ide-font-mono)' }} formatter={(v) => v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : ''} parser={(v) => v ? Number(v.replace(/[^0-9]/g, '')) : 0} />
        </Form.Item>
        <Form.Item label="Sales PIC (Assignee)" name="assigned_to_user_id">
          <Select
            allowClear
            showSearch
            optionFilterProp="label"
            options={(empQuery.data?.items || []).map((e) => ({
              value: e.id,
              label: `${e.nik} · ${e.full_name}`,
            }))}
          />
        </Form.Item>
        <Form.Item label="Direktur-driven?" name="is_direktur_driven" valuePropName="checked" extra="Direktur-driven = no commission saat CLOSED_WON">
          <Select options={[{ value: false, label: 'No (sales-driven, eligible commission)' }, { value: true, label: 'Yes (direktur-driven, no commission)' }]} />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── COMMISSIONS TAB ───────────────────────────────────────────

function CommissionsTab() {
  const query = useQuery({ queryKey: ['commissions'], queryFn: () => listCommissions() });
  const items = query.data || [];

  const totalPending = items
    .filter((c) => c.status === 'PENDING')
    .reduce((acc, c) => acc + parseFloat(c.commission_amount), 0);
  const totalPaid = items
    .filter((c) => c.status === 'PAID')
    .reduce((acc, c) => acc + parseFloat(c.commission_amount), 0);

  return (
    <div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 18 }}>
        <div className="ide-kpi">
          <div className="ide-kpi-val">{items.length}</div>
          <div className="ide-kpi-lbl">Total Commissions</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-orange)', fontSize: 16 }}>
            Rp {(totalPending / 1_000_000).toFixed(1)}M
          </div>
          <div className="ide-kpi-lbl">Pending Payment</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-green)', fontSize: 16 }}>
            Rp {(totalPaid / 1_000_000).toFixed(1)}M
          </div>
          <div className="ide-kpi-lbl">Paid (linked to payroll)</div>
        </div>
      </div>

      {query.isLoading && <Spin />}
      {items.length === 0 && <Empty description="Belum ada commission" />}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {items.map((c) => (
          <div key={c.id} style={{ background: 'var(--ide-surface)', border: '1px solid var(--ide-border)', borderRadius: 'var(--ide-rm)', padding: 14, display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 1fr 0.6fr', gap: 12, alignItems: 'center' }}>
            <div>
              <div style={{ fontWeight: 700 }}>{c.lead_company}</div>
              <div style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'var(--ide-font-mono)' }}>
                Sales: {c.sales_nik}
              </div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--ide-ink2)' }}>
              {c.commission_pct}% commission
            </div>
            <div style={{ fontFamily: 'var(--ide-font-mono)', fontWeight: 700, color: 'var(--ide-green)' }}>
              {formatIDR(c.commission_amount)}
            </div>
            <div>
              <Tag color={c.status === 'PAID' ? 'green' : 'orange'}>{c.status}</Tag>
            </div>
            <div style={{ fontSize: 10, color: 'var(--ide-ink3)' }}>
              {c.target_payroll_period_id ? '📊 in payroll' : 'not assigned'}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── TARGETS TAB ───────────────────────────────────────────────

function TargetsTab() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const query = useQuery({ queryKey: ['targets'], queryFn: () => listTargets() });
  const empQuery = useQuery({ queryKey: ['emp-target'], queryFn: () => listEmployees({ page_size: 200 }) });
  const deptQuery = useQuery({ queryKey: ['depts'], queryFn: listDepartments });

  const mutation = useMutation({
    mutationFn: createTarget,
    onSuccess: () => {
      message.success('Target created');
      queryClient.invalidateQueries({ queryKey: ['targets'] });
      setCreateOpen(false);
    },
  });

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
          Set Target
        </Button>
      </div>

      {query.isLoading && <Spin />}
      {(query.data || []).length === 0 && <Empty description="Belum ada target" />}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
        {(query.data || []).map((t) => {
          const pct = parseFloat(t.achievement_pct);
          const color = pct >= 100 ? 'var(--ide-green)' : pct >= 50 ? 'var(--ide-blue)' : 'var(--ide-orange)';
          return (
            <div key={t.id} style={{ background: 'var(--ide-surface)', border: '1px solid var(--ide-border)', borderRadius: 'var(--ide-r)', padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>
                    {t.user_nik || t.department_name || 'Company-wide'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>
                    {t.year}{t.month ? `-${String(t.month).padStart(2, '0')}` : ' (annual)'}
                  </div>
                </div>
                <div style={{ fontSize: 16, fontWeight: 800, color, fontFamily: 'var(--ide-font-mono)' }}>
                  {pct.toFixed(0)}%
                </div>
              </div>
              <Progress percent={Math.min(pct, 100)} size="small" style={{ marginTop: 8 }} strokeColor={color} />
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 11, fontFamily: 'var(--ide-font-mono)' }}>
                <span>{formatIDR(t.achieved_amount)}</span>
                <span style={{ color: 'var(--ide-ink3)' }}>/ {formatIDR(t.target_amount)}</span>
              </div>
            </div>
          );
        })}
      </div>

      <Modal title="Set Sales Target" open={createOpen} onCancel={() => setCreateOpen(false)} footer={null} destroyOnClose>
        <Form layout="vertical" onFinish={(v) => mutation.mutate(v)} initialValues={{ year: new Date().getFullYear() }}>
          <Form.Item label="Sales PIC (opsional)" name="user_id">
            <Select
              allowClear
              showSearch
              optionFilterProp="label"
              options={(empQuery.data?.items || []).map((e) => ({ value: e.id, label: `${e.nik} · ${e.full_name}` }))}
            />
          </Form.Item>
          <Form.Item label="Departemen (opsional)" name="department_id">
            <Select
              allowClear
              options={(deptQuery.data || []).map((d) => ({ value: d.id, label: d.name }))}
            />
          </Form.Item>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <Form.Item label="Year" name="year" rules={[{ required: true }]}>
              <InputNumber min={2020} max={2099} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="Month (opsional)" name="month">
              <InputNumber min={1} max={12} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item label="Target Amount (IDR)" name="target_amount" rules={[{ required: true }]}>
            <InputNumber min={0} style={{ width: '100%', fontFamily: 'var(--ide-font-mono)' }} formatter={(v) => v ? `Rp ${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.') : ''} parser={(v) => v ? Number(v.replace(/[^0-9]/g, '')) : 0} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={mutation.isPending}>Submit</Button>
        </Form>
      </Modal>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────

export default function SalesPage() {
  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
          Sales Pipeline
        </h2>
        <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
          Lead funnel 6-stage + auto-commission saat CLOSED_WON + sales target tracking.
        </p>
      </div>

      <Tabs
        defaultActiveKey="pipeline"
        items={[
          { key: 'pipeline', label: 'Pipeline (Kanban)', children: <PipelineTab /> },
          { key: 'commissions', label: 'Commissions', children: <CommissionsTab /> },
          { key: 'targets', label: 'Targets', children: <TargetsTab /> },
        ]}
      />
    </div>
  );
}
