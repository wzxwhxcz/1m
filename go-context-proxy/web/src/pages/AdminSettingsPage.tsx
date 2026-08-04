import React, { useState } from 'react';
import { Card, Form, Input, Button, Space, Typography, message, Divider } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import axios from 'axios';

const { Title, Paragraph, Text } = Typography;

interface SystemConfig {
  oauth_client_id: string;
  oauth_client_secret: string;
  oauth_redirect_uri: string;
  default_plan_free: string;
  default_plan_trust_0: string;
  default_plan_trust_1: string;
  default_plan_trust_2: string;
  default_plan_trust_3: string;
  default_plan_trust_4: string;
}

const AdminSettingsPage: React.FC = () => {
  const [oauthForm] = Form.useForm();
  const [planForm] = Form.useForm();
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const response = await axios.get('/api/admin/config');
      const config = response.data.data;
      
      oauthForm.setFieldsValue({
        oauth_client_id: config.oauth_client_id,
        oauth_client_secret: config.oauth_client_secret,
        oauth_redirect_uri: config.oauth_redirect_uri,
      });

      planForm.setFieldsValue({
        default_plan_free: config.default_plan_free,
        default_plan_trust_0: config.default_plan_trust_0,
        default_plan_trust_1: config.default_plan_trust_1,
        default_plan_trust_2: config.default_plan_trust_2,
        default_plan_trust_3: config.default_plan_trust_3,
        default_plan_trust_4: config.default_plan_trust_4,
      });
    } catch (error) {
      message.error('加载配置失败');
    }
  };

  const handleSaveOAuth = async (values: any) => {
    setLoading(true);
    try {
      await Promise.all([
        axios.put('/api/admin/config', { key: 'oauth_client_id', value: values.oauth_client_id }),
        axios.put('/api/admin/config', { key: 'oauth_client_secret', value: values.oauth_client_secret }),
        axios.put('/api/admin/config', { key: 'oauth_redirect_uri', value: values.oauth_redirect_uri }),
      ]);
      message.success('OAuth 配置已保存');
    } catch (error) {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSavePlan = async (values: any) => {
    setLoading(true);
    try {
      await Promise.all([
        axios.put('/api/admin/config', { key: 'default_plan_free', value: values.default_plan_free }),
        axios.put('/api/admin/config', { key: 'default_plan_trust_0', value: values.default_plan_trust_0 }),
        axios.put('/api/admin/config', { key: 'default_plan_trust_1', value: values.default_plan_trust_1 }),
        axios.put('/api/admin/config', { key: 'default_plan_trust_2', value: values.default_plan_trust_2 }),
        axios.put('/api/admin/config', { key: 'default_plan_trust_3', value: values.default_plan_trust_3 }),
        axios.put('/api/admin/config', { key: 'default_plan_trust_4', value: values.default_plan_trust_4 }),
      ]);
      message.success('套餐规则已保存');
    } catch (error) {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>系统配置</Title>

      {/* OAuth 配置 */}
      <Card
        title="Linux Do OAuth 配置"
        style={{ marginBottom: 24, background: '#1E222E', borderColor: '#2a2f3d' }}
        headStyle={{ color: '#fff', borderBottomColor: '#2a2f3d' }}
      >
        <Form
          form={oauthForm}
          layout="vertical"
          onFinish={handleSaveOAuth}
        >
          <Form.Item
            label={<span style={{ color: '#e5e7eb' }}>Client ID</span>}
            name="oauth_client_id"
            rules={[{ required: true, message: '请输入 Client ID' }]}
          >
            <Input placeholder="your-client-id" size="large" />
          </Form.Item>

          <Form.Item
            label={<span style={{ color: '#e5e7eb' }}>Client Secret</span>}
            name="oauth_client_secret"
            rules={[{ required: true, message: '请输入 Client Secret' }]}
          >
            <Input.Password placeholder="your-client-secret" size="large" />
          </Form.Item>

          <Form.Item
            label={<span style={{ color: '#e5e7eb' }}>Redirect URI</span>}
            name="oauth_redirect_uri"
            rules={[{ required: true, message: '请输入回调地址' }]}
          >
            <Input placeholder="http://localhost:5173/user/callback" size="large" />
          </Form.Item>

          <Paragraph style={{ color: '#9ca3af', fontSize: 13 }}>
            💡 在 Linux Do 开发者设置中创建 OAuth 应用，填写上述信息。
          </Paragraph>

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SaveOutlined />}
              loading={loading}
              size="large"
              style={{ background: '#5B8CFF', borderColor: '#5B8CFF' }}
            >
              保存 OAuth 配置
            </Button>
          </Form.Item>
        </Form>
      </Card>

      {/* 默认套餐规则 */}
      <Card
        title="默认套餐分配规则"
        style={{ background: '#1E222E', borderColor: '#2a2f3d' }}
        headStyle={{ color: '#fff', borderBottomColor: '#2a2f3d' }}
      >
        <Paragraph style={{ color: '#9ca3af', marginBottom: 24 }}>
          根据用户的 Linux Do Trust Level 自动分配套餐和每日配额。格式: <Text code style={{ color: '#5B8CFF' }}>plan:quota_daily</Text>
        </Paragraph>

        <Form
          form={planForm}
          layout="vertical"
          onFinish={handleSavePlan}
        >
          <Form.Item
            label={<span style={{ color: '#e5e7eb' }}>默认套餐（无 Trust Level）</span>}
            name="default_plan_free"
            rules={[{ required: true, message: '请输入默认套餐' }]}
          >
            <Input placeholder="free:100" size="large" />
          </Form.Item>

          <Divider style={{ borderColor: '#2a2f3d', margin: '16px 0' }} />

          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Form.Item
              label={<span style={{ color: '#e5e7eb' }}>Trust Level 0</span>}
              name="default_plan_trust_0"
              rules={[{ required: true }]}
            >
              <Input placeholder="free:100" size="large" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: '#e5e7eb' }}>Trust Level 1</span>}
              name="default_plan_trust_1"
              rules={[{ required: true }]}
            >
              <Input placeholder="pro:1000" size="large" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: '#e5e7eb' }}>Trust Level 2</span>}
              name="default_plan_trust_2"
              rules={[{ required: true }]}
            >
              <Input placeholder="pro:2000" size="large" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: '#e5e7eb' }}>Trust Level 3</span>}
              name="default_plan_trust_3"
              rules={[{ required: true }]}
            >
              <Input placeholder="enterprise:5000" size="large" />
            </Form.Item>

            <Form.Item
              label={<span style={{ color: '#e5e7eb' }}>Trust Level 4</span>}
              name="default_plan_trust_4"
              rules={[{ required: true }]}
            >
              <Input placeholder="enterprise:10000" size="large" />
            </Form.Item>
          </Space>

          <Form.Item style={{ marginTop: 24 }}>
            <Button
              type="primary"
              htmlType="submit"
              icon={<SaveOutlined />}
              loading={loading}
              size="large"
              style={{ background: '#5B8CFF', borderColor: '#5B8CFF' }}
            >
              保存套餐规则
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default AdminSettingsPage;
