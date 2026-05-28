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
  CrownOutlined,
  DashboardOutlined,
  LockOutlined,
  LogoutOutlined,
  MenuOutlined,
  SafetyOutlined,
  SearchOutlined,
  SettingOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { Avatar, Button, Drawer, Dropdown, Layout, Menu, Space, Typography } from 'antd';
import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import { logout } from '@/api/auth';
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

function getMenuItems(isExecutive: boolean) {
  const items = [
    { key: '/', icon: <DashboardOutlined />, label: 'Dashboard' },
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

  const isExecutive = user?.roles.some(
    (r) => r.code === 'DIREKTUR_UTAMA' || r.code === 'WAKIL_DIREKTUR_UTAMA',
  ) ?? false;

  const menuItems = getMenuItems(isExecutive);

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

  const userMenu = (
    <Menu
      items={[
        {
          key: 'profile',
          icon: <UserOutlined />,
          label: `${user?.nik ?? '—'}`,
          disabled: true,
        },
        {
          key: 'role',
          icon: isExecutive ? <CrownOutlined /> : <UserOutlined />,
          label: user?.roles[0]?.name ?? '—',
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
      ]}
    />
  );

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

            <Dropdown overlay={userMenu} trigger={['click']} placement="bottomRight">
              <Space style={{ cursor: 'pointer', padding: '0 8px' }}>
                <Avatar
                  size={32}
                  style={{
                    background: isExecutive ? 'var(--purple)' : 'var(--blue)',
                  }}
                  icon={isExecutive ? <CrownOutlined /> : <UserOutlined />}
                />
                {!isMobile && (
                  <Text strong style={{ fontSize: 13 }}>
                    {user?.nik ?? '—'}
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
