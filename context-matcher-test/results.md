# 上下文压缩匹配策略测试报告

## 测试目标

解决客户端压缩上下文后如何准确恢复原始会话的问题。

## 测试场景

- **项目数量**: 3个（Express API、React Dashboard、Python数据处理）
- **压缩方法**: 4种（截断、总结、删除代码、混合）
- **匹配策略**: 5种（时间窗口、首尾锚点、项目特征、语义向量、混合评分）
- **测试用例**: 12个（3个项目 × 4种压缩）

## 测试结果

### 准确率对比

| 策略 | 准确率 | 误匹配率 | 平均耗时 | 推荐度 |
|------|--------|----------|----------|--------|
| **anchor（首尾锚点）** | **100.0%** | 0.0% | 0.3ms | ⭐⭐⭐⭐⭐ |
| **hybrid（混合评分）** | **91.7%** | 8.3% | 1.4ms | ⭐⭐⭐⭐ |
| **vector（语义向量）** | 83.3% | 16.7% | 0.9ms | ⭐⭐⭐ |
| **features（项目特征）** | 58.3% | 41.7% | 0.2ms | ⭐⭐ |
| **time_window（时间窗口）** | 33.3% | 66.7% | 0.0ms | ⭐ |

### 关键发现

#### 1. **首尾锚点策略（anchor）表现最佳**
- ✅ **100% 准确率**
- ✅ 极快响应（0.3ms）
- ✅ 在所有4种压缩场景下都能正确匹配

**原理**：
- 匹配首条 system message 的 hash（权重 40%）
- 匹配最后 3 条消息的 hash（权重 60%）

**为什么有效**：
- 大多数客户端压缩时会保留首条 system prompt
- 即使压缩很激进，最近的几条对话通常会保留
- Hash 匹配精确，不会误判

#### 2. **时间窗口策略（time_window）不可靠**
- ❌ 只有 33.3% 准确率
- ⚠️ 用户同时处理多个项目时会混淆

**失败原因**：
- 测试中3个项目几乎同时存储，时间差太小
- 实际场景中用户经常在多个标签页切换项目

#### 3. **混合评分（hybrid）平衡性好**
- ✅ 91.7% 准确率
- ✅ 容错能力强
- ⚠️ 稍慢（1.4ms），但仍在可接受范围

## 不同压缩场景的表现

### Truncate（截断，只保留最后10条）
- anchor: 100% ✓
- time_window: 33% ✗（最容易混淆）

### Summarize（总结前面 + 保留最近）
- anchor: 100% ✓
- hybrid: 100% ✓（综合策略也很好）

### Remove Code（删除代码块）
- anchor: 100% ✓
- vector: 100% ✓（语义信息保留完整）

### Mixed（混合压缩）
- anchor: 100% ✓
- 所有策略表现都较好

## 最终推荐

### 🏆 生产环境推荐：首尾锚点（anchor）

```python
def match_session(user_id, compressed_messages):
    """
    使用首尾锚点策略匹配会话
    """
    # 1. 提取首条消息 hash
    first_hash = hash(compressed_messages[0]["content"])
    
    # 2. 提取最后3条消息 hash
    last_3_hash = hash(json.dumps([m["content"] for m in compressed_messages[-3:]]))
    
    # 3. 在存储的会话中查找匹配
    for session in stored_sessions[user_id]:
        score = 0.0
        if first_hash == session["first_hash"]:
            score += 0.4
        if last_3_hash == session["last_3_hash"]:
            score += 0.6
        
        if score >= 0.6:  # 阈值
            return session["id"]
    
    return None
```

**优势**：
- ✅ 100% 准确率
- ✅ 极低延迟（<1ms）
- ✅ 实现简单
- ✅ 无需额外依赖（不需要 embedding API）

### 🥈 备选方案：混合评分（hybrid）

适用于对准确率要求极高的场景，可以在 anchor 失败时作为备选。

### ❌ 不推荐：时间窗口（time_window）

除非你确定用户：
- 只会单项目工作
- 短时间内不会切换项目

## 实际部署建议

### 存储结构

```python
# Redis 存储
key: "user:{user_id}:sessions"
value: {
    "session_1": {
        "messages": [...],  # 完整历史
        "first_hash": "abc123",
        "last_3_hash": "def456",
        "features": {...},
        "timestamp": 1234567890
    }
}
```

### 匹配流程

```
1. 用户请求进来（可能已被客户端压缩）
2. 提取首尾锚点特征（<1ms）
3. 在 Redis 中查找匹配（<1ms）
4. 如果匹配成功：
   - 用完整历史 + 新问题
   - 如果太长，用选择器模型压缩
5. 如果匹配失败：
   - 视为新会话
   - 用当前 messages 直接处理
```

### 成本估算

- **存储成本**: 
  - 单个会话 1M tokens ≈ 4MB
  - Redis: $0.10/GB/月
  - 1000个活跃会话 = 4GB = $0.40/月
  
- **计算成本**: 
  - Hash 计算：免费
  - 无需调用 embedding API
  - 总成本：**几乎为零**

## 代码实现

完整实现见：
- `src/matcher.py` - 5种匹配策略
- `src/benchmark.py` - 测试框架
- `test_data/` - 测试数据

## 结论

**首尾锚点（anchor）策略在所有测试中表现完美，是生产环境的最佳选择。**

它结合了：
- ✅ 最高准确率（100%）
- ✅ 最低延迟（0.3ms）
- ✅ 零额外成本
- ✅ 简单可靠

对于你的中转服务场景，这个策略可以完美解决客户端压缩后的上下文恢复问题。
