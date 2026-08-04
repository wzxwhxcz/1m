import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Typography, Space, DatePicker, Select, Button } from 'antd';
import { CheckCircleOutlined, CloseCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { userService, RequestLog } from '../../services/userApi';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

const UserLogsPage: React.FC = () => {
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadLogs();
  }, [page, pageSize]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const result = await userService.getLogs(page, pageSize);
      setLogs(result.logs);
      setTotal(result.total);
    } catch (error) {
      console.error('加载日志失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => dayjs(time).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '上游地址',
      dataIndex: 'upstream_url',
      key: 'upstream_url',
      ellipsis: true,
      render: (url: string) => {
        const domain = new URL(url).hostname;
        return <span title={url}>{domain}</span>;
      },
    },
    {
      title: '输入 Tokens',
      dataIndex: 'input_tokens',
      key: 'input_tokens',
      width: 130,
      align: 'right' as const,
      render: (tokens: number) => tokens.toLocaleString(),
    },
    {
      title: '输出 Tokens',
      dataIndex: 'output_tokens',
      key: 'output_tokens',
      width: 130,
      align: 'right' as const,
      render: (tokens: number) => tokens.toLocaleString(),
    },
    {
      title: '召回',
      dataIndex: 'recall_triggered',
      key: 'recall_triggered',
      width: 80,
      align: 'center' as const,
      render: (triggered: boolean) =>
        triggered ? (
          <Tag icon={<ThunderboltOutlined />} color="blue">
            已触发
          </Tag>
        ) : (
          <Tag color="default">未触发</Tag>
        ),
    },
    {
      title: '延迟',
      dataIndex: 'total_latency_ms',
      key: 'total_latency_ms',
      width: 100,
      align: 'right' as const,
      render: (latency: number, record: RequestLog) => (
        <Space direction="vertical" size={0}>
          <span>{latency}ms</span>
          {record.recall_triggered && (
            <span style={{ fontSize: 12, color: '#999' }}>
              (召回: {record.recall_latency_ms}ms)
            </span>
          )}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 90,
      align: 'center' as const,
      render: (status: string) =>
        status === 'success' ? (
          <Tag icon={<CheckCircleOutlined />} color="success">
            成功
          </Tag>
        ) : (
          <Tag icon={<CloseCircleOutlined />} color="error">
            失败
          </Tag>
        ),
    },
  ];

  return (
    <div style={{ padding: 24, background: '#f5f5f5', minHeight: '100vh' }}>
      <Title level={2}>请求日志</Title>

      <Card style={{ marginBottom: 24, borderRadius: 8 }}>
        <Space size="middle" wrap>
          <RangePicker
            placeholder={['开始日期', '结束日期']}
            style={{ width: 260 }}
          />
          <Select
            placeholder="召回状态"
            allowClear
            style={{ width: 120 }}
            options={[
              { value: 'all', label: '全部' },
              { value: 'triggered', label: '已触发' },
              { value: 'not_triggered', label: '未触发' },
            ]}
          />
          <Button type="primary" style={{ background: '#5B8CFF', borderColor: '#5B8CFF' }}>
            查询
          </Button>
          <Button>重置</Button>
        </Space>
      </Card>

      <Card style={{ borderRadius: 8 }}>
        <Table
          columns={columns}
          dataSource={logs}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条记录`,
            onChange: (newPage, newPageSize) => {
              setPage(newPage);
              setPageSize(newPageSize);
            },
          }}
        />
      </Card>
    </div>
  );
};

export default UserLogsPage;
