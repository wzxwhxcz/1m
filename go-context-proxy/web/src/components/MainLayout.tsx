import { useState } from 'react';
import { Layout, Menu } from 'antd';
import {
  DashboardOutlined,
  TeamOutlined,
  BarChartOutlined,
  SettingOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/auth';

const { Header, Sider, Content } = Layout;

export default function MainLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAuthStore((state) => state.logout);

  const menuItems = [
    {
      key: '/admin/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
      onClick: () => navigate('/admin/dashboard'),
    },
    {
      key: '/admin/users',
      icon: <TeamOutlined />,
      label: '用户管理',
      onClick: () => navigate('/admin/users'),
    },
    {
      key: '/admin/statistics',
      icon: <BarChartOutlined />,
      label: '统计分析',
      onClick: () => navigate('/admin/statistics'),
    },
    {
      key: '/admin/settings',
      icon: <SettingOutlined />,
      label: '系统配置',
      onClick: () => navigate('/admin/settings'),
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: logout,
      style: { marginTop: 'auto' },
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        collapsible 
        collapsed={collapsed} 
        onCollapse={setCollapsed}
        style={{
          background: '#171A23',
          borderRight: '1px solid #1E222E',
        }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 18,
          fontWeight: 600,
          color: '#F3F4F6',
          borderBottom: '1px solid #1E222E',
        }}>
          {collapsed ? 'CP' : 'Context Proxy Admin'}
        </div>
        <Menu
          theme="dark"
          selectedKeys={[location.pathname]}
          mode="inline"
          items={menuItems}
          style={{
            background: '#171A23',
            border: 'none',
          }}
        />
      </Sider>
      <Layout>
        <Header style={{
          padding: '0 24px',
          background: '#171A23',
          borderBottom: '1px solid #1E222E',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <div style={{ color: '#F3F4F6', fontSize: 16 }}>
            1M → 400K 上下文压缩代理系统
          </div>
        </Header>
        <Content style={{
          margin: 24,
          padding: 24,
          minHeight: 280,
          background: '#0F1117',
        }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
