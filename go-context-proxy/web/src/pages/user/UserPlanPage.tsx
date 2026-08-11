import React from 'react';
import { Card, Row, Col, Typography, Tag, Table } from 'antd';
import { CheckOutlined, TrophyOutlined } from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;

const UserPlanPage: React.FC = () => {
  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}');
  const { plan = 'free', trust_level = 0, quota_daily = 100 } = userInfo;

  const planFeatures = {
    free: {
      name: 'Free',
      color: '#6B7280',
      quota: 100,
      features: [
        '每日 100 次请求',
        '自动上下文压缩（1M→400K）',
        '基础技术支持',
        '7 天日志保留',
      ],
    },
    pro: {
      name: 'Pro',
      color: '#5B8CFF',
      quota: '1,000 - 2,000',
      features: [
        '每日 1,000-2,000 次请求',
        '自动上下文压缩（1M→400K）',
        '优先技术支持',
        '30 天日志保留',
        '高级监控面板',
      ],
    },
    enterprise: {
      name: 'Enterprise',
      color: '#F59E0B',
      quota: '5,000 - 10,000',
      features: [
        '每日 5,000-10,000 次请求',
        '自动上下文压缩（1M→400K）',
        '7x24 技术支持',
        '90 天日志保留',
        '高级监控面板',
        '自定义限流规则',
        'SLA 保障',
      ],
    },
  };

  const currentPlan = planFeatures[plan as keyof typeof planFeatures] || planFeatures.free;

  const trustLevelInfo = [
    { level: 0, plan: 'Free', quota: 100, description: '新注册用户' },
    { level: 1, plan: 'Pro', quota: 1000, description: '活跃用户' },
    { level: 2, plan: 'Pro', quota: 2000, description: '贡献者' },
    { level: 3, plan: 'Enterprise', quota: 5000, description: '资深成员' },
    { level: 4, plan: 'Enterprise', quota: 10000, description: '核心成员' },
  ];

  const columns = [
    {
      title: 'Trust Level',
      dataIndex: 'level',
      key: 'level',
      width: 120,
      render: (level: number) => (
        <Tag color={level === trust_level ? '#5B8CFF' : 'default'}>
          {level === trust_level && <TrophyOutlined style={{ marginRight: 4 }} />}
          Level {level}
        </Tag>
      ),
    },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
      width: 120,
      render: (plan: string) => (
        <Text strong style={{ color: planFeatures[plan.toLowerCase() as keyof typeof planFeatures]?.color }}>
          {plan}
        </Text>
      ),
    },
    {
      title: '每日配额',
      dataIndex: 'quota',
      key: 'quota',
      width: 120,
      render: (quota: number) => `${quota.toLocaleString()} 次`,
    },
    {
      title: '说明',
      dataIndex: 'description',
      key: 'description',
    },
  ];

  return (
    <div style={{ padding: 24, background: '#f5f5f5', minHeight: '100vh' }}>
      <Title level={2}>套餐信息</Title>

      {/* 当前套餐 */}
      <Card
        style={{
          marginBottom: 24,
          borderRadius: 8,
          border: `2px solid ${currentPlan.color}`,
        }}
      >
        <Row gutter={24} align="middle">
          <Col flex="auto">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Tag color={currentPlan.color} style={{ fontSize: 14, padding: '4px 12px', width: 'fit-content' }}>
                当前套餐
              </Tag>
              <Title level={3} style={{ margin: 0, color: currentPlan.color }}>
                {currentPlan.name}
              </Title>
              <Text type="secondary">
                每日配额: <Text strong style={{ fontSize: 16 }}>{quota_daily.toLocaleString()}</Text> 次请求
              </Text>
            </div>
          </Col>
          <Col>
            <div style={{ textAlign: 'center' }}>
              <TrophyOutlined style={{ fontSize: 48, color: currentPlan.color }} />
              <div style={{ marginTop: 8 }}>
                <Text type="secondary">Trust Level</Text>
                <Title level={4} style={{ margin: 0 }}>{trust_level}</Title>
              </div>
            </div>
          </Col>
        </Row>

        <div style={{ marginTop: 24 }}>
          <Text strong>套餐特性:</Text>
          <ul style={{ marginTop: 8, paddingLeft: 20 }}>
            {currentPlan.features.map((feature, index) => (
              <li key={index} style={{ marginBottom: 8 }}>
                <CheckOutlined style={{ color: currentPlan.color, marginRight: 8 }} />
                {feature}
              </li>
            ))}
          </ul>
        </div>
      </Card>

      {/* Trust Level 说明 */}
      <Card title="Trust Level 与套餐对应关系" style={{ marginBottom: 24, borderRadius: 8 }}>
        <Paragraph type="secondary">
          您的套餐由 Linux Do 社区的 Trust Level 自动决定。随着您在社区的活跃度提升，Trust Level 会自动升级，配额也会相应增加。
        </Paragraph>
        <Table
          columns={columns}
          dataSource={trustLevelInfo}
          rowKey="level"
          pagination={false}
          rowClassName={(record) => (record.level === trust_level ? 'current-level-row' : '')}
        />
        <style>{`
          .current-level-row {
            background-color: #f0f7ff !important;
          }
        `}</style>
      </Card>

      {/* 套餐对比 */}
      <Card title="所有套餐对比" style={{ borderRadius: 8 }}>
        <Row gutter={16}>
          {Object.entries(planFeatures).map(([key, planInfo]) => (
            <Col xs={24} md={8} key={key}>
              <Card
                style={{
                  borderRadius: 8,
                  border: plan === key ? `2px solid ${planInfo.color}` : '1px solid #e5e7eb',
                  height: '100%',
                }}
              >
                <div style={{ textAlign: 'center', marginBottom: 16 }}>
                  <Title level={4} style={{ color: planInfo.color, margin: 0 }}>
                    {planInfo.name}
                  </Title>
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    每日 {planInfo.quota} 次
                  </Text>
                </div>
                <ul style={{ paddingLeft: 20, minHeight: 180 }}>
                  {planInfo.features.map((feature, index) => (
                    <li key={index} style={{ marginBottom: 8, fontSize: 13 }}>
                      <CheckOutlined style={{ color: planInfo.color, marginRight: 8 }} />
                      {feature}
                    </li>
                  ))}
                </ul>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>
    </div>
  );
};

export default UserPlanPage;
