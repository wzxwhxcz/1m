# 前端测试指南

## 🚀 快速开始

### 1. 启动服务

前端和 Mock API 已经在运行：

- **前端**: http://localhost:5178
- **Mock API**: http://localhost:8083

如果需要重启：

```bash
# 启动 Mock API（在 web 目录下）
cd /d/1m/go-context-proxy/web
node mock-server.cjs

# 启动前端（在另一个终端）
npm run dev -- --port 5178
```

### 2. 默认账号

```
用户名: admin
密码: admin123
```

---

## 📋 完整测试清单

### ✅ 测试 1：登录页面 (http://localhost:5178/login)

**视觉检查**：
- [ ] 页面背景是深色 (#0F1117)
- [ ] 卡片背景是深灰色 (#171A23)
- [ ] 标题 "Context Proxy" 是**蓝色** (#5B8CFF)，不是黄色
- [ ] 登录按钮是蓝色 (#5B8CFF)
- [ ] 输入框有图标和占位符

**功能测试**：
- [ ] 输入 admin / admin123，点击"登 录"
- [ ] 登录成功后自动跳转到仪表盘 (/dashboard)
- [ ] 如果输入错误密码，显示红色错误提示

---

### ✅ 测试 2：仪表盘页面 (/dashboard)

**顶部统计卡片**（应显示 4 个卡片）：
- [ ] 今日请求数：12543（带绿色百分比标签）
- [ ] 成功率：99.2%（带绿色百分比标签）
- [ ] 平均延迟：45ms（带蓝色图标）
- [ ] 召回触发：856（带紫色图标）

**实时 QPS 曲线图**：
- [ ] 图表标题是 "实时 QPS"
- [ ] X 轴显示时间，Y 轴显示 QPS 值
- [ ] 曲线是**蓝色** (#5B8CFF)，有半透明填充
- [ ] 曲线平滑，数据点在 80-130 之间波动
- [ ] 每秒自动刷新一次（观察曲线移动）

---

### ✅ 测试 3：用户管理页面 (/users)

**用户列表**：
- [ ] 显示 3 个测试用户
- [ ] Service Key 是蓝色等宽字体，右侧有复制按钮
- [ ] 套餐显示标签：free（蓝色）、pro（紫色）、enterprise（金色）
- [ ] 配额进度条：
  - user1: 45/100 (45%)
  - user2: 678/1000 (67.8%)
  - user3: 3245/10000 (32.45%)
- [ ] 状态标签：正常（绿色）、禁用（红色）

**创建用户**：
- [ ] 点击右上角"新增用户"按钮
- [ ] 弹出表单对话框
- [ ] 填写：
  - 邮箱: test@example.com
  - 套餐: pro（下拉选择）
  - 每日配额: 500
- [ ] 点击"确定"，新用户出现在列表顶部
- [ ] 新用户的 Service Key 自动生成（sk-xxxxx 格式）

**编辑用户**：
- [ ] 点击任意用户的"编辑"按钮
- [ ] 表单预填充该用户的数据
- [ ] 修改套餐为 enterprise，每日配额改为 5000
- [ ] 点击"确定"，列表更新成功

**删除用户**：
- [ ] 点击任意用户的"删除"按钮
- [ ] 弹出确认对话框："确定要删除该用户吗？"
- [ ] 点击"确定"，用户从列表消失

**搜索功能**：
- [ ] 在搜索框输入 "user1@example.com"
- [ ] 列表只显示匹配的用户
- [ ] 清空搜索框，所有用户重新显示

---

### ✅ 测试 4：统计分析页面 (/statistics)

**请求趋势图**：
- [ ] 图表标题是 "请求趋势（最近 7 天）"
- [ ] X 轴显示日期（7 天）
- [ ] Y 轴显示请求数（10,000-15,000 范围）
- [ ] 面积图是蓝色渐变填充
- [ ] 鼠标悬停显示具体数值

**成功率趋势图**：
- [ ] 图表标题是 "成功率趋势"
- [ ] 折线图是绿色
- [ ] Y 轴范围在 98%-100%
- [ ] 显示 7 天的数据点

**平均延迟趋势图**：
- [ ] 图表标题是 "平均延迟趋势"
- [ ] 折线图是橙色
- [ ] Y 轴单位是 ms
- [ ] 延迟在 40-60ms 范围

---

### ✅ 测试 5：系统监控页面 (/monitoring)

**服务状态卡片**：
- [ ] 显示 "Go Proxy Service"、"Python Recall Service"、"Redis"、"PostgreSQL"
- [ ] 所有服务状态都是"运行中"（绿色勾号）

**错误日志表格**：
- [ ] 表格显示 10 条模拟日志
- [ ] 列包括：时间、级别、服务、消息、详情
- [ ] 级别标签颜色：error（红色）、warn（橙色）、info（蓝色）
- [ ] 可以分页浏览（每页 10 条）

---

### ✅ 测试 6：响应式布局

**侧边栏**：
- [ ] 侧边栏是深色背景
- [ ] Logo 和菜单项清晰可见
- [ ] 当前页面的菜单项高亮显示（蓝色）
- [ ] 底部显示"退出登录"按钮

**顶部导航栏**：
- [ ] 显示当前页面标题
- [ ] 右侧显示用户名和头像
- [ ] 背景与主内容区协调

---

## 🎨 UI 验收标准

### 颜色规范（已修复）

- ✅ **主色调**：专业蓝色 #5B8CFF（不是黄色 #FBBF24）
- ✅ **背景色**：
  - 页面背景：#0F1117（深黑）
  - 卡片背景：#171A23（深灰）
  - 输入框背景：#1E222E（中灰）
- ✅ **文本颜色**：
  - 主文本：#F3F4F6（浅灰白）
  - 次要文本：#9CA3AF（中灰）
- ✅ **状态颜色**：
  - 成功/正常：#10B981（绿色）
  - 警告：#F59E0B（橙色）
  - 错误/禁用：#EF4444（红色）

### 组件验收

- [ ] 所有按钮有 hover 效果（颜色加深）
- [ ] 输入框有 focus 边框高亮（蓝色）
- [ ] 表格行有 hover 效果（背景变浅灰）
- [ ] 加载状态显示 Spin 组件（蓝色旋转）
- [ ] 所有图标清晰可见，大小适中

---

## 🐛 已知问题

### 已修复
- ✅ 登录页面和所有按钮从黄色 (#FBBF24) 改为蓝色 (#5B8CFF)
- ✅ Mock API 接口响应格式正确（统一 `{code, message, data}` 结构）
- ✅ Vite 代理配置正确转发 `/api` 到 Mock API (8083)

### 当前限制
- ⚠️ 这是前端展示版本，使用 Mock API（假数据）
- ⚠️ 真实的 Rust 后端需要编译后才能运行（GitHub Actions 会自动构建）
- ⚠️ 图表数据是随机生成的，用于演示 UI 效果

---

## 📊 API 接口文档

所有接口已在 Mock API 中实现：

### 认证

**POST /api/admin/login**
```json
Request:
{
  "username": "admin",
  "password": "admin123"
}

Response:
{
  "code": 0,
  "message": "success",
  "data": {
    "token": "mock-jwt-token-xxx",
    "user": { "username": "admin" }
  }
}
```

### 统计数据

**GET /api/admin/stats/overview**
```json
Response:
{
  "code": 0,
  "data": {
    "total_requests": 12543,
    "success_rate": 99.2,
    "avg_latency": 45,
    "recall_triggered": 856
  }
}
```

**GET /api/admin/stats/realtime**
```json
Response:
{
  "code": 0,
  "data": [
    { "timestamp": 1785838538000, "qps": 91 },
    { "timestamp": 1785838539000, "qps": 93 },
    ...
  ]
}
```

**GET /api/admin/stats/trend?days=7**
```json
Response:
{
  "code": 0,
  "data": [
    {
      "date": "2026-08-04",
      "requests": 12543,
      "success_rate": 99.2,
      "avg_latency": 45
    },
    ...
  ]
}
```

### 用户管理

**GET /api/admin/users?page=1&page_size=20&search=**
```json
Response:
{
  "code": 0,
  "data": {
    "users": [...],
    "total": 3,
    "page": 1,
    "page_size": 20
  }
}
```

**POST /api/admin/users**
```json
Request:
{
  "email": "test@example.com",
  "plan": "pro",
  "quota_daily": 500
}

Response:
{
  "code": 0,
  "data": {
    "id": 4,
    "service_key": "sk-xxxxx",
    "email": "test@example.com",
    "plan": "pro",
    "quota_daily": 500,
    "quota_used_today": 0,
    "is_active": true,
    "created_at": "2026-08-04T10:15:38.149Z"
  }
}
```

**PUT /api/admin/users/:id**
```json
Request:
{
  "email": "updated@example.com",
  "plan": "enterprise",
  "quota_daily": 5000,
  "is_active": true
}

Response:
{
  "code": 0,
  "data": { ...updated user... }
}
```

**DELETE /api/admin/users/:id**
```json
Response:
{
  "code": 0,
  "message": "success"
}
```

**GET /api/admin/users/:id**
```json
Response:
{
  "code": 0,
  "data": { ...user details... }
}
```

---

## ✅ 验收完成标准

当以下所有项都完成时，前端即可交付：

- [x] UI 颜色从黄色改为蓝色（已完成）
- [x] Mock API 所有接口正常工作（已验证）
- [ ] 用户手动测试所有 6 个页面功能正常
- [ ] 所有 CRUD 操作（创建、读取、更新、删除）正常工作
- [ ] 图表和数据可视化正常渲染
- [ ] 没有控制台错误（按 F12 查看）

---

## 🎯 下一步

1. **现在**: 请按照上面的测试清单逐项测试前端
2. **完成后**: 报告任何发现的 UI/功能问题
3. **最终**: 等待 GitHub Actions 构建 Rust 后端二进制文件，然后集成真实后端

---

**测试开始时间**: 2026-08-04
**测试人**: [待填写]
**预计测试时间**: 15-20 分钟
