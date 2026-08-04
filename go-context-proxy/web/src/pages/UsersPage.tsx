import { useEffect, useState } from 'react';
import { 
  Table, 
  Button, 
  Space, 
  Tag, 
  Progress, 
  Badge, 
  Modal, 
  Form, 
  Input, 
  Select,
  InputNumber,
  Switch,
  App,
  Popconfirm,
  Typography,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { userApi } from '../api/client';
import type { User, CreateUserRequest, UpdateUserRequest } from '../types';

const { Text } = Typography;

export default function UsersPage() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    loadUsers();
  }, [page, pageSize]);

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await userApi.list(page, pageSize);
      setUsers(response.data.users);
      setTotal(response.data.total);
    } catch (error) {
      message.error('加载用户列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingUser(null);
    form.resetFields();
    form.setFieldsValue({ plan: 'free', quota_daily: 100 });
    setModalVisible(true);
  };

  const handleEdit = (user: User) => {
    setEditingUser(user);
    form.setFieldsValue(user);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await userApi.delete(id);
      message.success('删除成功');
      loadUsers();
    } catch (error) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      if (editingUser) {
        await userApi.update(editingUser.id, values as UpdateUserRequest);
        message.success('更新成功');
      } else {
        await userApi.create(values as CreateUserRequest);
        message.success('创建成功');
      }
      
      setModalVisible(false);
      loadUsers();
    } catch (error: any) {
      if (error.errorFields) return;
      message.error(editingUser ? '更新失败' : '创建失败');
    }
  };

  const planColors: Record<string, string> = {
    free: 'default',
    pro: 'blue',
    enterprise: 'gold',
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'Service Key',
      dataIndex: 'service_key',
      key: 'service_key',
      render: (key: string) => (
        <Text copyable style={{ color: '#5B8CFF', fontFamily: 'monospace' }}>
          {key.substring(0, 16)}...
        </Text>
      ),
    },
    {
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
    },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
      render: (plan: string) => (
        <Tag color={planColors[plan]}>{plan.toUpperCase()}</Tag>
      ),
    },
    {
      title: '配额使用',
      key: 'quota',
      render: (_: any, record: User) => (
        <Progress
          percent={(record.quota_used_today / record.quota_daily) * 100}
          format={() => `${record.quota_used_today}/${record.quota_daily}`}
          strokeColor="#5B8CFF"
        />
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Badge 
          status={active ? 'success' : 'error'} 
          text={active ? '正常' : '禁用'}
        />
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: User) => (
        <Space size="small">
          <Button 
            size="small" 
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除该用户吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button 
              size="small" 
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        marginBottom: 24,
      }}>
        <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0, color: '#F3F4F6' }}>
          用户管理
        </h1>
        <Button 
          type="primary" 
          icon={<PlusOutlined />}
          onClick={handleCreate}
        >
          创建用户
        </Button>
      </div>

      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize: pageSize,
          total: total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => {
            setPage(page);
            setPageSize(pageSize);
          },
        }}
        style={{
          background: '#0F1117',
          borderRadius: 8,
        }}
      />

      <Modal
        title={editingUser ? '编辑用户' : '创建用户'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        okText="确定"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>

          <Form.Item
            name="plan"
            label="套餐"
            rules={[{ required: true, message: '请选择套餐' }]}
          >
            <Select>
              <Select.Option value="free">Free</Select.Option>
              <Select.Option value="pro">Pro</Select.Option>
              <Select.Option value="enterprise">Enterprise</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="quota_daily"
            label="每日配额"
            rules={[{ required: true, message: '请输入每日配额' }]}
          >
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>

          {editingUser && (
            <Form.Item
              name="is_active"
              label="状态"
              valuePropName="checked"
            >
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
}
