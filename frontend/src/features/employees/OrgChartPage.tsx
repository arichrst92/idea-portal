/**
 * Org Chart Page — TSK-014
 *
 * Visualisasi hierarki dari Employee.supervisor_id.
 * Approach: vertical tree dengan recursive rendering + CSS connector lines.
 * (Bukan absolute positioning seperti mockup IDEA_OrgChart.html — lebih
 * maintainable dan adaptive ke jumlah node).
 *
 * Capabilities:
 * - Dept filter (semua dept atau filter per dept)
 * - Tree nodes: avatar gradient, name, position, dept tag
 * - Click node → navigate ke /employees/:nik
 * - Collapse/expand subtree
 * - Empty state kalau dept belum ada employee
 */

import {
  CaretDownOutlined,
  CaretRightOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Empty, Select, Spin, Tag } from 'antd';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  avatarGradient,
  employeeStatusColor,
  getInitials,
  getOrgChart,
  listDepartments,
  type OrgChartNode as Node,
} from '@/api/organization';

interface NodeCardProps {
  node: Node;
  depth: number;
  expanded: Set<string>;
  toggle: (id: string) => void;
  onClick: (nik: string) => void;
}

function NodeCard({ node, depth, expanded, toggle, onClick }: NodeCardProps) {
  const isExpanded = expanded.has(node.id);
  const hasChildren = node.children.length > 0;
  const statusTag = employeeStatusColor(node.status);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
      {/* Card */}
      <div
        onClick={() => onClick(node.nik)}
        style={{
          background: 'var(--ide-surface)',
          border: '1.5px solid var(--ide-border)',
          borderRadius: 'var(--ide-rm)',
          padding: 14,
          cursor: 'pointer',
          width: 220,
          boxShadow: 'var(--ide-shadow-sm)',
          transition: 'all 0.15s',
          position: 'relative',
          marginBottom: hasChildren ? 6 : 0,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-2px)';
          e.currentTarget.style.boxShadow = 'var(--ide-shadow-md)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = 'var(--ide-shadow-sm)';
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <div
            className="ide-avatar ide-avatar-md"
            style={{ background: avatarGradient(node.nik) }}
          >
            {getInitials(node.full_name)}
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 700,
                lineHeight: 1.2,
                color: 'var(--ide-ink)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {node.full_name}
            </div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--ide-ink3)',
                fontFamily: 'var(--ide-font-mono)',
              }}
            >
              {node.nik}
            </div>
          </div>
        </div>

        <div
          style={{
            fontSize: 11,
            color: 'var(--ide-ink2)',
            marginBottom: 8,
          }}
        >
          {node.position_name || '—'}
          {node.position_level !== null && (
            <span style={{ color: 'var(--ide-ink3)' }}> · L{node.position_level}</span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className={`ide-tag ${statusTag.className}`}>{statusTag.label}</span>
          {node.department_name && (
            <span className="ide-tag ide-tag-gray">{node.department_name}</span>
          )}
          {node.direct_reports_count > 0 && (
            <span
              className="ide-tag ide-tag-blue"
              style={{ marginLeft: 'auto' }}
            >
              <TeamOutlined style={{ fontSize: 9, marginRight: 2 }} />
              {node.direct_reports_count}
            </span>
          )}
        </div>
      </div>

      {/* Expand/Collapse + connector + children */}
      {hasChildren && (
        <>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              toggle(node.id);
            }}
            style={{
              width: 22,
              height: 22,
              borderRadius: '50%',
              background: 'var(--ide-surface)',
              border: '1.5px solid var(--ide-border)',
              color: 'var(--ide-ink2)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              fontWeight: 700,
              boxShadow: 'var(--ide-shadow-sm)',
              marginBottom: 6,
            }}
            title={isExpanded ? 'Collapse' : 'Expand'}
          >
            {isExpanded ? <CaretDownOutlined /> : <CaretRightOutlined />}
          </button>

          {isExpanded && (
            <>
              {/* Vertical connector dari parent ke children container */}
              <div
                style={{
                  width: 2,
                  height: 18,
                  background: 'var(--ide-border)',
                }}
              />

              {/* Children row */}
              <div
                style={{
                  display: 'flex',
                  gap: 24,
                  position: 'relative',
                  paddingTop: 10,
                }}
              >
                {/* Horizontal connector line di atas semua children */}
                {node.children.length > 1 && (
                  <div
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 110,
                      right: 110,
                      height: 2,
                      background: 'var(--ide-border)',
                    }}
                  />
                )}
                {node.children.map((child) => (
                  <div
                    key={child.id}
                    style={{
                      position: 'relative',
                      paddingTop: 12,
                    }}
                  >
                    {/* Vertical connector dari horizontal line ke each child card */}
                    <div
                      style={{
                        position: 'absolute',
                        top: 0,
                        left: '50%',
                        width: 2,
                        height: 12,
                        background: 'var(--ide-border)',
                        transform: 'translateX(-50%)',
                      }}
                    />
                    <NodeCard
                      node={child}
                      depth={depth + 1}
                      expanded={expanded}
                      toggle={toggle}
                      onClick={onClick}
                    />
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function OrgChartPage() {
  const navigate = useNavigate();
  const [deptFilter, setDeptFilter] = useState<string | undefined>(undefined);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const deptQuery = useQuery({ queryKey: ['departments'], queryFn: listDepartments });
  const orgQuery = useQuery({
    queryKey: ['org-chart', deptFilter],
    queryFn: () => getOrgChart(deptFilter),
  });

  // Auto-expand semua node saat data baru load (default behavior)
  // User bisa collapse manual
  const data = orgQuery.data;
  if (data && expanded.size === 0) {
    const allIds = new Set<string>();
    const collect = (n: Node) => {
      allIds.add(n.id);
      n.children.forEach(collect);
    };
    data.roots.forEach(collect);
    if (allIds.size > 0) {
      setExpanded(allIds);
    }
  }

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleClickNode = (nik: string) => {
    navigate(`/employees/${nik}`);
  };

  return (
    <div className="ide-font" style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          marginBottom: 18,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 800, letterSpacing: -0.5, marginBottom: 4 }}>
            Org Chart
          </h2>
          <p style={{ fontSize: 13, color: 'var(--ide-ink2)' }}>
            Hierarki organisasi dibangun dari relasi supervisor — klik node untuk lihat detail karyawan.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Select
            style={{ width: 240 }}
            placeholder="Filter departemen"
            allowClear
            value={deptFilter}
            onChange={(v) => {
              setDeptFilter(v);
              setExpanded(new Set()); // reset expansion saat filter berubah
            }}
            options={(deptQuery.data || []).map((d) => ({
              value: d.id,
              label: `${d.code} · ${d.name} (${d.employee_count ?? 0})`,
            }))}
          />
        </div>
      </div>

      {/* KPI bar */}
      {data && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 12,
            marginBottom: 18,
          }}
        >
          <div className="ide-kpi">
            <div className="ide-kpi-val">{data.total_employees}</div>
            <div className="ide-kpi-lbl">Total Karyawan</div>
          </div>
          <div className="ide-kpi">
            <div className="ide-kpi-val">{data.roots.length}</div>
            <div className="ide-kpi-lbl">Top Nodes (No Supervisor)</div>
          </div>
          <div className="ide-kpi">
            <div className="ide-kpi-val">{data.department_name || 'Semua'}</div>
            <div className="ide-kpi-lbl">Scope Dept</div>
          </div>
        </div>
      )}

      {/* Tree */}
      <div
        style={{
          background: 'var(--ide-surface)',
          border: '1px solid var(--ide-border)',
          borderRadius: 'var(--ide-r)',
          padding: '36px 28px',
          overflowX: 'auto',
        }}
      >
        {orgQuery.isLoading && (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
          </div>
        )}

        {orgQuery.data && orgQuery.data.roots.length === 0 && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span style={{ color: 'var(--ide-ink2)' }}>
                {deptFilter ? 'Departemen ini belum ada karyawan' : 'Belum ada karyawan di sistem'}
              </span>
            }
          />
        )}

        {orgQuery.data && orgQuery.data.roots.length > 0 && (
          <div
            style={{
              display: 'flex',
              gap: 48,
              justifyContent: 'flex-start',
              minWidth: 'max-content',
            }}
          >
            {orgQuery.data.roots.map((root) => (
              <NodeCard
                key={root.id}
                node={root}
                depth={0}
                expanded={expanded}
                toggle={toggle}
                onClick={handleClickNode}
              />
            ))}
          </div>
        )}
      </div>

      {/* Hint legend */}
      {data && data.total_employees > 0 && (
        <div
          style={{
            marginTop: 14,
            padding: '8px 14px',
            background: 'var(--ide-blue-soft)',
            borderRadius: 'var(--ide-rs)',
            fontSize: 11,
            color: 'var(--ide-ink2)',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <UserOutlined style={{ color: 'var(--ide-blue)' }} />
          Atur supervisor karyawan via halaman detail → Mutate untuk membangun hierarki lebih dalam.
        </div>
      )}
    </div>
  );
}
