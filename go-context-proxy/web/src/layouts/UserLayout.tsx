import React from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import { Layout, Menu, Avatar, Dropdown, Space, Typography } from 'antd';
import {
  DashboardOutlined,
  KeyOutlined,
  HistoryOutlined,
  CrownOutlined,
  LogoutOutlined,
  UserOutlined,
} from '@ant-design/icons';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const UserLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}');

  const menuItems = [
    {
      key: '/user/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/user/api-keys',
      icon: <KeyOutlined />,
      label: 'API 密钥',
    },
    {
      key: '/user/logs',
      icon: <HistoryOutlined />,
      label: '请求日志',
    },
    {
      key: '/user/plan',
      icon: <CrownOutlined />,
      label: '套餐信息',
    },
  ];

  const handleLogout = () => {
    localStorage.removeItem('user_token');
    localStorage.removeItem('user_info');
    navigate('/user/login');
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: handleLogout,
    },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 1px 4px rgba(0,0,0,0.08)',
          zIndex: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <div
            style={{
              fontSize: 20,
              fontWeight: 600,
              color: '#1f2937',
              cursor: 'pointer',
            }}
            onClick={() => navigate('/user/dashboard')}
          >
            Context Proxy
          </div>
          <div
            style={{
              marginLeft: 12,
              padding: '2px 8px',
              background: '#5B8CFF',
              color: '#fff',
              fontSize: 12,
              borderRadius: 4,
            }}
          >
            用户面板
          </div>
        </div>

        <Dropdown menu={{ items: userMenuItems }} placement="bottomRight">
          <Space style={{ cursor: 'pointer' }}>
            <Avatar size="small" src={userInfo.avatar_url} style={{ background: '#5B8CFF' }}>
              {userInfo.username?.[0]?.toUpperCase()}
            </Avatar>
            <Text>{userInfo.username}</Text>
          </Space>
        </Dropdown>
      </Header>

      <Layout>
        <Sider
          width={220}
          style={{
            background: '#fff',
            boxShadow: '1px 0 4px rgba(0,0,0,0.08)',
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ height: '100%', borderRight: 0, paddingTop: 16 }}
            onClick={({ key }) => navigate(key)}
          />
        </Sider>

        <Content style={{ background: '#f5f5f5' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
};

export default UserLayout;
