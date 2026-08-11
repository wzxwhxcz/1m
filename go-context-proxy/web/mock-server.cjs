const express = require('express');
const cors = require('cors');
const bcrypt = require('bcryptjs');

const app = express();
const PORT = 8083;

app.use(cors());
app.use(express.json());

// Mock 数据
const mockAdmin = {
  username: 'admin',
  password: bcrypt.hashSync('admin123', 10), // $2a$10$...
};

const mockUsers = [
  {
    id: 1,
    service_key: 'sk-test-user-001',
    email: 'user1@example.com',
    username: 'user1',
    avatar_url: 'https://cdn.linux.do/user_avatar/connect.linux.do/user1/120/1_2.png',
    linux_do_id: 'linuxdo_user1',
    trust_level: 1,
    plan: 'pro',
    quota_daily: 1000,
    quota_used_today: 45,
    is_active: true,
    created_at: '2026-08-01T10:00:00Z',
  },
  {
    id: 2,
    service_key: 'sk-test-user-002',
    email: 'user2@example.com',
    username: 'user2',
    avatar_url: 'https://cdn.linux.do/user_avatar/connect.linux.do/user2/120/2_2.png',
    linux_do_id: 'linuxdo_user2',
    trust_level: 2,
    plan: 'pro',
    quota_daily: 2000,
    quota_used_today: 678,
    is_active: true,
    created_at: '2026-08-02T11:30:00Z',
  },
  {
    id: 3,
    service_key: 'sk-test-user-003',
    email: 'user3@example.com',
    username: 'user3',
    avatar_url: 'https://cdn.linux.do/user_avatar/connect.linux.do/user3/120/3_2.png',
    linux_do_id: 'linuxdo_user3',
    trust_level: 0,
    plan: 'free',
    quota_daily: 100,
    quota_used_today: 32,
    is_active: false,
    created_at: '2026-08-03T09:15:00Z',
  },
];

let nextUserId = 4;

// Mock 系统配置
const mockSystemConfig = {
  oauth_client_id: 'your-client-id',
  oauth_client_secret: 'your-client-secret',
  oauth_redirect_uri: 'http://localhost:5173/user/callback',
  default_plan_free: 'free:100',
  default_plan_trust_0: 'free:100',
  default_plan_trust_1: 'pro:1000',
  default_plan_trust_2: 'pro:2000',
  default_plan_trust_3: 'enterprise:5000',
  default_plan_trust_4: 'enterprise:10000',
};

// Mock 用户请求日志
const mockRequestLogs = [
  {
    id: 1,
    user_id: 1,
    upstream_url: 'https://api.openai.com/v1/chat/completions',
    input_tokens: 1500000,
    output_tokens: 400000,
    recall_triggered: true,
    recall_latency_ms: 850,
    total_latency_ms: 2340,
    status: 'success',
    created_at: '2026-08-04T10:23:15Z',
  },
  {
    id: 2,
    user_id: 1,
    upstream_url: 'https://api.anthropic.com/v1/messages',
    input_tokens: 50000,
    output_tokens: 2000,
    recall_triggered: false,
    recall_latency_ms: 0,
    total_latency_ms: 450,
    status: 'success',
    created_at: '2026-08-04T09:15:32Z',
  },
  {
    id: 3,
    user_id: 1,
    upstream_url: 'https://api.openai.com/v1/chat/completions',
    input_tokens: 2000000,
    output_tokens: 380000,
    recall_triggered: true,
    recall_latency_ms: 920,
    total_latency_ms: 2580,
    status: 'success',
    created_at: '2026-08-03T16:42:08Z',
  },
];

// 登录
app.post('/api/admin/login', (req, res) => {
  const { username, password } = req.body;
  
  if (username === mockAdmin.username && bcrypt.compareSync(password, mockAdmin.password)) {
    res.json({
      code: 0,
      message: 'success',
      data: {
        token: 'mock-jwt-token-' + Date.now(),
        user: { username: 'admin' },
      },
    });
  } else {
    res.status(401).json({
      code: 401,
      message: '用户名或密码错误',
    });
  }
});

// 概览统计
app.get('/api/admin/stats/overview', (req, res) => {
  res.json({
    code: 0,
    message: 'success',
    data: {
      total_requests: 12543,
      success_rate: 99.2,
      avg_latency: 45,
      recall_triggered: 856,
    },
  });
});

// 仪表盘统计（前端使用的接口）
app.get('/api/admin/stats/dashboard', (req, res) => {
  // 动态计算真实统计数据
  const activeUsers = mockUsers.filter(u => u.is_active).length;
  const totalQuotaUsed = mockUsers.reduce((sum, u) => sum + u.quota_used_today, 0);
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      today_requests: Math.floor(totalQuotaUsed * 0.3), // 今日请求数
      total_requests: totalQuotaUsed, // 总请求数
      success_rate: 99.2,
      avg_latency: 45,
      recall_triggered: Math.floor(totalQuotaUsed * 0.15), // 约15%触发召回
      active_users: activeUsers,
      error_rate: 0.8,
    },
  });
});

// 实时 QPS（每秒更新）
app.get('/api/admin/stats/realtime', (req, res) => {
  const now = Date.now();
  const data = Array.from({ length: 60 }, (_, i) => ({
    timestamp: now - (59 - i) * 1000,
    qps: Math.floor(Math.random() * 50) + 80,
  }));
  
  res.json({
    code: 0,
    message: 'success',
    data,
  });
});

// QPS 数据（前端使用的接口）
app.get('/api/admin/stats/qps', (req, res) => {
  const { minutes = 60 } = req.query;
  const now = Date.now();
  const data = Array.from({ length: parseInt(minutes) }, (_, i) => ({
    timestamp: now - (parseInt(minutes) - 1 - i) * 60000,
    value: Math.floor(Math.random() * 50) + 80,
  }));
  
  res.json({
    code: 0,
    message: 'success',
    data,
  });
});

// 用户列表
app.get('/api/admin/users', (req, res) => {
  const { page = 1, page_size = 20, search = '' } = req.query;
  
  let filtered = mockUsers;
  if (search) {
    filtered = mockUsers.filter(u => 
      u.email.includes(search) || u.service_key.includes(search)
    );
  }
  
  const start = (page - 1) * page_size;
  const end = start + parseInt(page_size);
  const paginatedUsers = filtered.slice(start, end);
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      users: paginatedUsers,
      total: filtered.length,
      page: parseInt(page),
      page_size: parseInt(page_size),
    },
  });
});

// 创建用户
app.post('/api/admin/users', (req, res) => {
  const { email, plan, quota_daily } = req.body;
  
  const newUser = {
    id: nextUserId++,
    service_key: `sk-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    email,
    plan: plan || 'free',
    quota_daily: quota_daily || 100,
    quota_used_today: 0,
    is_active: true,
    created_at: new Date().toISOString(),
  };
  
  mockUsers.push(newUser);
  
  res.json({
    code: 0,
    message: 'success',
    data: newUser,
  });
});

// 更新用户
app.put('/api/admin/users/:id', (req, res) => {
  const { id } = req.params;
  const { email, plan, quota_daily, is_active } = req.body;
  
  const user = mockUsers.find(u => u.id === parseInt(id));
  if (!user) {
    return res.status(404).json({
      code: 404,
      message: '用户不存在',
    });
  }
  
  if (email !== undefined) user.email = email;
  if (plan !== undefined) user.plan = plan;
  if (quota_daily !== undefined) user.quota_daily = quota_daily;
  if (is_active !== undefined) user.is_active = is_active;
  
  res.json({
    code: 0,
    message: 'success',
    data: user,
  });
});

// 删除用户
app.delete('/api/admin/users/:id', (req, res) => {
  const { id } = req.params;
  const index = mockUsers.findIndex(u => u.id === parseInt(id));
  
  if (index === -1) {
    return res.status(404).json({
      code: 404,
      message: '用户不存在',
    });
  }
  
  mockUsers.splice(index, 1);
  
  res.json({
    code: 0,
    message: 'success',
  });
});

// 用户详情
app.get('/api/admin/users/:id', (req, res) => {
  const { id } = req.params;
  const user = mockUsers.find(u => u.id === parseInt(id));
  
  if (!user) {
    return res.status(404).json({
      code: 404,
      message: '用户不存在',
    });
  }
  
  res.json({
    code: 0,
    message: 'success',
    data: user,
  });
});

// 趋势统计
app.get('/api/admin/stats/trend', (req, res) => {
  const { days = 7 } = req.query;
  const data = [];
  
  for (let i = parseInt(days) - 1; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    
    data.push({
      date: date.toISOString().split('T')[0],
      requests: Math.floor(Math.random() * 5000) + 10000,
      success_rate: 98 + Math.random() * 2,
      avg_latency: 40 + Math.floor(Math.random() * 20),
    });
  }
  
  res.json({
    code: 0,
    message: 'success',
    data,
  });
});

// ========== 用户端 API ==========

// OAuth 回调处理（模拟 Linux Do 登录）
app.post('/api/user/oauth/callback', (req, res) => {
  const { code } = req.body;
  
  if (!code) {
    return res.status(400).json({
      code: 400,
      message: '缺少授权码',
    });
  }
  
  // 模拟：用 code 换取 access_token，然后获取用户信息
  const mockLinuxDoUsers = [
    { id: 'linuxdo_12345', username: 'testuser', name: '测试用户', trust_level: 2, avatar_template: 'https://cdn.linux.do/user_avatar/connect.linux.do/testuser/120/123_2.png' },
    { id: 'linuxdo_user1', username: 'user1', name: '用户1', trust_level: 1, avatar_template: 'https://cdn.linux.do/user_avatar/connect.linux.do/user1/120/1_2.png' },
  ];
  
  // 根据 code 模拟返回不同用户（实际应该调用 Linux Do API）
  const mockLinuxDoUser = code === 'test_code_existing' 
    ? mockLinuxDoUsers[1]  // 已存在用户
    : mockLinuxDoUsers[0];  // 新用户
  
  // 检查用户是否已存在
  let user = mockUsers.find(u => u.linux_do_id === mockLinuxDoUser.id);
  
  if (!user) {
    // 新用户：生成 service_key
    const serviceKey = `sk-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    // 根据 trust_level 分配套餐
    const planMap = {
      0: { plan: 'free', quota: 100 },
      1: { plan: 'pro', quota: 1000 },
      2: { plan: 'pro', quota: 2000 },
      3: { plan: 'enterprise', quota: 5000 },
      4: { plan: 'enterprise', quota: 10000 },
    };
    const { plan, quota } = planMap[mockLinuxDoUser.trust_level] || planMap[0];
    
    user = {
      id: nextUserId++,
      service_key: serviceKey,
      linux_do_id: mockLinuxDoUser.id,
      username: mockLinuxDoUser.username,
      email: `${mockLinuxDoUser.username}@linux.do`,
      avatar_url: mockLinuxDoUser.avatar_template,
      trust_level: mockLinuxDoUser.trust_level,
      plan,
      quota_daily: quota,
      quota_used_today: 0,
      is_active: true,
      created_at: new Date().toISOString(),
    };
    
    mockUsers.push(user);
  }
  
  // 生成用户 JWT token（简化版）
  const userToken = `user_token_${user.id}_${Date.now()}`;
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      token: userToken,
      user: {
        id: user.id,
        service_key: user.service_key,
        username: user.username,
        email: user.email,
        plan: user.plan,
        quota_daily: user.quota_daily,
        trust_level: user.trust_level,
        avatar_url: user.avatar_url,
      },
    },
  });
});

// 获取当前用户信息
app.get('/api/user/profile', (req, res) => {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      code: 401,
      message: '未授权',
    });
  }
  
  const token = authHeader.substring(7);
  
  // 从 token 中提取 user_id（简化版：user_token_1_xxxxx）
  const match = token.match(/user_token_(\d+)_/);
  if (!match) {
    return res.status(401).json({
      code: 401,
      message: '无效的 token',
    });
  }
  
  const userId = parseInt(match[1]);
  const user = mockUsers.find(u => u.id === userId);
  
  if (!user) {
    return res.status(404).json({
      code: 404,
      message: '用户不存在',
    });
  }
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      id: user.id,
      service_key: user.service_key,
      username: user.username,
      email: user.email,
      avatar_url: user.avatar_url,
      trust_level: user.trust_level,
      plan: user.plan,
      quota_daily: user.quota_daily,
      quota_used_today: user.quota_used_today,
      is_active: user.is_active,
      created_at: user.created_at,
    },
  });
});

// 重置 API 密钥
app.post('/api/user/api-key/reset', (req, res) => {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      code: 401,
      message: '未授权',
    });
  }
  
  const token = authHeader.substring(7);
  const match = token.match(/user_token_(\d+)_/);
  
  if (!match) {
    return res.status(401).json({
      code: 401,
      message: '无效的 token',
    });
  }
  
  const userId = parseInt(match[1]);
  const user = mockUsers.find(u => u.id === userId);
  
  if (!user) {
    return res.status(404).json({
      code: 404,
      message: '用户不存在',
    });
  }
  
  // 生成新的 service_key
  const newServiceKey = `sk-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  user.service_key = newServiceKey;
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      new_service_key: newServiceKey,
    },
  });
});

// 用户请求日志
app.get('/api/user/logs', (req, res) => {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      code: 401,
      message: '未授权',
    });
  }
  
  const token = authHeader.substring(7);
  const match = token.match(/user_token_(\d+)_/);
  
  if (!match) {
    return res.status(401).json({
      code: 401,
      message: '无效的 token',
    });
  }
  
  const userId = parseInt(match[1]);
  const { page = 1, page_size = 20 } = req.query;
  
  // 过滤该用户的日志
  const userLogs = mockRequestLogs.filter(log => log.user_id === userId);
  
  const start = (page - 1) * page_size;
  const end = start + parseInt(page_size);
  const paginatedLogs = userLogs.slice(start, end);
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      logs: paginatedLogs,
      total: userLogs.length,
      page: parseInt(page),
      page_size: parseInt(page_size),
    },
  });
});

// 用户配额使用趋势
app.get('/api/user/trend', (req, res) => {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      code: 401,
      message: '未授权',
    });
  }
  
  const token = authHeader.substring(7);
  const match = token.match(/user_token_(\d+)_/);
  
  if (!match) {
    return res.status(401).json({
      code: 401,
      message: '无效的 token',
    });
  }
  
  const userId = parseInt(match[1]);
  const user = mockUsers.find(u => u.id === userId);
  
  if (!user) {
    return res.status(404).json({
      code: 404,
      message: '用户不存在',
    });
  }
  
  const { days = 7 } = req.query;
  const data = [];
  
  for (let i = parseInt(days) - 1; i >= 0; i--) {
    const date = new Date();
    date.setDate(date.getDate() - i);
    
    const used = Math.floor(Math.random() * (user.quota_daily * 0.8)) + Math.floor(user.quota_daily * 0.1);
    const requests = Math.floor(Math.random() * 150) + 50;
    const recallCount = Math.floor(Math.random() * 20) + 5;
    
    data.push({
      date: date.toISOString().split('T')[0],
      used,
      quota: user.quota_daily,
      requests,
      recall_count: recallCount,
    });
  }
  
  res.json({
    code: 0,
    message: 'success',
    data,
  });
});

// 用户仪表盘数据
app.get('/api/user/dashboard', (req, res) => {
  const authHeader = req.headers.authorization;
  
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      code: 401,
      message: '未授权',
    });
  }
  
  const token = authHeader.substring(7);
  const match = token.match(/user_token_(\d+)_/);
  
  if (!match) {
    return res.status(401).json({
      code: 401,
      message: '无效的 token',
    });
  }
  
  const userId = parseInt(match[1]);
  const user = mockUsers.find(u => u.id === userId);
  
  if (!user) {
    return res.status(404).json({
      code: 404,
      message: '用户不存在',
    });
  }
  
  // 计算统计数据
  const userLogs = mockRequestLogs.filter(log => log.user_id === userId);
  const totalRequests = userLogs.length * 50; // 模拟总请求数
  const monthlyRequests = userLogs.length * 15; // 模拟本月请求数
  const recallTriggered = userLogs.filter(log => log.recall_triggered).length * 5;
  const avgLatency = userLogs.length > 0 
    ? Math.floor(userLogs.reduce((sum, log) => sum + log.total_latency_ms, 0) / userLogs.length)
    : 52;
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      quota_daily: user.quota_daily,
      quota_used_today: user.quota_used_today,
      quota_remaining: user.quota_daily - user.quota_used_today,
      total_requests: totalRequests,
      monthly_requests: monthlyRequests,
      recall_triggered: recallTriggered,
      avg_latency: avgLatency,
    },
  });
});

// ========== 管理端配置 API ==========

// 获取系统配置
app.get('/api/admin/config', (req, res) => {
  res.json({
    code: 0,
    message: 'success',
    data: mockSystemConfig,
  });
});

// 更新系统配置
app.put('/api/admin/config', (req, res) => {
  const { key, value } = req.body;
  
  if (!key) {
    return res.status(400).json({
      code: 400,
      message: '缺少配置键',
    });
  }
  
  if (!mockSystemConfig.hasOwnProperty(key)) {
    return res.status(404).json({
      code: 404,
      message: '配置项不存在',
    });
  }
  
  mockSystemConfig[key] = value;
  
  res.json({
    code: 0,
    message: 'success',
    data: {
      key,
      value,
    },
  });
});

// ========== 压缩代理 API ==========

// 动态路由：压缩代理请求
// 格式: POST /:service_key/https://api.openai.com/v1/chat/completions
app.post('/:service_key/https\\://api.openai.com/v1/chat/completions', async (req, res) => {
  const { service_key } = req.params;
  const authHeader = req.get('Authorization');
  
  console.log(`[Proxy Request] service_key=${service_key}`);
  console.log(`[Proxy Request] Authorization=${authHeader}`);
  console.log(`[Proxy Request] body=`, req.body);
  
  // 验证 service_key
  const user = mockUsers.find(u => u.service_key === service_key);
  if (!user) {
    return res.status(401).json({
      error: {
        message: 'Invalid service key',
        type: 'authentication_error',
      },
    });
  }
  
  // 检查配额
  if (user.quota_used >= user.quota_total) {
    return res.status(429).json({
      error: {
        message: 'Quota exceeded',
        type: 'quota_error',
      },
    });
  }
  
  // 模拟召回服务压缩上下文
  const originalMessages = req.body.messages || [];
  const compressedMessages = originalMessages.length > 5 
    ? [
        { role: 'system', content: '[Compressed context] Previous conversation summary...' },
        ...originalMessages.slice(-3) // 保留最近3条
      ]
    : originalMessages;
  
  const compressionRatio = originalMessages.length > 5 
    ? ((originalMessages.length - compressedMessages.length) / originalMessages.length * 100).toFixed(1)
    : 0;
  
  console.log(`[Compression] Original: ${originalMessages.length} messages, Compressed: ${compressedMessages.length} messages, Ratio: ${compressionRatio}%`);
  
  // 模拟 OpenAI API 响应
  const isStream = req.body.stream === true;
  
  if (isStream) {
    // 流式响应
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    
    const chunks = [
      { role: 'assistant', content: 'Hello' },
      { role: 'assistant', content: ' from' },
      { role: 'assistant', content: ' compressed' },
      { role: 'assistant', content: ' context' },
      { role: 'assistant', content: ' proxy!' },
    ];
    
    for (let i = 0; i < chunks.length; i++) {
      const chunk = {
        id: 'chatcmpl-mock-' + Date.now(),
        object: 'chat.completion.chunk',
        created: Math.floor(Date.now() / 1000),
        model: req.body.model || 'gpt-3.5-turbo',
        choices: [
          {
            index: 0,
            delta: chunks[i],
            finish_reason: i === chunks.length - 1 ? 'stop' : null,
          },
        ],
      };
      res.write(`data: ${JSON.stringify(chunk)}\n\n`);
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    res.write('data: [DONE]\n\n');
    res.end();
  } else {
    // 非流式响应
    setTimeout(() => {
      res.json({
        id: 'chatcmpl-mock-' + Date.now(),
        object: 'chat.completion',
        created: Math.floor(Date.now() / 1000),
        model: req.body.model || 'gpt-3.5-turbo',
        choices: [
          {
            index: 0,
            message: {
              role: 'assistant',
              content: `Hello from compressed context proxy! (Compression ratio: ${compressionRatio}%)`,
            },
            finish_reason: 'stop',
          },
        ],
        usage: {
          prompt_tokens: 50,
          completion_tokens: 10,
          total_tokens: 60,
        },
      });
    }, 500);
  }
  
  // 更新用户配额
  user.quota_used += 1;
});

// ==================== 系统配置 API ====================
// GET /api/admin/config - 获取系统配置
app.get('/api/admin/config', (req, res) => {
  res.json({
    code: 0,
    message: 'success',
    data: {
      max_context_tokens: 400000,
      compression_ratio: 2.5,
      model_provider: 'openai',
      cache_enabled: true,
      recall_enabled: true,
      max_concurrent_requests: 100,
    },
  });
});

// PUT /api/admin/config - 更新系统配置
app.put('/api/admin/config', (req, res) => {
  const config = req.body;
  console.log('更新系统配置:', config);
  res.json({
    code: 0,
    message: '配置更新成功',
    data: config,
  });
});

app.listen(PORT, () => {
  console.log(`Mock API server running on http://localhost:${PORT}`);
  console.log(`Compression proxy endpoint: POST /:service_key/*`);
});
