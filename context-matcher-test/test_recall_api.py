"""
测试新的无状态召回API接口
"""
import requests
import json
import time

# API端点
BASE_URL = "http://localhost:8000"

def test_recall_api():
    """测试 /api/v1/recall 接口"""
    
    print("\n" + "="*80)
    print("测试无状态召回API")
    print("="*80)
    
    # 构造测试数据
    messages = [
        {"content": "How do I prevent unnecessary re-renders in React?", "role": "user", "topic": "react"},
        {"content": "What's React.memo and when should I use it?", "role": "user", "topic": "react"},
        {"content": "Can you explain the difference between useMemo and useCallback?", "role": "user", "topic": "react"},
        {"content": "How do I handle form validation in React?", "role": "user", "topic": "react"},
        {"content": "I have a CSV file with user data. How do I load it with pandas?", "role": "user", "topic": "python"},
        {"content": "How do I group and aggregate data in a pandas DataFrame?", "role": "user", "topic": "python"},
        {"content": "What's the best way to handle missing values in my dataset?", "role": "user", "topic": "python"},
        {"content": "How do I create a Dockerfile for my React app?", "role": "user", "topic": "docker"},
        {"content": "How do I reduce my Docker image size?", "role": "user", "topic": "docker"},
        {"content": "What's the best base image for a Node.js application?", "role": "user", "topic": "docker"},
    ]
    
    # 测试查询
    query = "My React component re-renders too often, how can I optimize it?"
    
    # 发送请求
    print(f"\n查询: {query}")
    print(f"消息数: {len(messages)}")
    
    request_data = {
        "messages": messages,
        "query": query,
        "k": 5,
        "algorithm": "car",
        "n_clusters": 3
    }
    
    start = time.time()
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/recall",
            json=request_data,
            timeout=30
        )
        latency = (time.time() - start) * 1000
        
        if response.status_code == 200:
            result = response.json()
            
            print(f"\n✓ 请求成功")
            print(f"  - 原始消息数: {result['original_count']}")
            print(f"  - 召回消息数: {result['recalled_count']}")
            print(f"  - 延迟: {result['latency_ms']:.2f}ms")
            print(f"  - 算法: {result['algorithm_used']}")
            print(f"  - 缓存命中率: {result['cache_hit_rate']:.2%}")
            print(f"  - 总耗时: {latency:.2f}ms")
            
            print(f"\n召回的消息:")
            for i, msg in enumerate(result['recalled_messages'], 1):
                print(f"  {i}. [相似度: {msg['similarity']:.3f}] {msg['content'][:60]}...")
            
            # 验证召回质量
            recalled_topics = [msg.get('topic') for msg in result['recalled_messages']]
            react_count = recalled_topics.count('react')
            print(f"\n召回质量:")
            print(f"  - React相关: {react_count}/{len(result['recalled_messages'])} ({react_count/len(result['recalled_messages'])*100:.1f}%)")
            
            return True
        else:
            print(f"\n✗ 请求失败: {response.status_code}")
            print(f"  错误: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n✗ 异常: {e}")
        return False


def test_dense_algorithm():
    """测试Dense算法"""
    
    print("\n" + "="*80)
    print("测试Dense算法")
    print("="*80)
    
    messages = [
        {"content": "React performance optimization", "role": "user"},
        {"content": "Python data processing", "role": "user"},
        {"content": "Docker containerization", "role": "user"},
    ]
    
    request_data = {
        "messages": messages,
        "query": "How to optimize React performance?",
        "k": 2,
        "algorithm": "dense"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/recall",
            json=request_data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✓ Dense算法成功")
            print(f"  - 延迟: {result['latency_ms']:.2f}ms")
            print(f"  - 召回数: {result['recalled_count']}")
            return True
        else:
            print(f"\n✗ Dense算法失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n✗ 异常: {e}")
        return False


def test_health():
    """测试健康检查"""
    
    print("\n" + "="*80)
    print("健康检查")
    print("="*80)
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        
        if response.status_code == 200:
            health = response.json()
            print(f"\n✓ 服务健康")
            print(f"  - 状态: {health['status']}")
            print(f"  - 运行时间: {health['uptime_seconds']:.1f}秒")
            print(f"  - 总请求数: {health['total_requests']}")
            print(f"  - 平均延迟: {health['avg_latency_ms']:.2f}ms")
            print(f"  - 缓存命中率: {health['cache_hit_rate']:.2%}")
            return True
        else:
            print(f"\n✗ 服务异常: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n✗ 无法连接到服务: {e}")
        print(f"\n提示: 请先启动服务器:")
        print(f"  cd D:/1m/context-matcher-test")
        print(f"  python -m uvicorn src.api_server:app --host 0.0.0.0 --port 8000")
        return False


if __name__ == "__main__":
    # 测试顺序
    if not test_health():
        exit(1)
    
    if not test_recall_api():
        exit(1)
    
    if not test_dense_algorithm():
        exit(1)
    
    print("\n" + "="*80)
    print("✓ 所有测试通过")
    print("="*80 + "\n")
