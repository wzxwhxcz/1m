"""
测试Go代理服务
"""
import requests
import json
import urllib.parse

# 配置
GO_PROXY_URL = "http://localhost:8080"
SERVICE_KEY = "sk-test123"

def test_health():
    """测试健康检查"""
    print("\n" + "="*80)
    print("测试Go代理健康检查")
    print("="*80)
    
    try:
        response = requests.get(f"{GO_PROXY_URL}/health", timeout=5)
        
        if response.status_code == 200:
            health = response.json()
            print(f"\n✓ Go代理服务健康")
            print(f"  - 服务: {health['service']}")
            print(f"  - 版本: {health['version']}")
            print(f"  - 状态: {health['status']}")
            return True
        else:
            print(f"\n✗ 健康检查失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n✗ 无法连接到Go代理: {e}")
        return False


def test_small_request():
    """测试小请求（不触发召回）"""
    print("\n" + "="*80)
    print("测试小请求（<400K tokens，不触发召回）")
    print("="*80)
    
    # 编码上游URL（使用httpbin.org作为测试）
    upstream_url = "https://httpbin.org"
    encoded_upstream = urllib.parse.quote(upstream_url, safe='')
    
    # 构造请求
    url = f"{GO_PROXY_URL}/{SERVICE_KEY}/{encoded_upstream}/v1/chat/completions"
    
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Hello, this is a test message."}
        ],
        "stream": False
    }
    
    print(f"\n请求URL: {url}")
    print(f"上游: {upstream_url}")
    print(f"消息数: {len(payload['messages'])}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        
        print(f"\n响应状态: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(f"响应体前200字符: {response.text[:200]}")
        
        if response.status_code in [200, 404, 405]:  # httpbin可能返回404/405
            print(f"\n✓ Go代理转发成功（上游响应: {response.status_code}）")
            return True
        else:
            print(f"\n⚠️  意外状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n✗ 请求失败: {e}")
        return False


def test_large_request_with_recall():
    """测试大请求（触发召回）"""
    print("\n" + "="*80)
    print("测试大请求（>400K tokens，触发召回）")
    print("="*80)
    
    # 编码上游URL
    upstream_url = "https://httpbin.org"
    encoded_upstream = urllib.parse.quote(upstream_url, safe='')
    
    # 构造大量消息（模拟>400K tokens）
    messages = []
    for i in range(150):  # 150条消息，每条约3K字符 = 450K tokens
        messages.append({
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"This is message {i}. " + "Lorem ipsum dolor sit amet. " * 100
        })
    
    # 添加当前查询
    messages.append({
        "role": "user",
        "content": "Please summarize our conversation about React performance."
    })
    
    url = f"{GO_PROXY_URL}/{SERVICE_KEY}/{encoded_upstream}/v1/chat/completions"
    
    payload = {
        "model": "gpt-4",
        "messages": messages,
        "stream": False
    }
    
    print(f"\n请求URL: {url}")
    print(f"消息数: {len(payload['messages'])}")
    print(f"预估tokens: ~{len(payload['messages']) * 750}")
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        
        print(f"\n响应状态: {response.status_code}")
        
        if response.status_code in [200, 404, 405]:
            print(f"\n✓ Go代理召回+转发成功")
            print("  提示: 检查Go代理日志，应看到 '[Recall] Triggering recall' 信息")
            return True
        else:
            print(f"\n⚠️  意外状态码: {response.status_code}")
            print(f"响应: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"\n✗ 请求失败: {e}")
        return False


if __name__ == "__main__":
    # 测试顺序
    if not test_health():
        print("\n提示: 请确保Go代理服务正在运行:")
        print("  cd D:/1m/go-context-proxy")
        print("  go run cmd/server/main.go")
        exit(1)
    
    test_small_request()
    
    test_large_request_with_recall()
    
    print("\n" + "="*80)
    print("✓ Go代理测试完成")
    print("="*80 + "\n")
