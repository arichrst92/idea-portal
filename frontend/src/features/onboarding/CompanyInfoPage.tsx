/**
 * CompanyInfoPage — TSK-045 (US-GL-008).
 *
 * Layout: sidebar dengan category counts + main article list/detail.
 * All authenticated users read. Edit hanya HR (employee.edit permission).
 */

import { FileTextOutlined, PushpinFilled, SearchOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Empty, Input, Segmented, Spin, Tag, Typography } from 'antd';
import dayjs from 'dayjs';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

import { apiClient } from '@/api/client';

const { Title, Text, Paragraph } = Typography;

interface Article {
  id: string;
  title: string;
  slug: string;
  category: string;
  content: string;
  summary: string | null;
  is_published: boolean;
  is_pinned: boolean;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

interface CategoryCount {
  category: string;
  count: number;
}

const CATEGORY_META: Record<string, { label: string; icon: string }> = {
  HR_POLICY: { label: 'HR Policy', icon: '👔' },
  IT_POLICY: { label: 'IT Policy', icon: '💻' },
  SOP: { label: 'Standard Operating Procedure', icon: '📋' },
  HANDBOOK: { label: 'Employee Handbook', icon: '📘' },
  CODE_OF_CONDUCT: { label: 'Code of Conduct', icon: '⚖️' },
  VISION_MISSION: { label: 'Vision & Mission', icon: '🎯' },
  TEMPLATE: { label: 'Document Templates', icon: '📝' },
  ONBOARDING: { label: 'Onboarding', icon: '🚀' },
  OTHER: { label: 'Other', icon: '📄' },
};

export default function CompanyInfoPage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string | undefined>();
  const [selectedArticle, setSelectedArticle] = useState<Article | null>(null);

  const listQuery = useQuery({
    queryKey: ['cms-articles', category, search],
    queryFn: async () => {
      const r = await apiClient.get<Article[]>('/api/v1/cms/articles', {
        params: {
          category,
          search: search || undefined,
          published_only: true,
        },
      });
      return r.data;
    },
  });

  const catQuery = useQuery({
    queryKey: ['cms-categories'],
    queryFn: async () => {
      const r = await apiClient.get<{ categories: CategoryCount[] }>(
        '/api/v1/cms/articles/categories'
      );
      return r.data.categories;
    },
  });

  return (
    <div style={{ padding: '20px 24px', maxWidth: 1280, margin: '0 auto' }}>
      <div style={{ marginBottom: 18 }}>
        <Title level={3} style={{ margin: 0 }}>
          📚 Company Info Portal
        </Title>
        <Text type="secondary">
          Per US-GL-008: HR policies, SOPs, handbook, vision/mission. Read access untuk
          semua karyawan, edit oleh HR/Operation.
        </Text>
      </div>

      <Input
        prefix={<SearchOutlined />}
        placeholder="Cari artikel, kebijakan, SOP..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        allowClear
        size="large"
        style={{ maxWidth: 540, marginBottom: 16 }}
      />

      <div style={{ display: 'grid', gridTemplateColumns: '220px 1fr', gap: 20 }}>
        {/* Sidebar */}
        <div>
          <Segmented
            vertical
            block
            value={category ?? 'ALL'}
            onChange={(v) => setCategory(v === 'ALL' ? undefined : (v as string))}
            options={[
              { label: 'Semua', value: 'ALL' },
              ...(catQuery.data ?? []).map((c) => ({
                label: (
                  <span>
                    {CATEGORY_META[c.category]?.icon ?? '📄'}{' '}
                    {CATEGORY_META[c.category]?.label ?? c.category}{' '}
                    <Tag style={{ marginLeft: 4 }}>{c.count}</Tag>
                  </span>
                ),
                value: c.category,
              })),
            ]}
          />
        </div>

        {/* Main content */}
        <div>
          {selectedArticle ? (
            <div
              style={{
                background: 'var(--ide-surface, white)',
                border: '1px solid var(--ide-border, #E8E8ED)',
                borderRadius: 10,
                padding: 24,
              }}
            >
              <button
                onClick={() => setSelectedArticle(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--ide-blue, #0071E3)',
                  cursor: 'pointer',
                  marginBottom: 12,
                  padding: 0,
                  fontSize: 13,
                }}
              >
                ← Kembali ke daftar
              </button>
              <Tag>{CATEGORY_META[selectedArticle.category]?.label ?? selectedArticle.category}</Tag>
              {selectedArticle.is_pinned && (
                <Tag color="orange" icon={<PushpinFilled />}>
                  Pinned
                </Tag>
              )}
              <Title level={3} style={{ marginTop: 12 }}>
                {selectedArticle.title}
              </Title>
              <Text type="secondary" style={{ fontSize: 12 }}>
                Updated {dayjs(selectedArticle.updated_at).format('DD MMM YYYY')}
              </Text>
              <div className="markdown-body" style={{ marginTop: 16, fontSize: 14, lineHeight: 1.7 }}>
                <ReactMarkdown>{selectedArticle.content}</ReactMarkdown>
              </div>
            </div>
          ) : listQuery.isLoading ? (
            <Spin>
              <div style={{ minHeight: 24 }} />
            </Spin>
          ) : listQuery.data && listQuery.data.length > 0 ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {listQuery.data.map((a) => {
                const meta = CATEGORY_META[a.category];
                return (
                  <div
                    key={a.id}
                    onClick={() => setSelectedArticle(a)}
                    style={{
                      background: 'var(--ide-surface, white)',
                      border: '1px solid var(--ide-border, #E8E8ED)',
                      borderRadius: 10,
                      padding: 16,
                      cursor: 'pointer',
                      transition: 'all 0.12s',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = 'var(--ide-blue, #0071E3)';
                      e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,113,227,0.06)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--ide-border, #E8E8ED)';
                      e.currentTarget.style.boxShadow = 'none';
                    }}
                  >
                    <div style={{ display: 'flex', gap: 12, alignItems: 'start' }}>
                      <span style={{ fontSize: 24 }}>{meta?.icon ?? '📄'}</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Text strong style={{ fontSize: 15 }}>
                            {a.title}
                          </Text>
                          {a.is_pinned && (
                            <Tag color="orange" icon={<PushpinFilled />} style={{ fontSize: 10 }}>
                              Pinned
                            </Tag>
                          )}
                          <Tag style={{ fontSize: 10 }}>{meta?.label ?? a.category}</Tag>
                        </div>
                        {a.summary && (
                          <Paragraph
                            type="secondary"
                            style={{ marginTop: 4, marginBottom: 4, fontSize: 13 }}
                            ellipsis={{ rows: 2 }}
                          >
                            {a.summary}
                          </Paragraph>
                        )}
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          Updated {dayjs(a.updated_at).format('DD MMM YYYY')}
                        </Text>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <Empty
              image={<FileTextOutlined style={{ fontSize: 48, color: 'var(--ide-ink3)' }} />}
              description={
                search
                  ? `Tidak ada artikel match dengan "${search}"`
                  : 'Belum ada artikel yang dipublish. HR akan tambah konten segera.'
              }
            />
          )}
        </div>
      </div>
    </div>
  );
}
