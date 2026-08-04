import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Spin, message } from 'antd';
import { userService } from '../../services/userApi';

const UserCallbackPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code');
      
      if (!code) {
        message.error('授权失败：缺少授权码');
        setTimeout(() => navigate('/user/login'), 2000);
        return;
      }

      try {
        const result = await userService.oauthCallback(code);
        
        // 保存 token 和用户信息
        localStorage.setItem('user_token', result.token);
        localStorage.setItem('user_info', JSON.stringify(result.user));
        
        message.success(`欢迎回来，${result.user.username}！`);
        
        // 跳转到用户仪表盘
        setTimeout(() => navigate('/user/dashboard'), 1000);
      } catch (error: any) {
        message.error(error.message || '登录失败，请重试');
        setTimeout(() => navigate('/user/login'), 2000);
      } finally {
        setLoading(false);
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    }}>
      <Spin size="large" />
      <div style={{ marginTop: 24, color: '#fff', fontSize: 16 }}>
        {loading ? '正在登录中...' : '登录成功，即将跳转...'}
      </div>
    </div>
  );
};

export default UserCallbackPage;
