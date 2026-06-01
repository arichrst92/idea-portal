/**
 * JobBoardPage — TSK-036 Internal Job Board.
 *
 * Per knowledge.md sec.5: "Internal job board, tracking end-to-end".
 *
 * Public-ish page: semua karyawan ter-autentikasi dapat lihat OPEN job openings,
 * refer kandidat (US-OP-002 AC-01 source: referral). Tidak butuh permission
 * hiring.create — siapapun bisa ref kandidat.
 */

import {
  ApartmentOutlined,
  CalendarOutlined,
  CompassOutlined,
  PlusOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Empty,
  Form,
  Input,
  Modal,
  Select,
  Spin,
  Tag,
  Typography,
} from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';

import {
  createApplication,
  listJobOpenings,
  SOURCE_OPTIONS,
  type JobOpeningListItem,
} from '@/api/hiring';
import { message } from '@/lib/notify';

const { Title, Text, Paragraph } = Typography;

function JobCard({
  job,
  onRefer,
}: {
  job: JobOpeningListItem;
  onRefer: (job: JobOpeningListItem) => void;
}) {
  const slotsLeft = (job.slots_needed ?? 0) - (job.slots_filled ?? 0);
  return (
    <div
      style={{
        background: 'var(--ide-surface, white)',
        border: '1px solid var(--ide-border, #E8E8ED)',
        borderRadius: 10,
        padding: 18,
        marginBottom: 12,
        transition: 'all 0.12s',
        cursor: 'default',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = '0 4px 16px rgba(0,113,227,0.08)';
        e.currentTarget.style.borderColor = 'var(--ide-blue, #0071E3)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = 'none';
        e.currentTarget.style.borderColor = 'var(--ide-border, #E8E8ED)';
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Title level={5} style={{ margin: 0, fontSize: 16 }}>
            {job.title}
          </Title>
          <div style={{ display: 'flex', gap: 14, marginTop: 6, flexWrap: 'wrap' }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              <ApartmentOutlined /> {job.department_name ?? '—'}
            </Text>
            {job.position_name && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                <CompassOutlined /> {job.position_name}
              </Text>
            )}
            <Text type="secondary" style={{ fontSize: 12 }}>
              <TeamOutlined /> {slotsLeft} slot{slotsLeft !== 1 ? 's' : ''} tersedia
            </Text>
            {job.deadline && (
              <Text type="secondary" style={{ fontSize: 12 }}>
                <CalendarOutlined /> Deadline {dayjs(job.deadline).format('DD MMM YYYY')}
              </Text>
            )}
          </div>
        </div>
        <div style={{ textAlign: 'right', minWidth: 110 }}>
          <Tag color="green">
            {job.application_count} applicant{job.application_count !== 1 ? 's' : ''}
          </Tag>
        </div>
      </div>

      <div style={{ marginTop: 12, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={() => onRefer(job)}
        >
          Refer Kandidat
        </Button>
      </div>
    </div>
  );
}

function ReferModal({
  job,
  open,
  onClose,
  onSuccess,
}: {
  job: JobOpeningListItem | null;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form] = Form.useForm();
  const mutation = useMutation({
    mutationFn: createApplication,
    onSuccess: () => {
      message.success('Kandidat berhasil di-refer · HR akan review');
      form.resetFields();
      onSuccess();
      onClose();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail?.message ?? 'Gagal refer kandidat'),
  });

  if (!job) return null;

  return (
    <Modal
      title={`Refer Kandidat — ${job.title}`}
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnHidden
      width={560}
    >
      <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 14 }}>
        Anda akan refer kandidat untuk posisi <strong>{job.title}</strong> di
        departemen <strong>{job.department_name ?? '—'}</strong>. Setelah submit,
        HR akan review CV dan menjadwalkan screening.
      </Paragraph>
      <Form
        form={form}
        layout="vertical"
        initialValues={{ source: 'REFERRAL', job_opening_id: job.id }}
        onFinish={(v) =>
          mutation.mutate({
            job_opening_id: job.id,
            candidate_name: v.candidate_name,
            candidate_email: v.candidate_email,
            candidate_phone: v.candidate_phone || undefined,
            resume_url: v.resume_url || undefined,
            cover_letter: v.notes || undefined,
            linkedin_url: v.linkedin_url || undefined,
            source: v.source,
          })
        }
      >
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <Form.Item
            label="Nama Kandidat"
            name="candidate_name"
            rules={[{ required: true, message: 'Nama wajib' }]}
          >
            <Input placeholder="Budi Santoso" />
          </Form.Item>
          <Form.Item
            label="Email"
            name="candidate_email"
            rules={[
              { required: true, message: 'Email wajib' },
              { type: 'email', message: 'Format email salah' },
            ]}
          >
            <Input placeholder="budi@example.com" />
          </Form.Item>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <Form.Item label="No HP" name="candidate_phone">
            <Input placeholder="+62812..." />
          </Form.Item>
          <Form.Item label="LinkedIn" name="linkedin_url">
            <Input placeholder="https://linkedin.com/in/..." />
          </Form.Item>
        </div>
        <Form.Item label="CV / Resume URL" name="resume_url">
          <Input placeholder="https://drive.google.com/... (opsional)" />
        </Form.Item>
        <Form.Item label="Source" name="source" rules={[{ required: true }]}>
          <Select options={SOURCE_OPTIONS} />
        </Form.Item>
        <Form.Item label="Cover Letter / Catatan (opsional)" name="notes">
          <Input.TextArea
            rows={3}
            placeholder="Mantan rekan kerja saya, sudah 5 tahun di Tokopedia..."
          />
        </Form.Item>
        <Button type="primary" htmlType="submit" block loading={mutation.isPending}>
          Submit Refer
        </Button>
      </Form>
    </Modal>
  );
}

export default function JobBoardPage() {
  const [referJob, setReferJob] = useState<JobOpeningListItem | null>(null);
  const [search, setSearch] = useState('');
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['job-board-openings'],
    queryFn: () => listJobOpenings({ status: 'OPEN', page: 1, page_size: 50 }),
  });

  const items = query.data?.items ?? [];
  const filtered = search
    ? items.filter(
        (j) =>
          j.title.toLowerCase().includes(search.toLowerCase()) ||
          (j.department_name ?? '').toLowerCase().includes(search.toLowerCase()) ||
          (j.position_name ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : items;

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1000, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <Title level={3} style={{ margin: 0 }}>
          <CompassOutlined /> Job Board IDE Asia
        </Title>
        <Text type="secondary">
          Posisi yang sedang dibuka. Anda dapat refer kandidat ke HR — siapapun
          yang berhasil dihired akan tercatat sebagai referrer Anda.
        </Text>
      </div>

      <div
        style={{
          background: 'rgba(0,113,227,0.04)',
          border: '1px solid rgba(0,113,227,0.15)',
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
          fontSize: 12,
        }}
      >
        💡 <strong>Tip:</strong> Refer dengan menyertakan CV link akan mempercepat
        proses screening. HR akan menghubungi kandidat dalam 3-5 hari kerja.
      </div>

      <Input.Search
        placeholder="Cari posisi atau departemen..."
        allowClear
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ marginBottom: 16, maxWidth: 480 }}
      />

      {query.isLoading ? (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <Spin>
            <div style={{ minHeight: 24 }} />
          </Spin>
        </div>
      ) : filtered.length === 0 ? (
        <Empty
          description={
            search
              ? `Tidak ada lowongan yang match dengan "${search}"`
              : 'Saat ini belum ada lowongan terbuka. Cek kembali nanti!'
          }
          style={{ padding: 60 }}
        />
      ) : (
        <>
          <div style={{ marginBottom: 8, fontSize: 12, color: 'var(--ide-ink2)' }}>
            <Tag color="green">{filtered.length}</Tag> lowongan terbuka
          </div>
          {filtered.map((job) => (
            <JobCard key={job.id} job={job} onRefer={setReferJob} />
          ))}
        </>
      )}

      <ReferModal
        job={referJob}
        open={referJob !== null}
        onClose={() => setReferJob(null)}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ['job-board-openings'] });
        }}
      />
    </div>
  );
}
