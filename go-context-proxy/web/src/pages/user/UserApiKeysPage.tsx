import React, { useState } from 'react';
import { Card, Typography, Space, Button, message, Modal, Input } from 'antd';
import { CopyOutlined, EyeOutlined, EyeInvisibleOutlined, ReloadOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { userService } from '../../services/userApi';

const { Title, Paragraph, Text } = Typography;

const UserApiKeysPage: React.FC = () => {
  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}');
  const [serviceKey, setServiceKey] = useState(userInfo.service_key || '');
  const [showFullKey, setShowFullKey] = useState(false);
  const [resetting, setResetting] = useState(false);

  const copyKey = () => {
    navigator.clipboard.writeText(serviceKey);
    message.success('API 密钥已复制到剪贴板');
  };

  const handleResetKey = () => {
    Modal.confirm({
      title: '确认重置 API 密钥？',
      icon: <ExclamationCircleOutlined />,
      content: '重置后，旧密钥将立即失效，所有使用旧密钥的请求将被拒绝。此操作不可撤销。',
      okText: '确认重置',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setResetting(true);
        try {
          const result = await userService.resetApiKey();
          setServiceKey(result.new_service_key);
          
          // 更新 localStorage
          const updatedUser = { ...userInfo, service_key: result.new_service_key };
          localStorage.setItem('user_info', JSON.stringify(updatedUser));
          
          message.success('API 密钥已重置');
        } catch (error: any) {
          message.error(error.message || '重置失败');
        } finally {
          setResetting(false);
        }
      },
    });
  };

  const maskedKey = showFullKey
    ? serviceKey
    : `${serviceKey.substring(0, 12)}${'*'.repeat(20)}${serviceKey.substring(serviceKey.length - 8)}`;

  return (
    <div style={{ padding: 24, background: '#f5f5f5', minHeight: '100vh' }}>
      <Title level={2}>API 密钥管理</Title>
      
      {/* 当前密钥 */}
      <Card title="当前 API 密钥" style={{ marginBottom: 24, borderRadius: 8 }}>
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div>
            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>
              您的 API 密钥
            </Text>
            <Input
              value={maskedKey}
              readOnly
              size="large"
              style={{ fontFamily: 'monospace', fontSize: 14 }}
              addonAfter={
                <Space>
                  <Button
                    type="text"
                    size="small"
                    icon={showFullKey ? <EyeInvisibleOutlined /> : <EyeOutlined />}
                    onClick={() => setShowFullKey(!showFullKey)}
                  />
                  <Button
                    type="text"
                    size="small"
                    icon={<CopyOutlined />}
                    onClick={copyKey}
                  />
                </Space>
              }
            />
          </div>

          <Space>
            <Button
              type="primary"
              icon={<CopyOutlined />}
              onClick={copyKey}
              style={{ background: '#5B8CFF', borderColor: '#5B8CFF' }}
            >
              复制密钥
            </Button>
            <Button
              danger
              icon={<ReloadOutlined />}
              onClick={handleResetKey}
              loading={resetting}
            >
              重置密钥
            </Button>
          </Space>
        </Space>
      </Card>

      {/* 使用说明 */}
      <Card title="API 调用方式" style={{ marginBottom: 24, borderRadius: 8 }}>
        <Paragraph>
          <Text strong>方式一：URL 路径嵌入（推荐）</Text>
        </Paragraph>
        <Paragraph>
          将您的 service_key 和上游 API 地址拼接到请求路径中：
        </Paragraph>
        <pre style={{
          background: '#f5f5f5',
          padding: 16,
          borderRadius: 6,
          overflow: 'auto',
          fontSize: 13,
        }}>
{`POST ${window.location.origin}/${serviceKey}/https%3A%2F%2Fapi.openai.com/v1/chat/completions
Content-Type: application/json
Authorization: Bearer YOUR_UPSTREAM_API_KEY

{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ]
}`}
        </pre>

        <Paragraph style={{ marginTop: 24 }}>
          <Text strong>方式二：Header 传递</Text>
        </Paragraph>
        <pre style={{
          background: '#f5f5f5',
          padding: 16,
          borderRadius: 6,
          overflow: 'auto',
          fontSize: 13,
        }}>
{`POST ${window.location.origin}/v1/chat/completions
Content-Type: application/json
X-Service-Key: ${serviceKey}
Authorization: Bearer YOUR_UPSTREAM_API_KEY

{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ]
}`}
        </pre>
      </Card>

      {/* 支持的上游服务 */}
      <Card title="支持的上游 API 服务" style={{ borderRadius: 8 }}>
        <Paragraph>
          <Text>Context Proxy 支持透明代理以下 API 服务：</Text>
        </Paragraph>
        <ul>
          <li>
            <Text strong>OpenAI:</Text> <Text code>https://api.openai.com/v1/chat/completions</Text>
          </li>
          <li>
            <Text strong>Anthropic:</Text> <Text code>https://api.anthropic.com/v1/messages</Text>
          </li>
          <li>
            <Text strong>Google Gemini:</Text> <Text code>https://generativelanguage.googleapis.com/v1/models/...</Text>
          </li>
          <li>
            <Text strong>Azure OpenAI:</Text> <Text code>https://your-resource.openai.azure.com/openai/deployments/...</Text>
          </li>
          <li>
            <Text>以及其他兼容 OpenAI API 格式的服务</Text>
          </li>
        </ul>

        <Paragraph type="secondary" style={{ marginTop: 16 }}>
          💡 提示：当输入 tokens 超过 1M 时，系统会自动触发上下文压缩，将其优化至约 400K tokens。
        </Paragraph>
      </Card>
    </div>
  );
};

export default UserApiKeysPage;
