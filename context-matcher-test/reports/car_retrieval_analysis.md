# CAR (Cluster-based Adaptive Retrieval) 测试报告

生成时间: 2026-08-04 12:37:45

## 测试配置

- **数据集**: 300条消息，3个话题 (React/Python/Docker)
- **聚类算法**: KMeans (n_clusters=3)
- **向量模型**: all-MiniLM-L6-v2
- **测试查询**: 5个 (短查询2个，长查询2个，中等1个)

## 测试方法

### CAR (Cluster-based Adaptive Retrieval)
1. **预处理**: 对所有消息进行K-Means聚类
2. **查询路由**: 计算查询与各簇中心的相似度，优先检索相关簇
3. **自适应截断**: 根据簇内相似度分布动态决定召回数量
4. **全局精排**: 跨簇排序后返回Top-K

### Baseline (Dense Only)
- 纯向量检索，遍历所有消息计算相似度

## 汇总结果

| 方法 | 平均Precision@50 | 平均耗时 |
|------|------------------|----------|
| CAR (KMeans + Adaptive) | 94.4% | 91.8ms |
| CAR (KMeans + Fixed) | 100.0% | 33.5ms |
| Baseline (Dense Only) | 92.4% | 100.3ms |

## 详细结果

### 查询 1: "re-renders"
- **预期话题**: react
- **查询类型**: short

| 方法 | Precision@50 | 耗时 |
|------|--------------|------|
| CAR (KMeans + Adaptive) | 100.0% | 100.7ms |
| CAR (KMeans + Fixed) | 100.0% | 28.0ms |
| Baseline (Dense Only) | 92.0% | 109.5ms |

### 查询 2: "useReducer"
- **预期话题**: react
- **查询类型**: short

| 方法 | Precision@50 | 耗时 |
|------|--------------|------|
| CAR (KMeans + Adaptive) | 72.0% | 92.8ms |
| CAR (KMeans + Fixed) | 100.0% | 35.8ms |
| Baseline (Dense Only) | 70.0% | 96.3ms |

### 查询 3: "Group and aggregate pandas DataFrame"
- **预期话题**: python
- **查询类型**: long

| 方法 | Precision@50 | 耗时 |
|------|--------------|------|
| CAR (KMeans + Adaptive) | 100.0% | 79.4ms |
| CAR (KMeans + Fixed) | 100.0% | 30.2ms |
| Baseline (Dense Only) | 100.0% | 93.2ms |

### 查询 4: "Reduce Docker image size best practices"
- **预期话题**: docker
- **查询类型**: long

| 方法 | Precision@50 | 耗时 |
|------|--------------|------|
| CAR (KMeans + Adaptive) | 100.0% | 92.4ms |
| CAR (KMeans + Fixed) | 100.0% | 41.6ms |
| Baseline (Dense Only) | 100.0% | 101.4ms |

### 查询 5: "React hooks lifecycle explained"
- **预期话题**: react
- **查询类型**: medium

| 方法 | Precision@50 | 耗时 |
|------|--------------|------|
| CAR (KMeans + Adaptive) | 100.0% | 93.7ms |
| CAR (KMeans + Fixed) | 100.0% | 32.1ms |
| Baseline (Dense Only) | 100.0% | 101.1ms |

## 关键发现

1. **最佳方法**: CAR (KMeans + Fixed)
   - 平均Precision@50: 100.0%
   - 平均耗时: 33.5ms

2. **CAR优势**:
   - 通过聚类预索引，减少计算量
   - 自适应截断避免低质量结果
   - 适合大规模历史消息场景

3. **性能对比**:
   - CAR相比Baseline加速: 1.09x

## 推荐架构

```
用户请求 (1M context)
    ↓
CAR粗筛 (300条 → 50条, ~50ms)
    ↓
LLM精排 (Gemini Flash, ~2s)
    ↓
最终400K模型
```
