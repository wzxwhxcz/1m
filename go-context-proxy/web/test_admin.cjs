const axios = require('axios');

const BASE_URL = 'http://localhost:8083';
const results = [];

async function test(name, fn) {
  try {
    await fn();
    results.push(`✅ ${name}`);
  } catch (error) {
    results.push(`❌ ${name}: ${error.message}`);
  }
}

async function runTests() {
  console.log('═══════════════════════════════════════════════════════════════');
  console.log('  🧪 管理后台 API 自动化测试报告');
  console.log('═══════════════════════════════════════════════════════════════\n');

  // 测试 1: 登录
  await test('登录接口 (admin/admin123)', async () => {
    const res = await axios.post(`${BASE_URL}/api/admin/login`, {
      username: 'admin',
      password: 'admin123'
    });
    if (res.data.code !== 0) throw new Error('Login failed');
    if (!res.data.data.token) throw new Error('No token returned');
  });

  // 测试 2: Dashboard 统计
  await test('仪表盘统计接口', async () => {
    const res = await axios.get(`${BASE_URL}/api/admin/stats/dashboard`);
    if (res.data.code !== 0) throw new Error('Dashboard API failed');
    const data = res.data.data;
    if (!data.total_requests) throw new Error('Missing total_requests');
    if (!data.success_rate) throw new Error('Missing success_rate');
  });

  // 测试 3: QPS 数据
  await test('QPS 数据接口 (60分钟)', async () => {
    const res = await axios.get(`${BASE_URL}/api/admin/stats/qps?minutes=60`);
    if (res.data.code !== 0) throw new Error('QPS API failed');
    if (!Array.isArray(res.data.data)) throw new Error('QPS data not array');
    if (res.data.data.length !== 60) throw new Error(`Expected 60 points, got ${res.data.data.length}`);
  });

  // 测试 4: 用户列表
  await test('用户列表接口', async () => {
    const res = await axios.get(`${BASE_URL}/api/admin/users?page=1&page_size=20`);
    if (res.data.code !== 0) throw new Error('Users list failed');
    if (!Array.isArray(res.data.data.users)) throw new Error('Users not array');
    if (res.data.data.total < 3) throw new Error('Expected at least 3 users');
  });

  // 测试 5: 创建用户
  await test('创建用户接口', async () => {
    const res = await axios.post(`${BASE_URL}/api/admin/users`, {
      email: 'test-auto@example.com',
      plan: 'pro',
      quota_daily: 500
    });
    if (res.data.code !== 0) throw new Error('Create user failed');
    if (!res.data.data.service_key) throw new Error('No service_key generated');
    if (!res.data.data.service_key.startsWith('sk-')) throw new Error('Invalid service_key format');
  });

  // 测试 6: 更新用户
  await test('更新用户接口', async () => {
    const res = await axios.put(`${BASE_URL}/api/admin/users/1`, {
      plan: 'enterprise',
      quota_daily: 5000
    });
    if (res.data.code !== 0) throw new Error('Update user failed');
    if (res.data.data.plan !== 'enterprise') throw new Error('Plan not updated');
  });

  // 测试 7: 用户详情
  await test('用户详情接口', async () => {
    const res = await axios.get(`${BASE_URL}/api/admin/users/1`);
    if (res.data.code !== 0) throw new Error('User detail failed');
    if (!res.data.data.email) throw new Error('Missing user email');
  });

  // 测试 8: 趋势数据
  await test('趋势统计接口 (7天)', async () => {
    const res = await axios.get(`${BASE_URL}/api/admin/stats/trend?days=7`);
    if (res.data.code !== 0) throw new Error('Trend API failed');
    if (!Array.isArray(res.data.data)) throw new Error('Trend data not array');
    if (res.data.data.length !== 7) throw new Error(`Expected 7 days, got ${res.data.data.length}`);
  });

  // 测试 9: 删除用户
  await test('删除用户接口', async () => {
    const res = await axios.delete(`${BASE_URL}/api/admin/users/3`);
    if (res.data.code !== 0) throw new Error('Delete user failed');
  });

  // 输出结果
  console.log('──────────────────────────────────────────────────────────────\n');
  console.log('📊 测试结果汇总:\n');
  results.forEach(r => console.log(r));
  
  const passed = results.filter(r => r.startsWith('✅')).length;
  const failed = results.filter(r => r.startsWith('❌')).length;
  
  console.log('\n──────────────────────────────────────────────────────────────');
  console.log(`\n总计: ${results.length} 个测试`);
  console.log(`通过: ${passed} ✅`);
  console.log(`失败: ${failed} ❌`);
  console.log(`成功率: ${((passed/results.length)*100).toFixed(1)}%`);
  console.log('\n═══════════════════════════════════════════════════════════════\n');
  
  process.exit(failed > 0 ? 1 : 0);
}

runTests().catch(err => {
  console.error('Test suite failed:', err.message);
  process.exit(1);
});
