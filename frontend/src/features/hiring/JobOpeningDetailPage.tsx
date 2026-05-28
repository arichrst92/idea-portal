/**
 * Job Opening Detail + Pipeline Kanban — TSK-015 FE.
 *
 * Layout:
 * - Header: title, dept, status, slot progress
 * - Info card: description, requirements, salary range, deadline
 * - Action bar: Submit (DRAFT), Approve/Reject (PENDING_APPROVAL), Close (OPEN)
 * - Pipeline kanban: 9 stages, click candidate card → transition modal
 * - Add candidate button (open application form modal)
 */

import {
  ArrowLeftOutlined,
  CheckOutlined,
  CloseOutlined,
  PlusOutlined,
  SendOutlined,
  StopOutlined,
  UserAddOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Empty, Form, Input, Modal, Select, Spin, Tag, message } from 'antd';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import {
  approveJobOpening,
  closeJobOpening,
  createApplication,
  getJobOpening,
  getPipeline,
  jobStatusColor,
  stageColor,
  submitJobOpening,
  transitionStage,
  type ApplicationStage,
  type JobApplication,
  SOURCE_OPTIONS,
} from '@/api/hiring';
import { useAuthStore } from '@/store/auth';

const { TextArea } = Input;

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleDateString('id-ID', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return value;
  }
}

function formatIDR(value: string | null | undefined): string {
  if (!value) return '—';
  const n = parseFloat(value);
  if (!isFinite(n)) return value;
  return `Rp ${n.toLocaleString('id-ID')}`;
}

// ─── Candidate Card ──────────────────────────────────────────────

function CandidateCard({
  app,
  onClick,
}: {
  app: JobApplication;
  onClick: () => void;
}) {
  const color = stageColor(app.stage);
  return (
    <div
      onClick={onClick}
      style={{
        background: 'var(--ide-surface)',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-rs)',
        padding: '10px 12px',
        cursor: 'pointer',
        marginBottom: 8,
        transition: 'all 0.12s',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = color.hex;
        e.currentTarget.style.boxShadow = 'var(--ide-shadow-sm)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--ide-border)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ide-ink)', marginBottom: 3 }}>
        {app.candidate_name}
      </div>
      <div style={{ fontSize: 11, color: 'var(--ide-ink3)', marginBottom: 6 }}>
        {app.candidate_email}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span
          style={{
            fontSize: 10,
            fontWeight: 600,
            padding: '2px 8px',
            borderRadius: 20,
            background: color.soft,
            color: color.hex,
          }}
        >
          {app.source.replace(/_/g, ' ')}
        </span>
        {app.days_in_stage !== null && (
          <span style={{ fontSize: 10, color: 'var(--ide-ink3)' }}>{app.days_in_stage}d</span>
        )}
      </div>
    </div>
  );
}

// ─── Add Application Modal ───────────────────────────────────────

function AddApplicationModal({
  jobOpeningId,
  open,
  onClose,
  onSuccess,
}: {
  jobOpeningId: string;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();

  const mutation = useMutation({
    mutationFn: createApplication,
    onSuccess: () => {
      message.success('Kandidat ditambahkan');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: () => {
      message.error('Gagal tambah kandidat');
    },
  });

  const handleSubmit = async () => {
    const values = await form.validateFields();
    mutation.mutate({
      job_opening_id: jobOpeningId,
      candidate_name: values.candidate_name,
      candidate_email: values.candidate_email,
      candidate_phone: values.candidate_phone,
      linkedin_url: values.linkedin_url,
      source: values.source,
    });
  };

  return (
    <Modal
      title="Tambah Kandidat"
      open={open}
      onCancel={onClose}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button key="s" type="primary" loading={mutation.isPending} onClick={handleSubmit}>
          Tambah
        </Button>,
      ]}
      destroyOnClose
    >
      <Form form={form} layout="vertical" initialValues={{ source: 'OTHER' }}>
        <Form.Item
          label="Nama Kandidat"
          name="candidate_name"
          rules={[{ required: true, message: 'Nama wajib diisi' }]}
        >
          <Input placeholder="Nama lengkap" />
        </Form.Item>
        <Form.Item
          label="Email"
          name="candidate_email"
          rules={[
            { required: true, message: 'Email wajib diisi' },
            { type: 'email', message: 'Email tidak valid' },
          ]}
        >
          <Input placeholder="email@domain.com" />
        </Form.Item>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <Form.Item label="Nomor HP" name="candidate_phone">
            <Input placeholder="08xx-xxxx-xxxx" />
          </Form.Item>
          <Form.Item label="Source" name="source">
            <Select options={SOURCE_OPTIONS} />
          </Form.Item>
        </div>
        <Form.Item label="LinkedIn URL" name="linkedin_url">
          <Input placeholder="https://linkedin.com/in/..." />
        </Form.Item>
      </Form>
    </Modal>
  );
}

// ─── Transition Modal ────────────────────────────────────────────

const STAGE_FLOW: Record<ApplicationStage, ApplicationStage[]> = {
  APPLIED: ['SCREENING', 'REJECTED', 'WITHDRAWN'],
  SCREENING: ['HR_INTERVIEW', 'REJECTED', 'WITHDRAWN'],
  HR_INTERVIEW: ['USER_INTERVIEW', 'TECHNICAL_TEST', 'OFFERING', 'REJECTED', 'WITHDRAWN'],
  USER_INTERVIEW: ['TECHNICAL_TEST', 'OFFERING', 'REJECTED', 'WITHDRAWN'],
  TECHNICAL_TEST: ['OFFERING', 'REJECTED', 'WITHDRAWN'],
  OFFERING: ['HIRED', 'REJECTED', 'WITHDRAWN'],
  HIRED: [],
  REJECTED: [],
  WITHDRAWN: [],
};

function TransitionModal({
  app,
  open,
  onClose,
  onSuccess,
}: {
  app: JobApplication | null;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const [selectedStage, setSelectedStage] = useState<ApplicationStage | null>(null);

  const mutation = useMutation({
    mutationFn: ({ appId, payload }: { appId: string; payload: any }) =>
      transitionStage(appId, payload),
    onSuccess: () => {
      message.success('Stage berubah');
      form.resetFields();
      setSelectedStage(null);
      onSuccess();
      onClose();
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail?.message || 'Gagal pindah stage');
    },
  });

  const handleSubmit = async () => {
    const values = await form.validateFields();
    if (!app || !selectedStage) return;
    mutation.mutate({
      appId: app.id,
      payload: {
        new_stage: selectedStage,
        notes: values.notes || undefined,
        rejection_reason: selectedStage === 'REJECTED' ? values.rejection_reason : undefined,
      },
    });
  };

  if (!app) return null;
  const allowed = STAGE_FLOW[app.stage] || [];

  return (
    <Modal
      title={`${app.candidate_name} — Pindah Stage`}
      open={open}
      onCancel={() => {
        setSelectedStage(null);
        onClose();
      }}
      footer={[
        <Button key="c" onClick={onClose}>
          Batal
        </Button>,
        <Button
          key="s"
          type="primary"
          loading={mutation.isPending}
          disabled={!selectedStage}
          onClick={handleSubmit}
        >
          Lanjut
        </Button>,
      ]}
      destroyOnClose
    >
      <div
        style={{
          background: 'var(--ide-bg)',
          padding: '8px 12px',
          borderRadius: 'var(--ide-rs)',
          marginBottom: 16,
          fontSize: 12,
          color: 'var(--ide-ink2)',
        }}
      >
        Stage saat ini: <strong>{stageColor(app.stage).label}</strong>
      </div>

      {allowed.length === 0 ? (
        <div style={{ color: 'var(--ide-ink3)' }}>
          Stage <strong>{stageColor(app.stage).label}</strong> adalah terminal — tidak ada transisi.
        </div>
      ) : (
        <Form form={form} layout="vertical">
          <Form.Item label="Pindah ke Stage">
            <Select
              value={selectedStage ?? undefined}
              placeholder="Pilih stage tujuan"
              onChange={(v) => setSelectedStage(v as ApplicationStage)}
              options={allowed.map((s) => ({ value: s, label: stageColor(s).label }))}
            />
          </Form.Item>
          {selectedStage === 'REJECTED' && (
            <Form.Item
              label="Alasan Reject"
              name="rejection_reason"
              rules={[
                { required: true, message: 'Wajib diisi (min 10 karakter)' },
                { min: 10, message: 'Min 10 karakter' },
              ]}
            >
              <TextArea rows={3} placeholder="Contoh: Tidak memenuhi requirement min 5 tahun pengalaman." />
            </Form.Item>
          )}
          <Form.Item label="Catatan (opsional)" name="notes">
            <TextArea rows={3} placeholder="Catatan internal..." />
          </Form.Item>
        </Form>
      )}
    </Modal>
  );
}

// ─── Main Detail Page ────────────────────────────────────────────

export default function JobOpeningDetailPage() {
  const { id = '' } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);

  const [addAppOpen, setAddAppOpen] = useState(false);
  const [transitionApp, setTransitionApp] = useState<JobApplication | null>(null);

  const isExecutive =
    user?.roles.some((r) => r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA') ?? false;
  const isApprover =
    isExecutive ||
    (user?.roles.some((r) => ['C_LEVEL', 'GM'].includes(r.code)) ?? false);

  const openingQuery = useQuery({
    queryKey: ['job-opening', id],
    queryFn: () => getJobOpening(id),
    enabled: !!id,
  });

  const pipelineQuery = useQuery({
    queryKey: ['pipeline', id],
    queryFn: () => getPipeline(id),
    enabled: !!id,
  });

  const submitMut = useMutation({
    mutationFn: () => submitJobOpening(id),
    onSuccess: () => {
      message.success('Submitted for approval');
      refresh();
    },
  });

  const approveMut = useMutation({
    mutationFn: (approve: boolean) =>
      approveJobOpening(id, approve, approve ? undefined : 'Rejected via UI'),
    onSuccess: (_, approve) => {
      message.success(approve ? 'Approved' : 'Rejected');
      refresh();
    },
  });

  const closeMut = useMutation({
    mutationFn: () => closeJobOpening(id),
    onSuccess: () => {
      message.success('Lowongan ditutup');
      refresh();
    },
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['job-opening', id] });
    queryClient.invalidateQueries({ queryKey: ['pipeline', id] });
    queryClient.invalidateQueries({ queryKey: ['job-openings'] });
  };

  if (openingQuery.isLoading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (openingQuery.isError || !openingQuery.data) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <Empty description="Lowongan tidak ditemukan" />
        <Button onClick={() => navigate('/hiring')} style={{ marginTop: 12 }}>
          Kembali
        </Button>
      </div>
    );
  }

  const opening = openingQuery.data;
  const statusTag = jobStatusColor(opening.status);
  const slotsProgress =
    opening.slots_needed > 0 ? Math.round((opening.slots_filled / opening.slots_needed) * 100) : 0;

  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/hiring')}
        style={{ marginBottom: 14, fontWeight: 600 }}
      >
        Daftar Lowongan
      </Button>

      {/* Header card */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          padding: '20px 24px',
          marginBottom: 14,
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div style={{ flex: 1 }}>
            <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 6 }}>
              {opening.title}
            </h2>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
              <span style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
                {opening.department_name} {opening.position_name && `· ${opening.position_name}`}
              </span>
              {opening.deadline && (
                <span style={{ fontSize: 12, color: 'var(--ide-ink3)' }}>
                  Deadline: {formatDate(opening.deadline)}
                </span>
              )}
            </div>
          </div>

          {/* Action buttons */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {opening.status === 'DRAFT' && (
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={() => submitMut.mutate()}
                loading={submitMut.isPending}
              >
                Submit Approval
              </Button>
            )}
            {opening.status === 'PENDING_APPROVAL' && isApprover && (
              <>
                <Button
                  icon={<CheckOutlined />}
                  type="primary"
                  onClick={() => approveMut.mutate(true)}
                  loading={approveMut.isPending}
                  style={{ background: 'var(--ide-green)', borderColor: 'var(--ide-green)' }}
                >
                  Approve
                </Button>
                <Button
                  icon={<CloseOutlined />}
                  danger
                  onClick={() => approveMut.mutate(false)}
                  loading={approveMut.isPending}
                >
                  Reject
                </Button>
              </>
            )}
            {opening.status === 'OPEN' && (
              <>
                <Button
                  type="primary"
                  icon={<UserAddOutlined />}
                  onClick={() => setAddAppOpen(true)}
                  style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)' }}
                >
                  Tambah Kandidat
                </Button>
                {isApprover && (
                  <Button icon={<StopOutlined />} onClick={() => closeMut.mutate()} loading={closeMut.isPending}>
                    Close
                  </Button>
                )}
              </>
            )}
          </div>
        </div>

        {/* Slots progress */}
        <div style={{ marginTop: 14 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 11, color: 'var(--ide-ink3)', fontWeight: 600 }}>
              Slot Terisi
            </span>
            <span style={{ fontSize: 12, fontFamily: 'var(--ide-font-mono)', fontWeight: 700 }}>
              {opening.slots_filled} / {opening.slots_needed}
            </span>
          </div>
          <div style={{ height: 6, background: 'var(--ide-bg)', borderRadius: 3, overflow: 'hidden' }}>
            <div
              style={{
                height: '100%',
                width: `${slotsProgress}%`,
                background: 'var(--ide-blue)',
                transition: 'width 0.3s',
              }}
            />
          </div>
        </div>
      </div>

      {/* Info grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 14, marginBottom: 14 }}>
        <div
          style={{
            background: 'var(--ide-surface)',
            border: '1px solid var(--ide-border)',
            borderRadius: 'var(--ide-r)',
            padding: '18px 22px',
          }}
        >
          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: 'var(--ide-ink3)',
              textTransform: 'uppercase',
              letterSpacing: 0.8,
              marginBottom: 8,
            }}
          >
            Description
          </div>
          <div style={{ fontSize: 13, color: 'var(--ide-ink)', whiteSpace: 'pre-wrap' }}>
            {opening.description || <span style={{ color: 'var(--ide-ink3)' }}>—</span>}
          </div>

          <div
            style={{
              fontSize: 10,
              fontWeight: 700,
              color: 'var(--ide-ink3)',
              textTransform: 'uppercase',
              letterSpacing: 0.8,
              marginTop: 16,
              marginBottom: 8,
            }}
          >
            Requirements
          </div>
          <div style={{ fontSize: 13, color: 'var(--ide-ink)', whiteSpace: 'pre-wrap' }}>
            {opening.requirements || <span style={{ color: 'var(--ide-ink3)' }}>—</span>}
          </div>
        </div>

        <div
          style={{
            background: 'var(--ide-surface)',
            border: '1px solid var(--ide-border)',
            borderRadius: 'var(--ide-r)',
            padding: '18px 22px',
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
            fontSize: 12,
          }}
        >
          <div>
            <div style={{ color: 'var(--ide-ink3)', fontWeight: 600, marginBottom: 2 }}>
              Salary Range
            </div>
            <div style={{ fontFamily: 'var(--ide-font-mono)', fontWeight: 700 }}>
              {formatIDR(opening.min_salary)} – {formatIDR(opening.max_salary)}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--ide-ink3)', fontWeight: 600, marginBottom: 2 }}>Posted</div>
            <div>{formatDate(opening.posted_date)}</div>
          </div>
          <div>
            <div style={{ color: 'var(--ide-ink3)', fontWeight: 600, marginBottom: 2 }}>
              Requested by
            </div>
            <div style={{ fontFamily: 'var(--ide-font-mono)' }}>
              {opening.requested_by_nik || '—'}
            </div>
          </div>
          <div>
            <div style={{ color: 'var(--ide-ink3)', fontWeight: 600, marginBottom: 2 }}>
              Total Kandidat
            </div>
            <div style={{ fontFamily: 'var(--ide-font-mono)', fontWeight: 700 }}>
              {opening.application_count}
            </div>
          </div>
        </div>
      </div>

      {/* Pipeline Kanban */}
      {pipelineQuery.data && (
        <div>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              marginBottom: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            Pipeline Kandidat{' '}
            <Tag color="blue">{pipelineQuery.data.total_applications} aktif</Tag>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(9, minmax(180px, 1fr))',
              gap: 10,
              overflowX: 'auto',
              paddingBottom: 8,
            }}
          >
            {pipelineQuery.data.stages.map((bucket) => {
              const color = stageColor(bucket.stage);
              return (
                <div
                  key={bucket.stage}
                  style={{
                    background: 'var(--ide-bg)',
                    borderRadius: 'var(--ide-rm)',
                    padding: 10,
                    minHeight: 200,
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: 10,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 11,
                        fontWeight: 700,
                        color: color.hex,
                        textTransform: 'uppercase',
                        letterSpacing: 0.5,
                      }}
                    >
                      {bucket.label}
                    </div>
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

                  {bucket.applications.length === 0 ? (
                    <div
                      style={{
                        fontSize: 11,
                        color: 'var(--ide-ink3)',
                        textAlign: 'center',
                        padding: 14,
                      }}
                    >
                      Kosong
                    </div>
                  ) : (
                    bucket.applications.map((app) => (
                      <CandidateCard key={app.id} app={app} onClick={() => setTransitionApp(app)} />
                    ))
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Modals */}
      <AddApplicationModal
        jobOpeningId={id}
        open={addAppOpen}
        onClose={() => setAddAppOpen(false)}
        onSuccess={refresh}
      />
      <TransitionModal
        app={transitionApp}
        open={transitionApp !== null}
        onClose={() => setTransitionApp(null)}
        onSuccess={refresh}
      />
    </div>
  );
}
