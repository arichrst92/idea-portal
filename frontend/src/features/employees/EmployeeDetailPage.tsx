/**
 * Employee Detail Page — TSK-013 FE Chunk C
 *
 * Visual port dari GUI html/IDEA_ProfilSaya.html (hero header + info grid).
 * Reuse tokens.css design system.
 *
 * Layout:
 * - Hero header: gradient blue→teal, photo placeholder, name + position + tags
 * - Info sections: Personal Info, Employment, Financial
 * - Action bar (RBAC-aware): Edit, Promote, Mutate, Soft Delete
 * - History timeline: org changes (promote/mutate audit trail)
 *
 * Routes consumed:
 * - GET /api/v1/employees/{nik}
 * - GET /api/v1/employees/{nik}/history
 */

import {
  ArrowLeftOutlined,
  EditOutlined,
  RiseOutlined,
  SwapOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Button, Modal, Spin, message } from 'antd';
import { useNavigate, useParams } from 'react-router-dom';

import {
  avatarGradient,
  employeeStatusColor,
  employeeTypeColor,
  getEmployee,
  getEmployeeHistory,
  getInitials,
  softDeleteEmployee,
  type OrgChange,
} from '@/api/organization';
import { useAuthStore } from '@/store/auth';

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  try {
    const d = new Date(value);
    return d.toLocaleDateString('id-ID', { day: '2-digit', month: 'short', year: 'numeric' });
  } catch {
    return value;
  }
}

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 16, padding: '10px 0', borderBottom: '1px solid var(--ide-border2)' }}>
      <div style={{ fontSize: 12, color: 'var(--ide-ink3)', fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ide-ink)', textAlign: 'right' }}>{value || <span style={{ color: 'var(--ide-ink3)', fontWeight: 400 }}>—</span>}</div>
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div
      style={{
        background: 'var(--ide-surface)',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-r)',
        padding: '18px 22px',
        marginBottom: 14,
      }}
    >
      <div
        style={{
          fontSize: 10,
          fontWeight: 700,
          color: 'var(--ide-ink3)',
          textTransform: 'uppercase',
          letterSpacing: '0.8px',
          marginBottom: 8,
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function ChangeRow({ change }: { change: OrgChange }) {
  const before = change.before_snapshot || {};
  const after = change.after_snapshot || {};
  const diffKeys = new Set([...Object.keys(before), ...Object.keys(after)]);
  const isPromotion = change.change_type === 'PROMOTION';

  return (
    <div
      style={{
        padding: '14px 0',
        borderBottom: '1px solid var(--ide-border2)',
        display: 'flex',
        gap: 14,
      }}
    >
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 9,
          background: isPromotion ? 'var(--ide-green-soft)' : 'var(--ide-blue-soft)',
          color: isPromotion ? 'var(--ide-green)' : 'var(--ide-blue)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
          fontSize: 14,
        }}
      >
        {isPromotion ? <RiseOutlined /> : <SwapOutlined />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
          <div style={{ fontWeight: 700, fontSize: 13 }}>
            {isPromotion ? 'Promotion' : 'Mutation'}
          </div>
          <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>{formatDate(change.effective_date)}</div>
        </div>
        {change.reason && (
          <div style={{ fontSize: 12, color: 'var(--ide-ink2)', marginBottom: 6 }}>{change.reason}</div>
        )}
        <div style={{ fontSize: 11, color: 'var(--ide-ink3)', fontFamily: 'var(--ide-font-mono)' }}>
          {[...diffKeys].map((k) => {
            const b = (before as Record<string, unknown>)[k];
            const a = (after as Record<string, unknown>)[k];
            if (b === a) return null;
            return (
              <div key={k}>
                {k}: <span style={{ textDecoration: 'line-through', opacity: 0.6 }}>{String(b ?? '—')}</span>{' '}
                → <span style={{ color: 'var(--ide-ink)' }}>{String(a ?? '—')}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function EmployeeDetailPage() {
  const { nik = '' } = useParams<{ nik: string }>();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const isExecutive = user?.roles.some(
    (r) => r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA',
  ) ?? false;

  const empQuery = useQuery({
    queryKey: ['employee', nik],
    queryFn: () => getEmployee(nik),
    enabled: !!nik,
  });

  const historyQuery = useQuery({
    queryKey: ['employee-history', nik],
    queryFn: () => getEmployeeHistory(nik),
    enabled: !!nik,
  });

  if (empQuery.isLoading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (empQuery.isError || !empQuery.data) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ fontSize: 14, color: 'var(--ide-ink2)', marginBottom: 12 }}>
          Karyawan dengan NIK <strong>{nik}</strong> tidak ditemukan.
        </div>
        <Button onClick={() => navigate('/employees')}>← Kembali ke daftar</Button>
      </div>
    );
  }

  const emp = empQuery.data;
  const statusTag = employeeStatusColor(emp.status);
  const typeTag = employeeTypeColor(emp.employee_type);

  const handleDelete = () => {
    Modal.confirm({
      title: 'Hapus Karyawan',
      content: `Soft-delete ${emp.full_name} (${emp.nik})? Status akan diubah ke ALUMNI dan user dinonaktifkan. Data tetap di-archive.`,
      okText: 'Soft Delete',
      okType: 'danger',
      cancelText: 'Batal',
      onOk: async () => {
        try {
          await softDeleteEmployee(emp.nik);
          message.success('Karyawan diarsipkan');
          navigate('/employees');
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: { message?: string } } } };
          message.error(err.response?.data?.detail?.message || 'Gagal soft-delete');
        }
      },
    });
  };

  return (
    <div className="ide-font" style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* Back button */}
      <Button
        type="text"
        icon={<ArrowLeftOutlined />}
        onClick={() => navigate('/employees')}
        style={{ marginBottom: 14, fontWeight: 600 }}
      >
        Daftar Karyawan
      </Button>

      {/* Hero header */}
      <div
        style={{
          background: 'linear-gradient(135deg, #007AFF 0%, #32D2F2 100%)',
          borderRadius: 'var(--ide-r)',
          padding: 28,
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          marginBottom: 18,
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            right: -40,
            top: -40,
            width: 200,
            height: 200,
            background: 'rgba(255,255,255,0.08)',
            borderRadius: '50%',
          }}
        />
        <div
          style={{
            width: 90,
            height: 90,
            borderRadius: '50%',
            background: avatarGradient(emp.nik),
            border: '3px solid rgba(255,255,255,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 32,
            fontWeight: 800,
            flexShrink: 0,
            position: 'relative',
            zIndex: 1,
          }}
        >
          {getInitials(emp.full_name)}
        </div>
        <div style={{ flex: 1, position: 'relative', zIndex: 1 }}>
          <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: -0.6, marginBottom: 4 }}>
            {emp.full_name}
          </div>
          <div style={{ fontSize: 14, opacity: 0.9, marginBottom: 10 }}>
            {emp.position_name || 'Belum ada posisi'} · {emp.department_name || 'Belum ada departemen'}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <div className="ide-tag" style={{ background: 'rgba(255,255,255,0.2)', color: '#fff', backdropFilter: 'blur(8px)' }}>
              NIK · {emp.nik}
            </div>
            <div className="ide-tag" style={{ background: 'rgba(255,255,255,0.2)', color: '#fff', backdropFilter: 'blur(8px)' }}>
              {statusTag.label}
            </div>
            <div className="ide-tag" style={{ background: 'rgba(255,255,255,0.2)', color: '#fff', backdropFilter: 'blur(8px)' }}>
              {typeTag.label}
            </div>
          </div>
        </div>
        <div style={{ position: 'relative', zIndex: 1, textAlign: 'right' }}>
          <div style={{ fontSize: 11, opacity: 0.85, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Joined
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'var(--ide-font-mono)' }}>
            {formatDate(emp.joined_date)}
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
        <Button
          icon={<EditOutlined />}
          onClick={() => navigate(`/employees/${emp.nik}/edit`)}
          disabled={!isExecutive}
        >
          Edit
        </Button>
        <Button
          icon={<RiseOutlined />}
          onClick={() => message.info('Promote form — coming next session')}
          disabled={!isExecutive}
        >
          Promote
        </Button>
        <Button
          icon={<SwapOutlined />}
          onClick={() => message.info('Mutate form — coming next session')}
          disabled={!isExecutive}
        >
          Mutate
        </Button>
        <Button
          icon={<DeleteOutlined />}
          danger
          onClick={handleDelete}
          disabled={!isExecutive}
          style={{ marginLeft: 'auto' }}
        >
          Soft Delete
        </Button>
      </div>

      {/* Info grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <SectionCard title="Personal Info">
          <InfoRow label="Full Name" value={emp.full_name} />
          <InfoRow label="Email" value={emp.email} />
          <InfoRow label="Phone" value={emp.phone_number} />
          <InfoRow label="Date of Birth" value={formatDate(emp.date_of_birth)} />
          <InfoRow label="Gender" value={emp.gender} />
          <InfoRow label="Address" value={emp.address} />
          <InfoRow label="Emergency Contact" value={emp.emergency_contact} />
        </SectionCard>

        <SectionCard title="Employment">
          <InfoRow label="NIK" value={<span style={{ fontFamily: 'var(--ide-font-mono)' }}>{emp.nik}</span>} />
          <InfoRow label="Type" value={typeTag.label} />
          <InfoRow label="Status" value={<span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>} />
          <InfoRow label="Department" value={emp.department_name} />
          <InfoRow label="Position" value={emp.position_name} />
          <InfoRow label="Joined" value={formatDate(emp.joined_date)} />
          <InfoRow label="Probation End" value={formatDate(emp.probation_end_date)} />
          {emp.last_working_day && <InfoRow label="Last Working Day" value={formatDate(emp.last_working_day)} />}
        </SectionCard>

        <SectionCard title="Financial (basic)">
          <InfoRow label="Bank" value={emp.bank_name} />
          <InfoRow label="Account" value={emp.bank_account ? <span style={{ fontFamily: 'var(--ide-font-mono)' }}>{emp.bank_account}</span> : null} />
          <InfoRow label="NPWP" value={emp.npwp ? <span style={{ fontFamily: 'var(--ide-font-mono)' }}>{emp.npwp}</span> : null} />
        </SectionCard>

        <SectionCard title="Organizational History">
          {historyQuery.isLoading && <Spin />}
          {historyQuery.data && historyQuery.data.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--ide-ink3)', padding: '8px 0' }}>
              Belum ada perubahan organisasi (promosi/mutasi).
            </div>
          )}
          {historyQuery.data?.map((c) => <ChangeRow key={c.id} change={c} />)}
        </SectionCard>
      </div>
    </div>
  );
}
