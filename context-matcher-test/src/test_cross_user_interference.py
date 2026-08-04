"""
跨用户干扰测试：测试是否会将用户A的压缩会话误匹配到用户B的相似会话

场景：
- 用户A和用户B都在讨论 React Hooks
- 用户A和用户C都在讨论 Python async/await
- 用户D和用户E都在讨论 JWT 认证

测试目标：
- 用户A的压缩会话应该匹配到用户A的完整会话，而不是用户B的
"""
import json
from pathlib import Path
from matcher import SessionMatcher
import time

def generate_similar_conversations():
    """生成高度相似但属于不同用户的对话"""
    
    # 场景1：两个用户都在学习 React Hooks
    user_a_react = {
        "user_id": "alice",
        "session_id": "alice_react_hooks_20240804",
        "messages": [
            {"role": "user", "content": "What's the difference between useState and useReducer in React?"},
            {"role": "assistant", "content": "useState is for simple state management, while useReducer is better for complex state logic with multiple sub-values or when the next state depends on the previous one. Let me show you an example:\n\n```jsx\n// useState example\nconst [count, setCount] = useState(0);\n\n// useReducer example\nconst [state, dispatch] = useReducer(reducer, initialState);\n```"},
            {"role": "user", "content": "When should I use useEffect?"},
            {"role": "assistant", "content": "useEffect is for side effects like data fetching, subscriptions, or manually changing the DOM. It runs after render and can clean up:\n\n```jsx\nuseEffect(() => {\n  fetchData();\n  return () => cleanup();\n}, [dependencies]);\n```"},
            {"role": "user", "content": "Can I use multiple useState hooks in one component?"},
            {"role": "assistant", "content": "Yes! You can use as many useState hooks as you need:\n\n```jsx\nconst [name, setName] = useState('');\nconst [age, setAge] = useState(0);\nconst [email, setEmail] = useState('');\n```"},
            {"role": "user", "content": "What are the rules of hooks?"},
            {"role": "assistant", "content": "Two main rules:\n1. Only call hooks at the top level (not in loops, conditions, or nested functions)\n2. Only call hooks from React function components or custom hooks\n\nThis ensures hooks are called in the same order every render."},
            {"role": "user", "content": "How do I create a custom hook?"},
            {"role": "assistant", "content": "Custom hooks are functions that start with 'use' and can call other hooks:\n\n```jsx\nfunction useLocalStorage(key, initialValue) {\n  const [value, setValue] = useState(() => {\n    return localStorage.getItem(key) || initialValue;\n  });\n  \n  useEffect(() => {\n    localStorage.setItem(key, value);\n  }, [key, value]);\n  \n  return [value, setValue];\n}\n```"}
        ]
    }
    
    user_b_react = {
        "user_id": "bob",
        "session_id": "bob_react_hooks_20240804",
        "messages": [
            {"role": "user", "content": "I'm confused about useState vs useReducer. Which one should I use?"},
            {"role": "assistant", "content": "Choose useState for simple values, useReducer for complex state with multiple fields. Here's a comparison:\n\n```jsx\n// Simple: useState\nconst [isOpen, setIsOpen] = useState(false);\n\n// Complex: useReducer\nfunction reducer(state, action) {\n  switch (action.type) {\n    case 'increment': return { count: state.count + 1 };\n    case 'decrement': return { count: state.count - 1 };\n  }\n}\nconst [state, dispatch] = useReducer(reducer, { count: 0 });\n```"},
            {"role": "user", "content": "What's useEffect for?"},
            {"role": "assistant", "content": "useEffect handles side effects - API calls, timers, subscriptions. It's like componentDidMount + componentDidUpdate + componentWillUnmount:\n\n```jsx\nuseEffect(() => {\n  const timer = setInterval(() => console.log('tick'), 1000);\n  return () => clearInterval(timer);\n}, []);\n```"},
            {"role": "user", "content": "Can I have multiple useState calls?"},
            {"role": "assistant", "content": "Absolutely! Split state into multiple useState calls:\n\n```jsx\nfunction UserForm() {\n  const [firstName, setFirstName] = useState('');\n  const [lastName, setLastName] = useState('');\n  const [phone, setPhone] = useState('');\n}\n```"},
            {"role": "user", "content": "What are hooks rules?"},
            {"role": "assistant", "content": "Follow these rules:\n1. Always call hooks at the top level\n2. Only call from React functions (components or custom hooks)\n\nReact relies on call order to match state with hooks."},
            {"role": "user", "content": "How to make custom hooks?"},
            {"role": "assistant", "content": "Prefix with 'use' and compose existing hooks:\n\n```jsx\nfunction useFetch(url) {\n  const [data, setData] = useState(null);\n  const [loading, setLoading] = useState(true);\n  \n  useEffect(() => {\n    fetch(url)\n      .then(res => res.json())\n      .then(data => {\n        setData(data);\n        setLoading(false);\n      });\n  }, [url]);\n  \n  return { data, loading };\n}\n```"}
        ]
    }
    
    # 场景2：两个用户都在学习 Python async/await
    user_a_python = {
        "user_id": "alice",
        "session_id": "alice_python_async_20240804",
        "messages": [
            {"role": "user", "content": "What is async/await in Python?"},
            {"role": "assistant", "content": "async/await enables concurrent programming. async defines a coroutine, await pauses until it completes:\n\n```python\nimport asyncio\n\nasync def fetch_data():\n    await asyncio.sleep(1)\n    return 'data'\n\nasync def main():\n    result = await fetch_data()\n    print(result)\n\nasyncio.run(main())\n```"},
            {"role": "user", "content": "How do I run multiple async functions at once?"},
            {"role": "assistant", "content": "Use asyncio.gather() or create_task():\n\n```python\n# gather\nresults = await asyncio.gather(\n    fetch_user(),\n    fetch_posts(),\n    fetch_comments()\n)\n\n# create_task\ntask1 = asyncio.create_task(fetch_user())\ntask2 = asyncio.create_task(fetch_posts())\nresult1 = await task1\nresult2 = await task2\n```"},
            {"role": "user", "content": "Can I use regular functions with async?"},
            {"role": "assistant", "content": "You can call sync functions from async, but not await them. For blocking I/O, use run_in_executor:\n\n```python\nimport asyncio\nfrom concurrent.futures import ThreadPoolExecutor\n\ndef blocking_io():\n    time.sleep(1)\n    return 'done'\n\nasync def main():\n    loop = asyncio.get_event_loop()\n    result = await loop.run_in_executor(None, blocking_io)\n```"}
        ]
    }
    
    user_c_python = {
        "user_id": "charlie",
        "session_id": "charlie_python_async_20240804",
        "messages": [
            {"role": "user", "content": "Explain async/await in Python"},
            {"role": "assistant", "content": "async/await allows concurrent execution without threads. async marks a coroutine function, await suspends execution:\n\n```python\nimport asyncio\n\nasync def download_file(url):\n    await asyncio.sleep(2)  # simulate download\n    return f'Downloaded {url}'\n\nasync def main():\n    file = await download_file('https://example.com')\n    print(file)\n\nasyncio.run(main())\n```"},
            {"role": "user", "content": "How to run async functions concurrently?"},
            {"role": "assistant", "content": "Use asyncio.gather() for parallel execution:\n\n```python\nasync def task1():\n    await asyncio.sleep(1)\n    return 'Task 1'\n\nasync def task2():\n    await asyncio.sleep(2)\n    return 'Task 2'\n\nasync def main():\n    # Run concurrently\n    results = await asyncio.gather(task1(), task2())\n    print(results)  # ['Task 1', 'Task 2']\n```"},
            {"role": "user", "content": "Can async call sync functions?"},
            {"role": "assistant", "content": "Yes, but blocking sync functions should use run_in_executor to avoid blocking the event loop:\n\n```python\nimport time\nimport asyncio\n\ndef sync_function():\n    time.sleep(1)\n    return 'result'\n\nasync def async_function():\n    loop = asyncio.get_running_loop()\n    result = await loop.run_in_executor(None, sync_function)\n    return result\n```"}
        ]
    }
    
    # 场景3：两个用户都在学习 JWT 认证
    user_d_jwt = {
        "user_id": "dave",
        "session_id": "dave_jwt_auth_20240804",
        "messages": [
            {"role": "user", "content": "How does JWT authentication work?"},
            {"role": "assistant", "content": "JWT (JSON Web Token) has three parts: Header, Payload, Signature. Server signs tokens, client stores them:\n\n```javascript\n// Server generates token\nconst token = jwt.sign(\n  { userId: 123, role: 'admin' },\n  SECRET_KEY,\n  { expiresIn: '1h' }\n);\n\n// Client sends in header\nAuthorization: Bearer eyJhbGc...\n```"},
            {"role": "user", "content": "Where should I store JWT tokens?"},
            {"role": "assistant", "content": "Options:\n1. localStorage: Easy but vulnerable to XSS\n2. httpOnly cookie: Safer, immune to XSS\n3. sessionStorage: Cleared when tab closes\n\nBest practice: httpOnly cookie with SameSite=Strict"},
            {"role": "user", "content": "How to refresh expired tokens?"},
            {"role": "assistant", "content": "Use refresh tokens:\n\n```javascript\n// Initial login\nconst accessToken = jwt.sign(payload, SECRET, { expiresIn: '15m' });\nconst refreshToken = jwt.sign(payload, REFRESH_SECRET, { expiresIn: '7d' });\n\n// Refresh endpoint\napp.post('/refresh', (req, res) => {\n  const { refreshToken } = req.body;\n  jwt.verify(refreshToken, REFRESH_SECRET, (err, decoded) => {\n    if (err) return res.status(401).send('Invalid token');\n    const newAccessToken = jwt.sign({ userId: decoded.userId }, SECRET, { expiresIn: '15m' });\n    res.json({ accessToken: newAccessToken });\n  });\n});\n```"}
        ]
    }
    
    user_e_jwt = {
        "user_id": "eve",
        "session_id": "eve_jwt_auth_20240804",
        "messages": [
            {"role": "user", "content": "What is JWT and how does it work?"},
            {"role": "assistant", "content": "JWT consists of Header.Payload.Signature encoded in Base64. Server creates signed tokens for authenticated users:\n\n```javascript\nconst jwt = require('jsonwebtoken');\n\n// Sign token\nconst token = jwt.sign(\n  { id: user.id, email: user.email },\n  process.env.JWT_SECRET,\n  { expiresIn: '2h' }\n);\n\n// Verify token\njwt.verify(token, process.env.JWT_SECRET, (err, decoded) => {\n  if (err) return res.status(403).send('Invalid token');\n  req.user = decoded;\n  next();\n});\n```"},
            {"role": "user", "content": "Where to store JWT on client side?"},
            {"role": "assistant", "content": "Storage options:\n- localStorage: Convenient but XSS risk\n- httpOnly cookie: Secure, not accessible via JS\n- sessionStorage: Lost on tab close\n\nRecommendation: httpOnly cookie with Secure and SameSite flags"},
            {"role": "user", "content": "How to handle token expiration?"},
            {"role": "assistant", "content": "Implement refresh token pattern:\n\n```javascript\n// Login returns both tokens\nres.json({\n  accessToken: jwt.sign(user, SECRET, { expiresIn: '15m' }),\n  refreshToken: jwt.sign(user, REFRESH_SECRET, { expiresIn: '7d' })\n});\n\n// Refresh endpoint\napp.post('/token/refresh', (req, res) => {\n  const { refreshToken } = req.cookies;\n  if (!refreshToken) return res.sendStatus(401);\n  \n  jwt.verify(refreshToken, REFRESH_SECRET, (err, user) => {\n    if (err) return res.sendStatus(403);\n    const accessToken = jwt.sign({ id: user.id }, SECRET, { expiresIn: '15m' });\n    res.json({ accessToken });\n  });\n});\n```"}
        ]
    }
    
    return [
        user_a_react, user_b_react,
        user_a_python, user_c_python,
        user_d_jwt, user_e_jwt
    ]

def compress_conversation(messages):
    """模拟 LLM 压缩（保留20%）"""
    # 提取关键信息
    topics = []
    keywords = set()
    
    for msg in messages:
        content = msg.get("content", "")
        # 提取关键词
        if "React" in content or "useState" in content or "useEffect" in content:
            topics.append("React Hooks")
            keywords.update(["React", "Hooks", "useState", "useEffect"])
        if "async" in content or "await" in content or "asyncio" in content:
            topics.append("Python async/await")
            keywords.update(["Python", "async", "await", "asyncio"])
        if "JWT" in content or "token" in content or "authentication" in content:
            topics.append("JWT authentication")
            keywords.update(["JWT", "token", "authentication"])
    
    # 生成总结
    summary_msg = {
        "role": "system",
        "content": f"[Conversation Summary]\n\nTechnologies discussed: {', '.join(set(topics))}\n\nKey keywords: {', '.join(keywords)}\n\nThe user asked {len([m for m in messages if m['role'] == 'user'])} questions."
    }
    
    # 保留最后2条消息
    recent = messages[-2:]
    
    return [summary_msg] + recent

def test_cross_user_interference():
    """测试跨用户干扰"""
    print("=" * 80)
    print("跨用户干扰测试：相似主题的不同用户会话")
    print("=" * 80)
    print()
    
    conversations = generate_similar_conversations()
    
    print(f"生成了 {len(conversations)} 个相似对话：")
    for conv in conversations:
        print(f"  - {conv['user_id']}: {conv['session_id']}")
    print()
    
    # 测试场景
    test_scenarios = [
        {
            "name": "场景1: Alice的React压缩会话 vs Bob的React完整会话（相同主题）",
            "target_user": "alice",
            "target_session": "alice_react_hooks_20240804",
            "interference_user": "bob",
            "interference_session": "bob_react_hooks_20240804",
            "description": "两个用户都在学习React Hooks，讨论useState、useEffect等相同话题"
        },
        {
            "name": "场景2: Alice的Python压缩会话 vs Charlie的Python完整会话（相同主题）",
            "target_user": "alice",
            "target_session": "alice_python_async_20240804",
            "interference_user": "charlie",
            "interference_session": "charlie_python_async_20240804",
            "description": "两个用户都在学习Python async/await，讨论asyncio.gather等相同话题"
        },
        {
            "name": "场景3: Dave的JWT压缩会话 vs Eve的JWT完整会话（相同主题）",
            "target_user": "dave",
            "target_session": "dave_jwt_auth_20240804",
            "interference_user": "eve",
            "interference_session": "eve_jwt_auth_20240804",
            "description": "两个用户都在学习JWT认证，讨论token存储、refresh等相同话题"
        }
    ]
    
    results = {
        "time_window": {"correct": 0, "wrong": 0, "details": []},
        "anchor": {"correct": 0, "wrong": 0, "details": []},
        "features": {"correct": 0, "wrong": 0, "details": []},
        "vector": {"correct": 0, "wrong": 0, "details": []},
        "hybrid": {"correct": 0, "wrong": 0, "details": []}
    }
    
    for scenario in test_scenarios:
        print(f"\n{'='*80}")
        print(scenario["name"])
        print(scenario["description"])
        print(f"{'='*80}")
        
        # 准备数据
        target_conv = next(c for c in conversations if c["session_id"] == scenario["target_session"])
        interference_conv = next(c for c in conversations if c["session_id"] == scenario["interference_session"])
        
        # 压缩目标会话
        compressed_messages = compress_conversation(target_conv["messages"])
        
        # 创建matcher并存储两个会话
        # 注意：这里故意存储到同一个user_id下，模拟一个用户有多个相似主题的会话
        matcher = SessionMatcher()
        shared_user_id = "test_user"  # 用同一个user_id来测试是否会混淆
        matcher.store_session(shared_user_id, target_conv["session_id"], target_conv["messages"])
        matcher.store_session(shared_user_id, interference_conv["session_id"], interference_conv["messages"])
        
        print(f"\n目标会话: {target_conv['session_id']}")
        print(f"  原始用户: {target_conv['user_id']}")
        print(f"  完整消息: {len(target_conv['messages'])} 条")
        print(f"  压缩消息: {len(compressed_messages)} 条")
        print(f"\n干扰会话: {interference_conv['session_id']}")
        print(f"  原始用户: {interference_conv['user_id']}")
        print(f"  完整消息: {len(interference_conv['messages'])} 条")
        print(f"\n⚠️  关键：两个会话现在都属于同一个user_id='{shared_user_id}'")
        print(f"     测试能否区分相同用户下的相似主题会话")
        print()
        
        # 测试5种策略
        strategies = {
            "time_window": matcher.match_by_time_window,
            "anchor": matcher.match_by_anchor,
            "features": matcher.match_by_features,
            "vector": matcher.match_by_vector,
            "hybrid": matcher.match_by_hybrid
        }
        
        print(f"{'策略':<15} {'匹配结果':<30} {'分数':<8} {'状态'}")
        print("-" * 80)
        
        for strategy_name, strategy_func in strategies.items():
            matched_id, score = strategy_func(shared_user_id, compressed_messages)
            
            if matched_id == target_conv["session_id"]:
                status = "✓ 正确"
                results[strategy_name]["correct"] += 1
            elif matched_id == interference_conv["session_id"]:
                status = "✗ 误匹配到干扰会话"
                results[strategy_name]["wrong"] += 1
            else:
                status = f"? 未知匹配: {matched_id}"
                results[strategy_name]["wrong"] += 1
            
            results[strategy_name]["details"].append({
                "scenario": scenario["name"],
                "matched": matched_id,
                "expected": target_conv["session_id"],
                "score": score,
                "correct": matched_id == target_conv["session_id"]
            })
            
            print(f"{strategy_name:<15} {matched_id or 'None':<30} {score:.4f}   {status}")
    
    # 输出最终结果
    print("\n\n" + "=" * 80)
    print("跨用户干扰测试 - 最终结果")
    print("=" * 80)
    print()
    print(f"{'策略':<15} {'正确匹配':<12} {'误匹配':<12} {'准确率':<12} {'评级'}")
    print("-" * 80)
    
    for strategy_name, stats in results.items():
        total = stats["correct"] + stats["wrong"]
        accuracy = stats["correct"] / total * 100 if total > 0 else 0
        
        if accuracy >= 95:
            rating = "🏆 优秀"
        elif accuracy >= 80:
            rating = "✅ 良好"
        elif accuracy >= 60:
            rating = "⚠️  一般"
        else:
            rating = "❌ 较差"
        
        print(f"{strategy_name:<15} {stats['correct']}/{total:<10} {stats['wrong']}/{total:<10} {accuracy:>6.1f}%      {rating}")
    
    # 详细分析
    print("\n\n" + "=" * 80)
    print("详细分析：为什么会误匹配（或不会）")
    print("=" * 80)
    
    for strategy_name, stats in results.items():
        print(f"\n{'='*80}")
        print(f"{strategy_name.upper()} 策略")
        print(f"{'='*80}")
        
        wrong_cases = [d for d in stats["details"] if not d["correct"]]
        
        if not wrong_cases:
            print("  ✓ 所有测试都正确匹配，没有误匹配到其他用户的会话")
        else:
            print(f"  ✗ 发现 {len(wrong_cases)} 个误匹配案例：")
            for case in wrong_cases:
                print(f"    - {case['scenario']}")
                print(f"      期望: {case['expected']}")
                print(f"      实际: {case['matched']}")
                print(f"      分数: {case['score']:.4f}")
                print()
    
    return results

if __name__ == "__main__":
    results = test_cross_user_interference()
