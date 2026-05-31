/**
 * Global Search modal — TSK-012.
 *
 * Triggered by:
 * - Cmd+K (Mac) / Ctrl+K (Win/Linux)
 * - Custom event 'open-global-search' dari AppShell topbar search button
 *
 * Features:
 * - Debounced search input (250ms)
 * - Results grouped by type (User / Employee / Project)
 * - Keyboard navigation: ↑↓ arrow keys, Enter, Esc
 * - Click result → navigate to url + close modal
 */

import { FileTextOutlined, ProjectOutlined, SearchOutlined, UserOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Empty, Input, List, Modal, Space, Spin, Tag, Typography } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { globalSearch, type SearchResult, type SearchResultType } from '@/api/search';
import { useAuthStore } from '@/store/auth';

const { Text } = Typography;

const TYPE_LABEL: Record<SearchResultType, string> = {
  user: 'User',
  employee: 'Employee',
  project: 'Project',
};

const TYPE_ICON: Record<SearchResultType, React.ReactNode> = {
  user: <UserOutlined />,
  employee: <FileTextOutlined />,
  project: <ProjectOutlined />,
};

const TYPE_COLOR: Record<SearchResultType, string> = {
  user: 'blue',
  employee: 'green',
  project: 'purple',
};

function useDebounced<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);
  useEffect(() => {
    const t = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debouncedValue;
}

export function GlobalSearch() {
  const navigate = useNavigate();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const debouncedQuery = useDebounced(query, 250);

  const { data, isFetching } = useQuery({
    queryKey: ['global-search', debouncedQuery],
    queryFn: () => globalSearch(debouncedQuery),
    enabled: open && debouncedQuery.trim().length >= 2,
    staleTime: 30_000,
  });

  const results = data?.results ?? [];

  // Reset state saat modal close
  useEffect(() => {
    if (!open) {
      setQuery('');
      setHighlightIndex(0);
    }
  }, [open]);

  // Reset highlight saat results berubah
  useEffect(() => {
    setHighlightIndex(0);
  }, [results.length]);

  // ⌘K / Ctrl+K shortcut
  useEffect(() => {
    if (!isAuthenticated) return;

    const handler = (e: KeyboardEvent) => {
      // Don't trigger inside input/textarea (kecuali Esc)
      const target = e.target as HTMLElement | null;
      const isTyping = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA');

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === 'Escape' && open && !isTyping) {
        setOpen(false);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isAuthenticated, open]);

  // Custom event trigger dari AppShell topbar
  useEffect(() => {
    const handler = () => setOpen(true);
    window.addEventListener('open-global-search', handler);
    return () => window.removeEventListener('open-global-search', handler);
  }, []);

  // Auto-focus input saat modal open
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 100);
      return () => clearTimeout(t);
    }
  }, [open]);

  // Keyboard navigation di results
  useEffect(() => {
    if (!open) return;

    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setHighlightIndex((i) => Math.min(i + 1, Math.max(0, results.length - 1)));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setHighlightIndex((i) => Math.max(0, i - 1));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const target = results[highlightIndex];
        if (target) {
          navigate(target.url);
          setOpen(false);
        }
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, results, highlightIndex, navigate]);

  // Group results by type
  const grouped = results.reduce<Record<SearchResultType, SearchResult[]>>(
    (acc, r) => {
      if (!acc[r.type]) acc[r.type] = [];
      acc[r.type].push(r);
      return acc;
    },
    { user: [], employee: [], project: [] },
  );

  const showEmpty = !isFetching && debouncedQuery.length >= 2 && results.length === 0;
  const showHint = debouncedQuery.length < 2;

  return (
    <Modal
      open={open}
      onCancel={() => setOpen(false)}
      footer={null}
      closable={false}
      width={600}
      style={{ top: 80 }}
      destroyOnHidden
      maskClosable
    >
      <Input
        ref={inputRef as React.RefObject<HTMLInputElement>}
        size="large"
        prefix={<SearchOutlined style={{ color: '#86868B' }} aria-hidden="true" />}
        suffix={isFetching ? <Spin size="small" /> : <Text type="secondary" style={{ fontSize: 11 }}>esc</Text>}
        placeholder="Cari NIK, nama karyawan, atau project..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        autoFocus
        aria-label="Global search input"
      />

      <div style={{ marginTop: 16, maxHeight: 400, overflow: 'auto' }}>
        {showHint && (
          <Text type="secondary" style={{ fontSize: 13, padding: 20, display: 'block', textAlign: 'center' }}>
            Ketik minimal 2 karakter untuk mulai search. Tekan{' '}
            <Text keyboard>↑</Text> <Text keyboard>↓</Text> untuk navigasi,{' '}
            <Text keyboard>Enter</Text> untuk pilih, <Text keyboard>Esc</Text> untuk tutup.
          </Text>
        )}

        {showEmpty && (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={`Tidak ada hasil untuk "${debouncedQuery}"`}
          />
        )}

        {(['user', 'employee', 'project'] as SearchResultType[]).map((type) => {
          const items = grouped[type];
          if (items.length === 0) return null;
          return (
            <div key={type} style={{ marginBottom: 16 }}>
              <Text
                strong
                style={{
                  fontSize: 11,
                  textTransform: 'uppercase',
                  letterSpacing: 1,
                  color: 'var(--ink3, #86868B)',
                  padding: '0 8px',
                  display: 'block',
                  marginBottom: 4,
                }}
              >
                {TYPE_LABEL[type]} ({items.length})
              </Text>
              <List
                size="small"
                dataSource={items}
                renderItem={(item) => {
                  const overallIndex = results.findIndex(
                    (r) => r.type === item.type && r.id === item.id,
                  );
                  const isHighlighted = overallIndex === highlightIndex;
                  return (
                    <List.Item
                      onClick={() => {
                        navigate(item.url);
                        setOpen(false);
                      }}
                      style={{
                        cursor: 'pointer',
                        padding: '8px 12px',
                        borderRadius: 6,
                        background: isHighlighted ? 'var(--bl, #E8F1FF)' : 'transparent',
                        transition: 'background 0.1s',
                      }}
                      onMouseEnter={() => setHighlightIndex(overallIndex)}
                    >
                      <Space>
                        <Tag color={TYPE_COLOR[item.type]} icon={TYPE_ICON[item.type]}>
                          {TYPE_LABEL[item.type]}
                        </Tag>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: 13 }}>{item.title}</div>
                          {item.subtitle && (
                            <Text type="secondary" style={{ fontSize: 11 }}>
                              {item.subtitle}
                            </Text>
                          )}
                        </div>
                      </Space>
                    </List.Item>
                  );
                }}
              />
            </div>
          );
        })}
      </div>
    </Modal>
  );
}
