/**
 * OfferDrawer — TSK-034 (US-OP-002 AC-04..07).
 *
 * Drawer untuk kelola offering letter per JobApplication:
 * - Form salary + start_date + additional terms (DRAFT state)
 * - Generate PDF preview + download
 * - Submit Approval (HR action)
 * - Approve/Reject (GM/C-Level — hiring.approve)
 * - Mark Sent (after APPROVED)
 * - Record Candidate Response (Accept/Negotiate/Reject)
 *
 * NC-OP-002-03: block Mark Sent without approval
 * NC-OP-002-04: warning + override flag kalau salary > range
 * NC-OP-002-06: start date required for ACCEPTED→Hired
 */

import {
  CheckCircleOutlined,
  CheckOutlined,
  CloseOutlined,
  DownloadOutlined,
  FilePdfOutlined,
  SendOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Drawer,
  Form,
  Input,
  Popconfirm,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  approveOffer,
  generateOfferPdf,
  getOfferPdfUrl,
  markOfferSent,
  OFFER_STATUS_COLOR,
  recordCandidateResponse,
  rejectOffer,
  submitOfferForApproval,
  type CandidateResponse,
  type JobApplication,
  type OfferStatus,
} from '@/api/hiring';
import { message } from '@/lib/notify';
import { useAuthStore } from '@/store/auth';

const { Text, Title, Paragraph } = Typography;

const fmtIDR = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (!Number.isFinite(n)) return '—';
  return `Rp ${n.toLocaleString('id-ID')}`;
};

interface OfferDrawerProps {
  application: JobApplication & {
    offer_status?: OfferStatus;
    offer_pdf_url?: string | null;
    offer_pdf_generated_at?: string | null;
    candidate_response?: CandidateResponse | null;
    salary_override_approved?: boolean;
  };
  open: boolean;
  onClose: () => void;
  onChanged?: () => void;
}

export function OfferDrawer({ application, open, onClose, onChanged }: OfferDrawerProps) {
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const isApprover =
    user?.roles.some((r) =>
      ['DIREKTUR_UTAMA', 'WAKIL_DIREKTUR_UTAMA', 'C_LEVEL', 'GM'].includes(r.code)
    ) ?? false;

  const [responseModalOpen, setResponseModalOpen] = useState(false);
  const [responseForm] = Form.useForm();

  const status: OfferStatus = application.offer_status ?? 'DRAFT';
  const isDraft = status === 'DRAFT';
  const isPending = status === 'PENDING_APPROVAL';
  const isApproved = status === 'APPROVED';
  const isSent = status === 'SENT';
  const isTerminal = ['ACCEPTED', 'REJECTED', 'NEGOTIATING'].includes(status);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['pipeline'] });
    queryClient.invalidateQueries({ queryKey: ['application'] });
    onChanged?.();
  };

  const pdfQuery = useQuery({
    queryKey: ['offer-pdf-url', application.id, application.offer_pdf_url],
    queryFn: () => getOfferPdfUrl(application.id),
    enabled: open && !!application.offer_pdf_url,
  });

  const generatePdfMut = useMutation({
    mutationFn: () => generateOfferPdf(application.id),
    onSuccess: () => {
      message.success('Offer letter PDF generated');
      queryClient.invalidateQueries({ queryKey: ['offer-pdf-url', application.id] });
      refresh();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal generate PDF'),
  });

  const submitMut = useMutation({
    mutationFn: () => submitOfferForApproval(application.id),
    onSuccess: () => {
      message.success('Offer submitted — menunggu approval GM/C-Level');
      refresh();
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail;
      if (d?.code === 'SALARY_OVER_RANGE') {
        message.error(d.message);
      } else {
        message.error(d?.message ?? 'Gagal submit');
      }
    },
  });

  const approveMut = useMutation({
    mutationFn: (data: { notes?: string; salary_override?: boolean }) =>
      approveOffer(application.id, data),
    onSuccess: () => {
      message.success('Offer approved ✓');
      refresh();
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail;
      if (d?.code === 'SALARY_OVER_RANGE') {
        message.error(d.message + ' — Centang "C-Level override" untuk lanjut.');
      } else {
        message.error(d?.message ?? 'Gagal approve');
      }
    },
  });

  const rejectMut = useMutation({
    mutationFn: (reason: string) => rejectOffer(application.id, reason),
    onSuccess: () => {
      message.success('Offer rejected — kembali ke HR untuk revisi');
      refresh();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal reject'),
  });

  const markSentMut = useMutation({
    mutationFn: () => markOfferSent(application.id),
    onSuccess: () => {
      message.success('Offer marked as SENT — menunggu response kandidat');
      refresh();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal mark sent'),
  });

  const responseMut = useMutation({
    mutationFn: (data: { response: CandidateResponse; notes?: string }) =>
      recordCandidateResponse(application.id, data.response, data.notes),
    onSuccess: (res) => {
      if (res.candidate_response === 'ACCEPTED') {
        message.success('🎉 Candidate ACCEPTED — moved to Hired stage, onboarding next');
      } else {
        message.success(`Response recorded: ${res.candidate_response}`);
      }
      setResponseModalOpen(false);
      responseForm.resetFields();
      refresh();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail?.message ?? 'Gagal record response'),
  });

  const handleDownloadPdf = async () => {
    if (pdfQuery.data?.url) {
      window.open(pdfQuery.data.url, '_blank');
    } else {
      const r = await getOfferPdfUrl(application.id);
      if (r.url) {
        window.open(r.url, '_blank');
      } else {
        message.warning('PDF belum di-generate. Klik "Generate PDF" dulu.');
      }
    }
  };

  const handleApprove = () => {
    approveMut.mutate({ notes: undefined, salary_override: false });
  };

  const handleApproveWithOverride = () => {
    approveMut.mutate({ notes: 'C-Level salary override', salary_override: true });
  };

  const handleReject = () => {
    const reason = window.prompt('Alasan reject (min 3 karakter):');
    if (reason && reason.length >= 3) {
      rejectMut.mutate(reason);
    } else if (reason !== null) {
      message.warning('Alasan minimal 3 karakter');
    }
  };

  return (
    <Drawer
      title={
        <Space>
          <FilePdfOutlined />
          <span>Offering Letter — {application.candidate_name}</span>
        </Space>
      }
      open={open}
      onClose={onClose}
      width={520}
    >
      {/* Status banner */}
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Text type="secondary" style={{ fontSize: 12 }}>Status:</Text>
          <Tag color={OFFER_STATUS_COLOR[status].color} style={{ fontSize: 12 }}>
            {OFFER_STATUS_COLOR[status].label}
          </Tag>
          {application.salary_override_approved && (
            <Tag color="gold">Salary Override ✓</Tag>
          )}
        </Space>
      </div>

      {/* Offer summary */}
      <div
        style={{
          background: 'var(--ide-bg, #F5F5F7)',
          borderRadius: 8,
          padding: 14,
          marginBottom: 16,
        }}
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 12 }}>
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Gaji</Text>
            <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--ide-blue, #0071E3)' }}>
              {fmtIDR(application.offered_salary)}
            </div>
          </div>
          <div>
            <Text type="secondary" style={{ fontSize: 11 }}>Start Date</Text>
            <div style={{ fontSize: 14, fontWeight: 600 }}>
              {application.offered_start_date
                ? dayjs(application.offered_start_date).format('DD MMM YYYY')
                : '—'}
            </div>
          </div>
        </div>
        {(!application.offered_salary || !application.offered_start_date) && (
          <Alert
            type="warning"
            showIcon
            style={{ marginTop: 10, fontSize: 12 }}
            message="Salary dan Start Date wajib di-set sebelum generate offer letter. Edit di transition modal stage."
          />
        )}
      </div>

      {/* PDF section */}
      <div style={{ marginBottom: 16 }}>
        <Title level={5} style={{ marginBottom: 8 }}>
          <FilePdfOutlined /> Offer Letter PDF
        </Title>
        {application.offer_pdf_url ? (
          <Space>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownloadPdf}
            >
              Download PDF
            </Button>
            <Button
              type="link"
              icon={<ThunderboltOutlined />}
              onClick={() => generatePdfMut.mutate()}
              loading={generatePdfMut.isPending}
              disabled={isTerminal}
            >
              Re-generate
            </Button>
          </Space>
        ) : (
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            onClick={() => generatePdfMut.mutate()}
            loading={generatePdfMut.isPending}
            disabled={!application.offered_salary || !application.offered_start_date}
          >
            Generate PDF
          </Button>
        )}
        {application.offer_pdf_generated_at && (
          <Text type="secondary" style={{ fontSize: 11, display: 'block', marginTop: 4 }}>
            Last generated: {dayjs(application.offer_pdf_generated_at).format('DD MMM YYYY HH:mm')}
          </Text>
        )}
      </div>

      {/* Workflow Actions */}
      <Title level={5}>Actions</Title>
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        {/* DRAFT → submit */}
        {isDraft && (
          <Button
            type="primary"
            block
            icon={<SendOutlined />}
            onClick={() => submitMut.mutate()}
            loading={submitMut.isPending}
            disabled={!application.offer_pdf_url}
          >
            Submit untuk Approval GM/C-Level
          </Button>
        )}

        {/* PENDING_APPROVAL — approve/reject (only approver) */}
        {isPending && isApprover && (
          <>
            <Alert
              type="info"
              showIcon
              message="Pending GM/C-Level approval. Anda dapat approve atau reject."
              style={{ fontSize: 12 }}
            />
            <Popconfirm
              title="Approve offer ini?"
              description="Kandidat akan dapat menerima offer setelah Mark Sent."
              onConfirm={handleApprove}
            >
              <Button
                type="primary"
                block
                icon={<CheckOutlined />}
                loading={approveMut.isPending}
              >
                Approve
              </Button>
            </Popconfirm>
            {!application.salary_override_approved && (
              <Button
                type="dashed"
                block
                onClick={handleApproveWithOverride}
                loading={approveMut.isPending}
              >
                Approve dengan Salary Override (C-Level only)
              </Button>
            )}
            <Button block danger icon={<CloseOutlined />} onClick={handleReject}>
              Reject
            </Button>
          </>
        )}

        {isPending && !isApprover && (
          <Alert
            type="warning"
            showIcon
            message="Menunggu approval GM/C-Level. Anda tidak memiliki permission untuk approve."
            style={{ fontSize: 12 }}
          />
        )}

        {/* APPROVED → Mark Sent */}
        {isApproved && (
          <>
            <Alert
              type="success"
              showIcon
              message="Approved oleh GM/C-Level. Klik 'Mark Sent' setelah PDF dikirim ke kandidat via email."
              style={{ fontSize: 12 }}
            />
            <Popconfirm
              title="Mark offer sebagai SENT?"
              description="Pastikan PDF sudah dikirim ke email kandidat."
              onConfirm={() => markSentMut.mutate()}
            >
              <Button
                type="primary"
                block
                icon={<SendOutlined />}
                loading={markSentMut.isPending}
              >
                Mark Sent
              </Button>
            </Popconfirm>
          </>
        )}

        {/* SENT → Record candidate response */}
        {isSent && (
          <>
            <Alert
              type="info"
              showIcon
              message="Menunggu response kandidat. Record di sini saat kandidat reply."
              style={{ fontSize: 12 }}
            />
            <Button
              type="primary"
              block
              icon={<CheckCircleOutlined />}
              onClick={() => setResponseModalOpen(true)}
            >
              Record Candidate Response
            </Button>
          </>
        )}

        {/* Terminal */}
        {isTerminal && (
          <Alert
            type={status === 'ACCEPTED' ? 'success' : 'error'}
            showIcon
            message={`Candidate response: ${status}`}
            description={
              status === 'ACCEPTED'
                ? 'Application moved to HIRED stage. Onboarding will auto-trigger via TSK-038/039.'
                : 'Offer cycle closed.'
            }
            style={{ fontSize: 12 }}
          />
        )}
      </Space>

      {/* Candidate Response Modal */}
      <Drawer
        title="Record Candidate Response"
        open={responseModalOpen}
        onClose={() => setResponseModalOpen(false)}
        width={420}
      >
        <Form
          form={responseForm}
          layout="vertical"
          onFinish={(v) => responseMut.mutate(v)}
        >
          <Form.Item
            label="Response"
            name="response"
            rules={[{ required: true, message: 'Pilih response' }]}
          >
            <Select
              placeholder="Pilih response kandidat..."
              options={[
                { value: 'ACCEPTED', label: '✓ Accepted (kandidat setuju)' },
                { value: 'NEGOTIATING', label: '↻ Negotiating (ada negosiasi)' },
                { value: 'REJECTED', label: '✗ Rejected (kandidat menolak)' },
              ]}
            />
          </Form.Item>
          <Form.Item label="Notes (opsional)" name="notes">
            <Input.TextArea rows={3} placeholder="Detail negosiasi atau alasan tolak..." />
          </Form.Item>
          <Paragraph type="secondary" style={{ fontSize: 11 }}>
            ACCEPTED akan auto-move application ke stage HIRED (AC-07).
            Start date harus sudah di-set sebelum Accept (NC-OP-002-06).
          </Paragraph>
          <Button
            type="primary"
            htmlType="submit"
            block
            loading={responseMut.isPending}
            icon={<CheckCircleOutlined />}
          >
            Record Response
          </Button>
        </Form>
      </Drawer>
    </Drawer>
  );
}
