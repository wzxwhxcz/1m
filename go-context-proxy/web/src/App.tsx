import { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, theme, App as AntApp } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { useAuthStore } from './store/auth';
import MainLayout from './components/MainLayout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import UsersPage from './pages/UsersPage';
import StatisticsPage from './pages/StatisticsPage';
import AdminSettingsPage from './pages/AdminSettingsPage';

// 用户端页面
import UserLayout from './layouts/UserLayout';
import UserLoginPage from './pages/user/UserLoginPage';
import UserCallbackPage from './pages/user/UserCallbackPage';
import UserDashboardPage from './pages/user/UserDashboardPage';
import UserApiKeysPage from './pages/user/UserApiKeysPage';
import UserLogsPage from './pages/user/UserLogsPage';
import UserPlanPage from './pages/user/UserPlanPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  
  if (!isAuthenticated) {
    return <Navigate to="/admin/login" replace />;
  }
  
  return <>{children}</>;
}

function UserProtectedRoute({ children }: { children: React.ReactNode }) {
  const userToken = localStorage.getItem('user_token');
  
  if (!userToken) {
    return <Navigate to="/user/login" replace />;
  }
  
  return <>{children}</>;
}

function App() {
  const checkAuth = useAuthStore((state) => state.checkAuth);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#5B8CFF',
          colorBgContainer: '#0F1117',
          colorBgElevated: '#171A23',
          colorBgLayout: '#0F1117',
          colorBorder: '#1E222E',
          colorText: '#E5E7EB',
          colorTextSecondary: '#9CA3AF',
          colorTextTertiary: '#6B7280',
          borderRadius: 6,
          fontSize: 14,
        },
      }}
    >
      <AntApp>
        <BrowserRouter>
          <Routes>
            {/* 管理后台路由 */}
            <Route path="/admin/login" element={<LoginPage />} />
            
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <MainLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/admin/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="users" element={<UsersPage />} />
              <Route path="statistics" element={<StatisticsPage />} />
              <Route path="settings" element={<AdminSettingsPage />} />
            </Route>

            {/* 用户前台路由 */}
            <Route path="/user/login" element={<UserLoginPage />} />
            <Route path="/user/callback" element={<UserCallbackPage />} />
            
            <Route
              path="/user"
              element={
                <UserProtectedRoute>
                  <UserLayout />
                </UserProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/user/dashboard" replace />} />
              <Route path="dashboard" element={<UserDashboardPage />} />
              <Route path="api-keys" element={<UserApiKeysPage />} />
              <Route path="logs" element={<UserLogsPage />} />
              <Route path="plan" element={<UserPlanPage />} />
            </Route>

            {/* 默认重定向到用户登录 */}
            <Route path="/" element={<Navigate to="/user/login" replace />} />
            <Route path="*" element={<Navigate to="/user/login" replace />} />
          </Routes>
        </BrowserRouter>
      </AntApp>
    </ConfigProvider>
  );
}

export default App;
