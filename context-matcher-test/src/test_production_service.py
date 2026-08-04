"""
测试生产服务
验证异步处理、缓存效果、监控指标
"""
import asyncio
import time
from production_service import ProductionContextService, CacheBackend


async def test_production_service():
    """完整的生产服务测试"""
    
    print("="*80)
    print("生产服务完整测试")
    print("="*80)
    
    # 1. 初始化服务
    print("\n[1] 初始化服务...")
    service = ProductionContextService(
        cache_backend=CacheBackend.MEMORY,
        cache_ttl=3600,
        enable_monitoring=True
    )
    await service.initialize()
    
    # 2. 生成测试数据
    print("\n[2] 生成测试数据 (300条消息)...")
    messages = []
    
    # React消息 (120条)
    for i in range(120):
        messages.append({
            "content": f"React development question {i}: How to optimize component rendering and manage state effectively?",
            "topic": "react",
            "role": "user"
        })
    
    # Python消息 (80条)
    for i in range(80):
        messages.append({
            "content": f"Python coding question {i}: How to handle async/await and data processing with pandas?",
            "topic": "python",
            "role": "user"
        })
    
    # Docker消息 (60条)
    for i in range(60):
        messages.append({
            "content": f"Docker deployment question {i}: How to optimize image size and manage containers?",
            "topic": "docker",
            "role": "user"
        })
    
    # SQL消息 (40条)
    for i in range(40):
        messages.append({
            "content": f"SQL database question {i}: How to optimize queries and design database schema?",
            "topic": "sql",
            "role": "user"
        })
    
    print(f"✓ 生成 {len(messages)} 条消息")
    
    # 3. 构建聚类（测试异步处理）
    print("\n[3] 构建聚类索引（异步）...")
    await service.build_clusters_async(messages, n_clusters=10)
    
    # 4. 第一次查询（缓存未命中）
    print("\n[4] 第一次查询（缓存未命中）...")
    query1 = "How can I optimize React component rendering performance?"
    results1, latency1 = await service.car_retrieval_async(query1, messages, k=50)
    print(f"✓ 召回 {len(results1)} 条, 耗时 {latency1:.1f}ms")
    
    # 5. 第二次相同查询（缓存命中）
    print("\n[5] 第二次相同查询（缓存命中）...")
    results2, latency2 = await service.car_retrieval_async(query1, messages, k=50)
    print(f"✓ 召回 {len(results2)} 条, 耗时 {latency2:.1f}ms")
    print(f"✓ 加速比: {latency1 / latency2:.1f}x ({latency1:.1f}ms → {latency2:.1f}ms)")
    
    # 6. 多次不同查询（测试缓存效果）
    print("\n[6] 执行10次不同查询（测试缓存效果）...")
    queries = [
        "How to use React hooks effectively?",
        "What's the best way to manage state in React?",
        "How do I handle async operations in Python?",
        "How to optimize Docker image size?",
        "What are SQL join types?",
        "How to prevent unnecessary re-renders in React?",
        "How to use pandas for data processing?",
        "What's docker-compose and how to use it?",
        "How to design database schema?",
        "How to implement custom React hooks?"
    ]
    
    for i, query in enumerate(queries, 1):
        results, latency = await service.car_retrieval_async(query, messages, k=50)
        print(f"  查询 {i}: 耗时 {latency:.1f}ms, 召回 {len(results)} 条")
        await asyncio.sleep(0.1)  # 模拟真实间隔
    
    # 7. 重复查询（测试缓存命中率）
    print("\n[7] 重复前5个查询（测试缓存命中率）...")
    for i, query in enumerate(queries[:5], 1):
        results, latency = await service.car_retrieval_async(query, messages, k=50)
        print(f"  重复查询 {i}: 耗时 {latency:.1f}ms ← 缓存加速")
    
    # 8. 获取健康状态
    print("\n[8] 健康状态:")
    print("-" * 80)
    health = service.get_health()
    print(f"  状态: {health['status']}")
    print(f"  运行时间: {health['uptime_seconds']:.1f}秒")
    print(f"  总请求数: {health['total_requests']}")
    print(f"  错误率: {health['error_rate']*100:.2f}%")
    print(f"  平均延迟: {health['avg_latency_ms']:.1f}ms")
    print(f"  缓存命中率: {health['cache_hit_rate']*100:.1f}%")
    
    # 9. 获取监控指标
    print("\n[9] 监控指标（最近60秒）:")
    print("-" * 80)
    metrics = service.get_metrics(window_seconds=60)
    print(f"  请求数: {metrics['request_count']}")
    print(f"  平均延迟: {metrics['avg_latency_ms']:.1f}ms")
    print(f"  P95延迟: {metrics['p95_latency_ms']:.1f}ms")
    print(f"  P99延迟: {metrics['p99_latency_ms']:.1f}ms")
    print(f"  错误数: {metrics['error_count']}")
    print(f"  缓存命中率: {metrics['cache_hit_rate']*100:.1f}%")
    
    # 10. 获取缓存统计
    print("\n[10] 缓存统计:")
    print("-" * 80)
    cache_stats = await service.get_cache_stats()
    print(f"  后端类型: {cache_stats['backend']}")
    print(f"  缓存键数: {cache_stats.get('active_keys', cache_stats.get('total_keys'))}")
    
    # 11. 性能压测（并发查询）
    print("\n[11] 性能压测（20个并发查询）...")
    start = time.time()
    
    concurrent_queries = [
        service.car_retrieval_async(queries[i % len(queries)], messages, k=50)
        for i in range(20)
    ]
    
    results_list = await asyncio.gather(*concurrent_queries)
    
    elapsed = time.time() - start
    avg_latency = sum(r[1] for r in results_list) / len(results_list)
    
    print(f"✓ 完成20个并发查询")
    print(f"  总耗时: {elapsed*1000:.1f}ms")
    print(f"  平均延迟: {avg_latency:.1f}ms")
    print(f"  吞吐量: {20 / elapsed:.1f} QPS")
    
    # 12. 最终健康检查
    print("\n[12] 最终健康状态:")
    print("-" * 80)
    final_health = service.get_health()
    print(f"  状态: {final_health['status']}")
    print(f"  总请求数: {final_health['total_requests']}")
    print(f"  错误率: {final_health['error_rate']*100:.2f}%")
    print(f"  平均延迟: {final_health['avg_latency_ms']:.1f}ms")
    print(f"  缓存命中率: {final_health['cache_hit_rate']*100:.1f}%")
    
    # 评估健康状态
    if final_health['status'] == 'healthy':
        print(f"\n✅ 服务健康状态: 优秀")
    elif final_health['status'] == 'degraded':
        print(f"\n⚠️  服务健康状态: 降级")
    else:
        print(f"\n❌ 服务健康状态: 不健康")
    
    # 13. 关闭服务
    print("\n[13] 关闭服务...")
    await service.shutdown()
    
    # 14. 测试结论
    print("\n" + "="*80)
    print("测试结论")
    print("="*80)
    
    # 计算缓存效果
    speedup = latency1 / latency2
    cache_hit_rate = final_health['cache_hit_rate']
    
    print(f"\n✅ 缓存加速:")
    print(f"   首次查询: {latency1:.1f}ms")
    print(f"   缓存查询: {latency2:.1f}ms")
    print(f"   加速比: {speedup:.1f}x")
    
    print(f"\n✅ 整体性能:")
    print(f"   总请求数: {final_health['total_requests']}")
    print(f"   缓存命中率: {cache_hit_rate*100:.1f}%")
    print(f"   平均延迟: {final_health['avg_latency_ms']:.1f}ms")
    print(f"   错误率: {final_health['error_rate']*100:.2f}%")
    
    print(f"\n✅ 并发能力:")
    print(f"   20个并发查询: {elapsed*1000:.1f}ms")
    print(f"   吞吐量: {20 / elapsed:.1f} QPS")
    
    # 评分
    score = 0
    if cache_hit_rate > 0.5:
        score += 25
        print(f"\n✅ 缓存命中率 > 50%: 通过")
    else:
        print(f"\n⚠️  缓存命中率 < 50%: 需要优化")
    
    if final_health['avg_latency_ms'] < 200:
        score += 25
        print(f"✅ 平均延迟 < 200ms: 通过")
    else:
        print(f"⚠️  平均延迟 > 200ms: 需要优化")
    
    if final_health['error_rate'] == 0:
        score += 25
        print(f"✅ 错误率 = 0%: 通过")
    else:
        print(f"⚠️  错误率 > 0%: 需要排查")
    
    if 20 / elapsed > 10:
        score += 25
        print(f"✅ 吞吐量 > 10 QPS: 通过")
    else:
        print(f"⚠️  吞吐量 < 10 QPS: 需要优化")
    
    print(f"\n{'='*80}")
    print(f"总体评分: {score}/100")
    
    if score >= 90:
        print(f"评级: ⭐⭐⭐⭐⭐ 优秀，可以部署到生产环境")
    elif score >= 75:
        print(f"评级: ⭐⭐⭐⭐ 良好，建议进一步优化后部署")
    elif score >= 60:
        print(f"评级: ⭐⭐⭐ 中等，需要优化")
    else:
        print(f"评级: ⭐⭐ 较差，不建议部署")
    
    print(f"{'='*80}\n")


if __name__ == "__main__":
    asyncio.run(test_production_service())
