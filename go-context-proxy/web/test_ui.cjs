const axios = require('axios');
const BASE_URL = 'http://localhost:5178';

console.log('═══════════════════════════════════════════════════════════════');
console.log('  🎨 前端 UI 自动化检查报告');
console.log('═══════════════════════════════════════════════════════════════\n');

async function checkUI() {
  const results = [];
  
  // 测试 1: 前端服务是否运行
  try {
    const res = await axios.get(BASE_URL, { timeout: 3000 });
    if (res.status === 200) {
      results.push('✅ 前端服务运行正常 (http://localhost:5178)');
    }
  } catch (error) {
    results.push('❌ 前端服务未运行或无法访问');
    console.log('\n📊 测试结果:\n');
    results.forEach(r => console.log(r));
    console.log('\n═══════════════════════════════════════════════════════════════\n');
    process.exit(1);
  }
  
  // 测试 2: 检查关键文件是否存在颜色主题修改
  const fs = require('fs');
  const filesToCheck = [
    'src/pages/LoginPage.tsx',
    'src/pages/DashboardPage.tsx',
    'src/pages/UsersPage.tsx',
    'src/pages/StatisticsPage.tsx',
    'src/App.tsx'
  ];
  
  let colorIssues = [];
  for (const file of filesToCheck) {
    try {
      const content = fs.readFileSync(file, 'utf8');
      if (content.includes('#FBBF24')) {
        colorIssues.push(`  ⚠️  ${file} 仍包含黄色 #FBBF24`);
      }
      if (content.includes('#5B8CFF')) {
        // 应该包含蓝色
      } else {
        colorIssues.push(`  ⚠️  ${file} 缺少蓝色主题 #5B8CFF`);
      }
    } catch (e) {
      // 文件不存在
    }
  }
  
  if (colorIssues.length === 0) {
    results.push('✅ UI 颜色主题已全部更新为蓝色 (#5B8CFF)');
  } else {
    results.push('❌ UI 颜色主题存在问题:');
    colorIssues.forEach(issue => results.push(issue));
  }
  
  // 测试 3: 检查 API 客户端配置
  try {
    const apiClient = fs.readFileSync('src/api/client.ts', 'utf8');
    if (apiClient.includes('dashboard') && apiClient.includes('qps')) {
      results.push('✅ API 客户端包含 dashboard 和 qps 方法');
    } else {
      results.push('❌ API 客户端缺少必要的方法');
    }
  } catch (e) {
    results.push('⚠️  无法检查 API 客户端配置');
  }
  
  console.log('📊 UI 检查结果:\n');
  results.forEach(r => console.log(r));
  
  const passed = results.filter(r => r.startsWith('✅')).length;
  const failed = results.filter(r => r.startsWith('❌')).length;
  
  console.log('\n──────────────────────────────────────────────────────────────');
  console.log(`\n通过: ${passed} ✅`);
  console.log(`失败: ${failed} ❌`);
  console.log('\n═══════════════════════════════════════════════════════════════\n');
  
  return failed === 0;
}

checkUI().then(success => {
  if (success) {
    console.log('💡 下一步: 在浏览器中打开 http://localhost:5178/login');
    console.log('   使用账号: admin / admin123');
    console.log('   验证以下功能:');
    console.log('   1. 登录按钮是蓝色（不是黄色）');
    console.log('   2. 仪表盘显示 6 个统计数据卡片');
    console.log('   3. QPS 图表显示蓝色曲线');
    console.log('   4. 用户管理页面可以查看/创建/编辑/删除用户');
    console.log('   5. 统计分析页面显示图表');
    console.log('   6. 监控页面显示服务状态');
  }
  process.exit(success ? 0 : 1);
}).catch(err => {
  console.error('检查失败:', err.message);
  process.exit(1);
});
