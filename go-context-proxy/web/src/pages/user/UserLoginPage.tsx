import React from 'react';
import { Button, Card, Typography } from 'antd';
import { GithubOutlined } from '@ant-design/icons';

const { Title, Paragraph } = Typography;

const UserLoginPage: React.FC = () => {
  const handleLogin = () => {
    // 模拟跳转到 Linux Do OAuth（开发环境直接用 mock code）
    const isDev = import.meta.env.DEV;
    
    if (isDev) {
      // 开发模式：直接模拟回调
      window.location.href = '/user/callback?code=test_code_new_user';
    } else {
      // 生产模式：跳转真实 OAuth
      const clientId = 'your-client-id'; // 从后端配置获取
      const redirectUri = encodeURIComponent(window.location.origin + '/user/callback');
      window.location.href = `https://connect.linux.do/oauth2/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&response_type=code&scope=read`;
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
    }}>
      <Card
        style={{
          width: 480,
          borderRadius: 12,
          boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
        }}
      >
        <div style={{ textAlign: 'center', padding: '20px 0' }}>
          <Title level={2} style={{ marginBottom: 8, color: '#1f2937' }}>
            Context Proxy
          </Title>
          <Title level={4} style={{ marginTop: 0, marginBottom: 24, color: '#6b7280', fontWeight: 400 }}>
            1M→400K 智能上下文压缩
          </Title>
          
          <Paragraph style={{ fontSize: 15, color: '#6b7280', marginBottom: 32 }}>
            通过 Linux Do 登录，即刻开始使用
            <br />
            自动分配 API 密钥，无需手动注册
          </Paragraph>

          <Button
            type="primary"
            size="large"
            icon={<GithubOutlined />}
            onClick={handleLogin}
            style={{
              width: '100%',
              height: 48,
              fontSize: 16,
              background: '#5B8CFF',
              borderColor: '#5B8CFF',
              borderRadius: 8,
            }}
          >
            使用 Linux Do 登录
          </Button>

          <div style={{ marginTop: 32, padding: '16px 0', borderTop: '1px solid #e5e7eb' }}>
            <Paragraph style={{ fontSize: 13, color: '#9ca3af', margin: 0 }}>
              登录即表示您同意我们的服务条款和隐私政策
            </Paragraph>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default UserLoginPage;
