/**
 * AppShell — main layout wrapper untuk authenticated routes.
 *
 * Layout:
 * - Sidebar (Sider) — collapsible di desktop, Drawer di mobile
 * - Topbar — breadcrumb / app title + Cmd+K search trigger + user menu
 * - Main content area — auto-scroll
 *
 * Responsive:
 * - Desktop: Sider always visible, 240px wide, collapse → 64px
 * - Tablet: Sider collapsed by default (64px icon-only), expandable on hover
 * - Mobile: Sider hidden, Drawer slide-in dari kiri
 */

import {
  ApartmentOutlined,
  BarChartOutlined,
  CalendarOutlined,
  CheckSquareOutlined,
  CrownOutlined,
  DashboardOutlined,
  DollarOutlined,
  FileTextOutlined,
  FundOutlined,
  LockOutlined,
  LogoutOutlined,
  MenuOutlined,
  PoweroffOutlined,
  ProjectOutlined,
  SafetyOutlined,
  SearchOutlined,
  SettingOutlined,
  SolutionOutlined,
  TeamOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Avatar, Badge, Button, Drawer, Dropdown, Layout, Menu, Space, Tooltip, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { logout } from '@/api/auth';
import { getExpiringPlacements } from '@/api/outsource';
import { getMyTasksDueSummary } from '@/api/projects';
import {
  executiveColor,
  getTopRole,
  isExecutiveRole,
  isWakilDirektur,
} from '@/lib/persona';
import { useResponsive } from '@/lib/useResponsive';
import { broadcastLogout } from '@/lib/sessionBroadcast';
import { useAuthStore } from '@/store/auth';

const { Sider, Header, Content } = Layout;
const { Text } = Typography;

const SIDER_WIDTH = 240;
const SIDER_COLLAPSED_WIDTH = 64;

interface AppShellProps {
  children: React.ReactNode;
}

function getMenuItems(
  isExecutive: boolean,
  dueTaskBadge: number = 0,
  expiringPlacementBadge: number = 0,
  h7PlacementCount: number = 0,
) {
  // Project menu label with badge for overdue + due-soon task count (TSK-075)
  const projectLabel = dueTaskBadge > 0 ? (
    <Tooltip title={`${dueTaskBadge} task overdue / due soon`}>
      <span>
        Projects{' '}
        <Badge
          count={dueTaskBadge}
          size="small"
          style={{ background: 'var(--ide-orange, #FF9500)', marginLeft: 6 }}
        />
      </span>
    </Tooltip>
  ) : 'Projects';

  // Outsource menu label with badge for expiring placement (TSK-106)
  const outsourceLabel = expiringPlacementBadge > 0 ? (
    <Tooltip title={`${expiringPlacementBadge} placement expiring in 30d (${h7PlacementCount} urgent ≤7d)`}>
      <span>
        Outsource{' '}
        <Badge
          count={expiringPlacementBadge}
          size="small"
          style={{
            background: h7PlacementCount > 0 ? 'var(--ide-red, #FF3B30)' : 'var(--ide-orange, #FF9500)',
            marginLeft: 6,
          }}
        />
      </span>
    </Tooltip>
  ) : 'Outsource';

  const items: any[] = [
    { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
    { key: '/employees', icon: <TeamOutlined />, label: 'Karyawan' },
    { key: '/org-chart', icon: <ApartmentOutlined />, label: 'Org Chart' },
    { key: '/hiring', icon: <SolutionOutlined />, label: 'Hiring' },
    { key: '/onboarding', icon: <CheckSquareOutlined />, label: 'Onboarding' },
    { key: '/contracts', icon: <FileTextOutlined />, label: 'Contracts' },
    { key: '/leave', icon: <CalendarOutlined />, label: 'Leave' },
    { key: '/performance', icon: <BarChartOutlined />, label: 'Performance' },
    { key: '/projects', icon: <ProjectOutlined />, label: projectLabel },
    { key: '/finance', icon: <DollarOutlined />, label: 'Finance' },
    { key: '/payroll', icon: <DollarOutlined />, label: 'Payroll' },
    { key: '/sales', icon: <FundOutlined />, label: 'Sales' },
    { key: '/outsource', icon: <TeamOutlined />, label: outsourceLabel },
    { key: '/separations', icon: <PoweroffOutlined />, label: 'Separation' },
    { key: '/settings', icon: <SettingOutlined />, label: 'Pengaturan' },
  ];

  if (isExecutive) {
    items.push({
      key: '/admin/permissions',
      icon: <SafetyOutlined />,
      label: 'Permission Matrix',
    });
  }

  return items;
}

export function AppShell({ children }: AppShellProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isMobile, isTablet } = useResponsive();
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  // Desktop collapse state (saved in component state, not persisted)
  const [collapsed, setCollapsed] = useState(isTablet);
  // Mobile drawer state
  const [drawerOpen, setDrawerOpen] = useState(false);

  const isExecutive = isExecutiveRole(user);
  const isWakil = isWakilDirektur(user);
  const topRole = getTopRole(user);
  const avatarBg = executiveColor(user);

  // TSK-075: poll due task count every 60s
  const dueQuery = useQuery({
    queryKey: ['my-tasks-due-summary'],
    queryFn: getMyTasksDueSummary,
    refetchInterval: 60_000,
    enabled: !!user,
  });
  const dueBadge =
    (dueQuery.data?.overdue_count ?? 0) +
    (dueQuery.data?.due_h1_count ?? 0) +
    (dueQuery.data?.due_h3_count ?? 0);

  // TSK-106: poll expiring placement count every 5 min
  const expiringQ = useQuery({
    queryKey: ['expiring-placements'],
    queryFn: () => getExpiringPlacements(30),
    refetchInterval: 5 * 60_000,
    enabled: !!user,
  });
  const expiringBadge = expiringQ.data?.h30_count ?? 0;
  const h7Count = expiringQ.data?.h7_count ?? 0;

  const menuItems = getMenuItems(isExecutive, dueBadge, expiringBadge, h7Count);

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
    if (isMobile) setDrawerOpen(false);
  };

  const handleLogout = async () => {
    const refreshToken = useAuthStore.getState().refreshToken;
    if (refreshToken) {
      try {
        await logout(refreshToken);
      } catch {
        // Best-effort
      }
    }
    clearAuth();
    broadcastLogout('user');
    navigate('/login');
  };

  // Sidebar menu shared between Sider (desktop/tablet) and Drawer (mobile)
  const sidebarContent = (
    <>
      <div
        style={{
          height: 56,
          padding: '0 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            background: 'var(--blue)',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: 14,
          }}
          aria-hidden="true"
        >
          ID
        </div>
        {!collapsed && (
          <Text strong style={{ fontSize: 16 }}>
            IDEA Portal
          </Text>
        )}
      </div>

      <Menu
        mode="inline"
        selectedKeys={[location.pathname]}
        items={menuItems}
        onClick={handleMenuClick}
        style={{ borderRight: 0, paddingTop: 8 }}
      />
    </>
  );

  const userMenuItems = [
        {
          key: 'profile',
          icon: <UserOutlined />,
          label: `${user?.nik ?? '—'}`,
          disabled: true,
        },
        {
          key: 'role',
          icon: isExecutive ? <CrownOutlined style={{ color: avatarBg }} /> : <UserOutlined />,
          label: topRole
            ? `${topRole.name}${isWakil ? ' ⚖️' : ''}`
            : '—',
          disabled: true,
        },
        { type: 'divider' as const },
        {
          key: 'settings',
          icon: <SettingOutlined />,
          label: 'Pengaturan',
          onClick: () => navigate('/settings'),
        },
        {
          key: 'change-password',
          icon: <LockOutlined />,
          label: 'Ubah Password',
          onClick: () => navigate('/settings'),
        },
        { type: 'divider' as const },
        {
          key: 'logout',
          icon: <LogoutOutlined />,
          label: 'Logout',
          danger: true,
          onClick: handleLogout,
        },
      ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {!isMobile && (
        <Sider
          width={SIDER_WIDTH}
          collapsedWidth={SIDER_COLLAPSED_WIDTH}
          collapsible
          collapsed={collapsed}
          onCollapse={setCollapsed}
          trigger={null}
          theme="light"
          style={{
            borderRight: '1px solid var(--border)',
            background: 'var(--surface)',
          }}
        >
          {sidebarContent}
        </Sider>
      )}

      {isMobile && (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={SIDER_WIDTH}
          styles={{ body: { padding: 0 } }}
          closeIcon={null}
        >
          {sidebarContent}
        </Drawer>
      )}

      <Layout>
        <Header
          style={{
            background: 'var(--surface)',
            borderBottom: '1px solid var(--border)',
            padding: '0 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: 56,
            lineHeight: '56px',
          }}
        >
          <Space>
            <Button
              type="text"
              icon={<MenuOutlined />}
              onClick={() => (isMobile ? setDrawerOpen(true) : setCollapsed(!collapsed))}
              aria-label="Toggle menu"
            />
            {!isMobile && (
              <Text type="secondary" style={{ fontSize: 13 }}>
                Sprint 1 — M1.1 Auth & RBAC
              </Text>
            )}
          </Space>

          <Space size="small">
            <Button
              type="text"
              icon={<SearchOutlined />}
              onClick={() => window.dispatchEvent(new CustomEvent('open-global-search'))}
              aria-label="Open global search (Cmd+K)"
              title="Search (⌘K)"
            />

            <Dropdown menu={{ items: userMenuItems }} trigger={['click']} placement="bottomRight">
              <Space style={{ cursor: 'pointer', padding: '0 8px' }} title={topRole?.name ?? ''}>
                <Avatar
                  size={32}
                  style={{
                    background: avatarBg,
                    border: isWakil ? '2px solid var(--ide-purple, #AF52DE)' : 'none',
                  }}
                  icon={isExecutive ? <CrownOutlined /> : <UserOutlined />}
                />
                {!isMobile && (
                  <Text strong style={{ fontSize: 13 }}>
                    {user?.nik ?? '—'}
                    {isWakil && (
                      <span style={{
                        marginLeft: 6,
                        fontSize: 10,
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: 4,
                        background: 'var(--ide-teal-bg, rgba(50,173,230,0.12))',
                        color: 'var(--ide-teal, #32ADE6)',
                      }}>
                        WAKIL
                      </span>
                    )}
                  </Text>
                )}
              </Space>
            </Dropdown>
          </Space>
        </Header>

        <Content
          style={{
            overflow: 'auto',
            background: 'var(--bg)',
            minHeight: 'calc(100vh - 56px)',
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
}
