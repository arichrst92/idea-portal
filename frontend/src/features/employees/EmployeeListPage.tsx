/**
 * Employee List Page — TSK-013 FE
 *
 * Visual port dari GUI html/IDEA_EmployeeMgmtTK.html.
 * Design system: Plus Jakarta Sans + CSS variables di src/styles/tokens.css.
 *
 * Capabilities:
 * - KPI cards (total, by status)
 * - Search by NIK / name / email (debounced)
 * - Filter dropdowns (department, status, employee_type)
 * - Table grid dengan avatar gradient, status badges
 * - Pagination
 * - Click row → navigate ke /employees/:nik
 *
 * Acceptance:
 * - Konsumsi /api/v1/employees + /api/v1/departments
 * - Real-time filter (React Query refetch on filter change)
 * - Empty state kalau kosong
 * - Loading skeleton
 */

import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  type EmployeeListItem,
  type EmployeeStatus,
  type EmployeeType,
  avatarGradient,
  employeeStatusColor,
  employeeTypeColor,
  getInitials,
  listDepartments,
  listEmployees,
} from '@/api/organization';

const PAGE_SIZE = 25;

export default function EmployeeListPage() {
  const navigate = useNavigate();
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterDept, setFilterDept] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterType, setFilterType] = useState<string>('');
  const [page, setPage] = useState(1);

  // Debounce search input (250ms)
  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedSearch(searchInput), 250);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  // Reset page kalau filter berubah
  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, filterDept, filterStatus, filterType]);

  // Departments (untuk filter dropdown)
  const deptQuery = useQuery({
    queryKey: ['departments'],
    queryFn: listDepartments,
    staleTime: 5 * 60 * 1000,
  });

  // Employees list
  const empQuery = useQuery({
    queryKey: ['employees', debouncedSearch, filterDept, filterStatus, filterType, page],
    queryFn: () =>
      listEmployees({
        q: debouncedSearch || undefined,
        department_id: filterDept || undefined,
        status: (filterStatus as EmployeeStatus) || undefined,
        employee_type: (filterType as EmployeeType) || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    placeholderData: (prev) => prev,
  });

  const items = empQuery.data?.items ?? [];
  const total = empQuery.data?.total ?? 0;
  const totalPages = empQuery.data?.total_pages ?? 0;

  // KPI computation (simple: dari data yang sedang ditampilkan)
  const kpis = useMemo(() => {
    const byStatus: Record<string, number> = {};
    for (const e of items) {
      byStatus[e.status] = (byStatus[e.status] ?? 0) + 1;
    }
    return {
      total,
      active: byStatus['ACTIVE'] ?? 0,
      probation: byStatus['PROBATION'] ?? 0,
      onLeave: byStatus['ON_LEAVE'] ?? 0,
      alumni: byStatus['ALUMNI'] ?? 0,
    };
  }, [items, total]);

  return (
    <div className="ide-font" style={{ padding: '24px', background: 'var(--ide-bg)', minHeight: 'calc(100vh - 64px)' }}>
      {/* Breadcrumb + actions */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          gap: '14px',
          flexWrap: 'wrap',
        }}
      >
        <div>
          <div
            style={{
              fontSize: '12px',
              color: 'var(--ide-ink3)',
              fontWeight: 500,
              marginBottom: '4px',
            }}
          >
            Master Data <span style={{ margin: '0 6px' }}>/</span>{' '}
            <span style={{ color: 'var(--ide-ink)', fontWeight: 700 }}>Employee Management</span>
          </div>
          <div style={{ fontSize: '20px', fontWeight: 800, letterSpacing: '-0.4px' }}>
            Karyawan
          </div>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <ActionButton variant="secondary">📥 Export</ActionButton>
          <ActionButton variant="primary" onClick={() => navigate('/employees/new')}>
            + Tambah Karyawan
          </ActionButton>
        </div>
      </div>

      {/* KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(5, 1fr)',
          gap: '12px',
          marginBottom: '20px',
        }}
      >
        <KPICard label="Total Karyawan" value={kpis.total} />
        <KPICard label="Active" value={kpis.active} color="var(--ide-green)" />
        <KPICard label="Probation" value={kpis.probation} color="var(--ide-blue)" />
        <KPICard label="On Leave" value={kpis.onLeave} color="var(--ide-orange)" />
        <KPICard label="Alumni" value={kpis.alumni} color="var(--ide-ink3)" />
      </div>

      {/* Toolbar: search + filters */}
      <div
        style={{
          display: 'flex',
          gap: '10px',
          marginBottom: '16px',
          alignItems: 'center',
          flexWrap: 'wrap',
        }}
      >
        <SearchInput value={searchInput} onChange={setSearchInput} />
        <FilterSelect
          value={filterDept}
          onChange={setFilterDept}
          options={[
            { value: '', label: 'Semua Departemen' },
            ...(deptQuery.data?.map((d) => ({ value: d.id, label: d.name })) ?? []),
          ]}
        />
        <FilterSelect
          value={filterStatus}
          onChange={setFilterStatus}
          options={[
            { value: '', label: 'Semua Status' },
            { value: 'ACTIVE', label: 'Active' },
            { value: 'PROBATION', label: 'Probation' },
            { value: 'ON_LEAVE', label: 'On Leave' },
            { value: 'RESIGNED', label: 'Resigned' },
            { value: 'TERMINATED', label: 'Terminated' },
            { value: 'ALUMNI', label: 'Alumni' },
          ]}
        />
        <FilterSelect
          value={filterType}
          onChange={setFilterType}
          options={[
            { value: '', label: 'Semua Tipe' },
            { value: 'A', label: 'Internal' },
            { value: 'B', label: 'Outsource-IDEA' },
            { value: 'C', label: 'Outsource-Eksternal' },
          ]}
        />
        <div style={{ marginLeft: 'auto', fontSize: '12px', color: 'var(--ide-ink3)' }}>
          {total > 0 ? `${total} karyawan` : empQuery.isLoading ? 'Loading...' : 'Tidak ada hasil'}
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
        <TableHeader />
        {empQuery.isLoading && items.length === 0 ? (
          <LoadingRows />
        ) : items.length === 0 ? (
          <EmptyRow />
        ) : (
          items.map((emp) => (
            <EmployeeRow key={emp.nik} employee={emp} onClick={() => navigate(`/employees/${emp.nik}`)} />
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination current={page} total={totalPages} onChange={setPage} />
      )}
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────

function ActionButton({
  variant,
  children,
  onClick,
}: {
  variant: 'primary' | 'secondary';
  children: React.ReactNode;
  onClick?: () => void;
}) {
  const isPrimary = variant === 'primary';
  return (
    <button
      onClick={onClick}
      style={{
        padding: '8px 16px',
        borderRadius: 'var(--ide-rs)',
        fontSize: '13px',
        fontWeight: 600,
        cursor: 'pointer',
        fontFamily: 'var(--ide-font)',
        transition: 'all 0.15s',
        border: isPrimary ? 'none' : '1px solid var(--ide-border)',
        background: isPrimary ? 'var(--ide-blue)' : 'var(--ide-surface)',
        color: isPrimary ? '#fff' : 'var(--ide-ink)',
        boxShadow: isPrimary ? 'var(--ide-shadow-blue)' : 'none',
      }}
    >
      {children}
    </button>
  );
}

function KPICard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="ide-kpi">
      <div className="ide-kpi-val" style={color ? { color } : undefined}>
        {value.toLocaleString('id-ID')}
      </div>
      <div className="ide-kpi-lbl">{label}</div>
    </div>
  );
}

function SearchInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        background: 'var(--ide-surface)',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-rs)',
        padding: '8px 12px',
        width: '300px',
      }}
    >
      <span style={{ color: 'var(--ide-ink3)' }}>🔍</span>
      <input
        type="text"
        placeholder="Cari NIK, nama, atau email..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{
          border: 'none',
          outline: 'none',
          fontFamily: 'var(--ide-font)',
          fontSize: '13px',
          flex: 1,
          background: 'transparent',
          color: 'var(--ide-ink)',
        }}
      />
    </div>
  );
}

function FilterSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      style={{
        padding: '8px 12px',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-rs)',
        fontSize: '13px',
        fontFamily: 'var(--ide-font)',
        outline: 'none',
        background: 'var(--ide-surface)',
        color: 'var(--ide-ink)',
        cursor: 'pointer',
        minWidth: '160px',
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function TableHeader() {
  const cols = ['Karyawan', 'NIK', 'Departemen', 'Posisi', 'Status', 'Tipe'];
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '2.2fr 1fr 1.4fr 1.4fr 1fr 1fr',
        gap: '14px',
        padding: '14px 20px',
        background: 'var(--ide-bg)',
        borderBottom: '1px solid var(--ide-border)',
        fontSize: '10px',
        fontWeight: 700,
        color: 'var(--ide-ink3)',
        textTransform: 'uppercase',
        letterSpacing: '0.8px',
      }}
    >
      {cols.map((c) => (
        <div key={c}>{c}</div>
      ))}
    </div>
  );
}

function EmployeeRow({
  employee,
  onClick,
}: {
  employee: EmployeeListItem;
  onClick: () => void;
}) {
  const statusInfo = employeeStatusColor(employee.status);
  const typeInfo = employeeTypeColor(employee.employee_type);
  const initials = getInitials(employee.full_name);
  const gradient = avatarGradient(employee.nik);

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onClick()}
      style={{
        display: 'grid',
        gridTemplateColumns: '2.2fr 1fr 1.4fr 1.4fr 1fr 1fr',
        gap: '14px',
        padding: '14px 20px',
        borderBottom: '1px solid var(--ide-border2)',
        fontSize: '13px',
        alignItems: 'center',
        cursor: 'pointer',
        transition: 'background 0.12s',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--ide-bg)')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--ide-surface)')}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div className="ide-avatar ide-avatar-md" style={{ background: gradient }}>
          {initials}
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: '13px' }}>{employee.full_name}</div>
          {employee.email && (
            <div
              style={{
                fontSize: '11px',
                color: 'var(--ide-ink3)',
                fontWeight: 500,
              }}
            >
              {employee.email}
            </div>
          )}
        </div>
      </div>
      <div style={{ fontFamily: 'var(--ide-font-mono)', fontSize: '12px', fontWeight: 600 }}>
        {employee.nik}
      </div>
      <div>{employee.department_name ?? <Dash />}</div>
      <div>{employee.position_name ?? <Dash />}</div>
      <div>
        <span className={`ide-tag ${statusInfo.className}`}>{statusInfo.label}</span>
      </div>
      <div>
        <span className={`ide-tag ${typeInfo.className}`}>{typeInfo.label}</span>
      </div>
    </div>
  );
}

function Dash() {
  return <span style={{ color: 'var(--ide-ink3)' }}>—</span>;
}

function LoadingRows() {
  return (
    <div style={{ padding: '40px', textAlign: 'center', color: 'var(--ide-ink3)' }}>
      Memuat data...
    </div>
  );
}

function EmptyRow() {
  return (
    <div style={{ padding: '60px 20px', textAlign: 'center' }}>
      <div style={{ fontSize: '40px', marginBottom: '12px' }}>👥</div>
      <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: '4px' }}>
        Tidak ada karyawan
      </div>
      <div style={{ fontSize: '12px', color: 'var(--ide-ink3)' }}>
        Coba ubah filter atau tambah karyawan baru.
      </div>
    </div>
  );
}

function Pagination({
  current,
  total,
  onChange,
}: {
  current: number;
  total: number;
  onChange: (p: number) => void;
}) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '6px',
        marginTop: '16px',
      }}
    >
      <PageBtn disabled={current <= 1} onClick={() => onChange(current - 1)}>
        ←
      </PageBtn>
      <span
        style={{
          padding: '6px 12px',
          fontSize: '12px',
          color: 'var(--ide-ink2)',
          fontWeight: 600,
        }}
      >
        Halaman {current} dari {total}
      </span>
      <PageBtn disabled={current >= total} onClick={() => onChange(current + 1)}>
        →
      </PageBtn>
    </div>
  );
}

function PageBtn({
  disabled,
  children,
  onClick,
}: {
  disabled: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      style={{
        padding: '6px 12px',
        background: disabled ? 'var(--ide-bg)' : 'var(--ide-surface)',
        border: '1px solid var(--ide-border)',
        borderRadius: 'var(--ide-rs)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: '13px',
        fontFamily: 'var(--ide-font)',
        color: disabled ? 'var(--ide-ink3)' : 'var(--ide-ink)',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {children}
    </button>
  );
}
