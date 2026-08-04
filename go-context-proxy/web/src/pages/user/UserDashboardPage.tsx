import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Typography, message, Space, Avatar, Button, Divider } from 'antd';
import { Line } from '@ant-design/charts';
import { CopyOutlined, ThunderboltOutlined, ClockCircleOutlined, ApiOutlined, RocketOutlined } from '@ant-design/icons';
import { userService, User, UserStats, QuotaTrend } from '../../services/userApi';

const { Title, Paragraph, Text } = Typography;

const UserDashboardPage: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [trendData, setTrendData] = useState<QuotaTrend[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [userInfo, statsData, trend] = await Promise.all([
        userService.getProfile(),
        userService.getStats(),
        userService.getQuotaTrend(7),
      ]);
      
      setUser(userInfo);
      setStats(statsData);
      setTrendData(trend);
    } catch (error: any) {
      message.error(error.message || '加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  const copyServiceKey = () => {
    if (user?.service_key) {
      navigator.clipboard.writeText(user.service_key);
      message.success('API 密钥已复制到剪贴板');
    }
  };

  const chartConfig = {
    data: trendData,
    xField: 'date',
    yField: 'used',
    smooth: true,
    color: '#5B8CFF',
    point: {
      size: 4,
      shape: 'circle',
      style: {
        fill: '#5B8CFF',
        stroke: '#fff',
        lineWidth: 2,
      },
    },
    line: {
      style: {
        lineWidth: 3,
      },
    },
    yAxis: {
      label: {
        formatter: (v: string) => `${v}`,
      },
    },
    xAxis: {
      label: {
        formatter: (v: string) => {
          const date = new Date(v);
          return `${date.getMonth() + 1}/${date.getDate()}`;
        },
      },
    },
    tooltip: {
      formatter: (datum: any) => {
        return {
          name: '已用配额',
          value: `${datum.used} / ${datum.quota}`,
        };
      },
    },
  };

  if (loading) {
    return <div style={{ padding: 24 }}>加载中...</div>;
  }

  return (
    <div style={{ padding: 24, background: '#f5f5f5', minHeight: '100vh' }}>
      {/* 用户信息卡片 */}
      <Card style={{ marginBottom: 24, borderRadius: 8 }}>
        <Space size="large" align="start" style={{ width: '100%' }}>
          <Avatar size={80} src={user?.avatar_url} style={{ background: '#5B8CFF' }}>
            {user?.username?.[0]?.toUpperCase()}
          </Avatar>
          
          <div style={{ flex: 1 }}>
            <Title level={3} style={{ margin: 0 }}>
              {user?.username}
            </Title>
            <Text type="secondary">{user?.email}</Text>
            
            <div style={{ marginTop: 16 }}>
              <Space>
                <Text strong>API 密钥:</Text>
                <Text code style={{ fontSize: 14 }}>
                  {user?.service_key}
                </Text>
                <Button
                  type="link"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={copyServiceKey}
                  style={{ color: '#5B8CFF' }}
                >
                  复制
                </Button>
              </Space>
            </div>
            
            <div style={{ marginTop: 8 }}>
              <Space>
                <Text type="secondary">套餐:</Text>
                <Text strong style={{ color: '#5B8CFF', textTransform: 'capitalize' }}>
                  {user?.plan}
                </Text>
                <Divider type="vertical" />
                <Text type="secondary">Trust Level:</Text>
                <Text strong>{user?.trust_level}</Text>
              </Space>
            </div>
          </div>
        </Space>
      </Card>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} style={{ borderRadius: 8 }}>
            <Statistic
              title="今日已用配额"
              value={stats?.quota_used_today || 0}
              suffix={`/ ${stats?.quota_daily || 0}`}
              prefix={<ThunderboltOutlined />}
              styles={{ value: { color: '#5B8CFF' } }}
            />
          </Card>
        </Col>
        
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} style={{ borderRadius: 8 }}>
            <Statistic
              title="配额使用率"
              value={stats ? ((stats.quota_used_today / stats.quota_daily) * 100).toFixed(1) : 0}
              suffix="%"
              prefix={<ClockCircleOutlined />}
              styles={{ value: { color: stats && (stats.quota_used_today / stats.quota_daily) > 0.8 ? '#F87171' : '#22D3EE' } }}
            />
          </Card>
        </Col>
        
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} style={{ borderRadius: 8 }}>
            <Statistic
              title="本月总请求数"
              value={stats?.monthly_requests || 0}
              prefix={<ApiOutlined />}
              styles={{ value: { color: '#5B8CFF' } }}
            />
          </Card>
        </Col>
        
        <Col xs={24} sm={12} lg={6}>
          <Card bordered={false} style={{ borderRadius: 8 }}>
            <Statistic
              title="召回触发次数"
              value={stats?.recall_triggered || 0}
              prefix={<RocketOutlined />}
              styles={{ value: { color: '#22D3EE' } }}
            />
          </Card>
        </Col>
      </Row>

      {/* 配额使用趋势 */}
      <Card title="7日配额使用趋势" style={{ marginBottom: 24, borderRadius: 8 }}>
        <Line {...chartConfig} height={300} />
      </Card>

      {/* API 使用示例 */}
      <Card title="API 使用示例" style={{ borderRadius: 8 }}>
        <Paragraph>
          <Text strong>请求地址:</Text>
        </Paragraph>
        <Paragraph>
          <Text code style={{ fontSize: 13 }}>
            POST https://your-proxy.com/{user?.service_key}/https://api.openai.com/v1/chat/completions
          </Text>
          <Button
            type="link"
            size="small"
            icon={<CopyOutlined />}
            onClick={() => {
              navigator.clipboard.writeText(
                `https://your-proxy.com/${user?.service_key}/https://api.openai.com/v1/chat/completions`
              );
              message.success('API 地址已复制');
            }}
            style={{ color: '#5B8CFF' }}
          >
            复制
          </Button>
        </Paragraph>

        <Paragraph style={{ marginTop: 16 }}>
          <Text strong>请求示例:</Text>
        </Paragraph>
        <pre style={{
          background: '#f5f5f5',
          padding: 16,
          borderRadius: 6,
          overflow: 'auto',
          fontSize: 13,
        }}>
{`curl https://your-proxy.com/${user?.service_key}/https://api.openai.com/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_UPSTREAM_API_KEY" \\
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'`}
        </pre>

        <Paragraph type="secondary" style={{ marginTop: 16, fontSize: 13 }}>
          💡 提示：将 <Text code>YOUR_UPSTREAM_API_KEY</Text> 替换为您的实际上游 API 密钥（OpenAI、Anthropic 等）
        </Paragraph>
      </Card>
    </div>
  );
};

export default UserDashboardPage;
