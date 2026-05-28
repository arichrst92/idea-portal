/**
 * Job Openings List — TSK-015 FE.
 * Visual reference: GUI html/IDEA_HiringModule.html
 *
 * Pakai design tokens dari src/styles/tokens.css.
 */

import { PlusOutlined, SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Button, Empty, Input, Select, Spin } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  jobStatusColor,
  listJobOpenings,
  type JobOpeningListItem,
  type JobOpeningStatus,
} from '@/api/hiring';
import { listDepartments } from '@/api/organization';

function formatDate(value: string | null): string {
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

function OpeningRow({ opening, onClick }: { opening: JobOpeningListItem; onClick: () => void }) {
  const statusTag = jobStatusColor(opening.status);
  const slotsProgress = opening.slots_needed > 0
    ? Math.round((opening.slots_filled / opening.slots_needed) * 100)
    : 0;

  return (
    <div
      onClick={onClick}
      style={{
        display: 'grid',
        gridTemplateColumns: '2.4fr 1.2fr 0.8fr 1fr 1fr 0.8fr',
        gap: 14,
        padding: '14px 20px',
        borderBottom: '1px solid var(--ide-border2)',
        fontSize: 13,
        alignItems: 'center',
        cursor: 'pointer',
        transition: 'background 0.12s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--ide-bg)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      <div>
        <div style={{ fontWeight: 700, color: 'var(--ide-ink)' }}>{opening.title}</div>
        <div style={{ fontSize: 11, color: 'var(--ide-ink3)', marginTop: 2 }}>
          {opening.position_name || 'No position set'}
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--ide-ink2)' }}>
        {opening.department_name || '—'}
      </div>
      <div>
        <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
      </div>
      <div>
        <div
          style={{
            fontSize: 11,
            color: 'var(--ide-ink2)',
            fontFamily: 'var(--ide-font-mono)',
            marginBottom: 4,
          }}
        >
          {opening.slots_filled} / {opening.slots_needed}
        </div>
        <div style={{ height: 4, background: 'var(--ide-bg)', borderRadius: 2, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              width: `${slotsProgress}%`,
              background: 'var(--ide-blue)',
              transition: 'width 0.2s',
            }}
          />
        </div>
      </div>
      <div style={{ fontSize: 12, color: 'var(--ide-ink2)' }}>
        {opening.application_count} kandidat
      </div>
      <div style={{ fontSize: 11, color: 'var(--ide-ink3)' }}>{formatDate(opening.deadline)}</div>
    </div>
  );
}

export default function JobOpeningListPage() {
  const navigate = useNavigate();
  const [statusFilter, setStatusFilter] = useState<JobOpeningStatus | undefined>(undefined);
  const [deptFilter, setDeptFilter] = useState<string | undefined>(undefined);
  const [search, setSearch] = useState('');

  const deptQuery = useQuery({ queryKey: ['departments'], queryFn: listDepartments });
  const openingsQuery = useQuery({
    queryKey: ['job-openings', deptFilter, statusFilter],
    queryFn: () =>
      listJobOpenings({
        department_id: deptFilter,
        status: statusFilter,
        page_size: 100,
      }),
  });

  const items = openingsQuery.data?.items || [];
  const filtered = search
    ? items.filter((o) =>
        o.title.toLowerCase().includes(search.toLowerCase()) ||
        (o.position_name || '').toLowerCase().includes(search.toLowerCase()),
      )
    : items;

  // KPIs
  const totalOpen = items.filter((o) => o.status === 'OPEN').length;
  const totalDraft = items.filter((o) => o.status === 'DRAFT').length;
  const totalPending = items.filter((o) => o.status === 'PENDING_APPROVAL').length;
  const totalFilled = items.filter((o) => o.status === 'FILLED').length;
  const totalApplications = items.reduce((acc, o) => acc + o.application_count, 0);

  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 18,
          gap: 12,
          flexWrap: 'wrap',
        }}
      >
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
            Hiring · Job Openings
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
            Kelola lowongan, approval, dan pipeline kandidat.
          </p>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/hiring/new')}
          style={{ background: 'var(--ide-blue)', borderColor: 'var(--ide-blue)', fontWeight: 600 }}
        >
          Tambah Lowongan
        </Button>
      </div>

      {/* KPIs */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: 12,
          marginBottom: 18,
        }}
      >
        <div className="ide-kpi">
          <div className="ide-kpi-val">{items.length}</div>
          <div className="ide-kpi-lbl">Total Openings</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-green)' }}>
            {totalOpen}
          </div>
          <div className="ide-kpi-lbl">Open</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-orange)' }}>
            {totalPending}
          </div>
          <div className="ide-kpi-lbl">Pending Approval</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-ink3)' }}>
            {totalDraft + totalFilled}
          </div>
          <div className="ide-kpi-lbl">Draft / Filled</div>
        </div>
        <div className="ide-kpi">
          <div className="ide-kpi-val" style={{ color: 'var(--ide-blue)' }}>
            {totalApplications}
          </div>
          <div className="ide-kpi-lbl">Total Kandidat</div>
        </div>
      </div>

      {/* Toolbar */}
      <div
        style={{
          display: 'flex',
          gap: 10,
          marginBottom: 14,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        <Input
          prefix={<SearchOutlined style={{ color: 'var(--ide-ink3)' }} />}
          placeholder="Cari judul lowongan / posisi..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          placeholder="Semua Departemen"
          style={{ width: 200 }}
          allowClear
          value={deptFilter}
          onChange={(v) => setDeptFilter(v)}
          options={(deptQuery.data || []).map((d) => ({
            value: d.id,
            label: `${d.code} · ${d.name}`,
          }))}
        />
        <Select
          placeholder="Semua Status"
          style={{ width: 180 }}
          allowClear
          value={statusFilter}
          onChange={(v) => setStatusFilter(v as JobOpeningStatus)}
          options={[
            { value: 'DRAFT', label: 'Draft' },
            { value: 'PENDING_APPROVAL', label: 'Pending Approval' },
            { value: 'OPEN', label: 'Open' },
            { value: 'FILLED', label: 'Filled' },
            { value: 'CANCELLED', label: 'Cancelled' },
            { value: 'CLOSED', label: 'Closed' },
          ]}
        />
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
        {/* Header row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '2.4fr 1.2fr 0.8fr 1fr 1fr 0.8fr',
            gap: 14,
            padding: '12px 20px',
            background: 'var(--ide-bg)',
            borderBottom: '1px solid var(--ide-border)',
            fontSize: 10,
            fontWeight: 700,
            color: 'var(--ide-ink3)',
            textTransform: 'uppercase',
            letterSpacing: '0.8px',
          }}
        >
          <div>Posisi</div>
          <div>Departemen</div>
          <div>Status</div>
          <div>Slot Terisi</div>
          <div>Kandidat</div>
          <div>Deadline</div>
        </div>

        {openingsQuery.isLoading && (
          <div style={{ padding: 40, textAlign: 'center' }}>
            <Spin />
          </div>
        )}

        {openingsQuery.data && filtered.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span style={{ color: 'var(--ide-ink2)' }}>
                {search ? `Tidak ada lowongan match "${search}"` : 'Belum ada lowongan'}
              </span>
            }
            style={{ padding: '40px 20px' }}
          />
        )}

        {filtered.map((o) => (
          <OpeningRow key={o.id} opening={o} onClick={() => navigate(`/hiring/${o.id}`)} />
        ))}
      </div>
    </div>
  );
}
