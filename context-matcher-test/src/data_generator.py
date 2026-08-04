"""
生成测试数据：从 HuggingFace 下载真实对话，模拟压缩场景
"""
import json
import random
from datasets import load_dataset
from pathlib import Path

def download_real_conversations(num_samples=10):
    """
    从 LMSYS-Chat-1M 下载真实对话数据
    """
    print(f"正在从 LMSYS-Chat-1M 下载 {num_samples} 条真实对话...")
    print("提示：如果网络连接慢，请耐心等待...\n")
    
    try:
        # 使用流式加载，避免下载整个数据集
        from datasets import load_dataset
        
        dataset = load_dataset(
            "lmsys/lmsys-chat-1m",
            split="train",
            streaming=True
        )
        
        conversations = []
        print("开始提取对话...")
        
        for i, item in enumerate(dataset):
            if i >= num_samples:
                break
            
            # 提取对话内容
            conversation = item.get("conversation", [])
            
            # 只保留有足够长度的对话（至少10轮）
            if len(conversation) >= 10:
                conversations.append({
                    "id": f"real_conv_{i}",
                    "model": item.get("model", "unknown"),
                    "language": item.get("language", "unknown"),
                    "messages": conversation,
                    "turn": len(conversation)
                })
                print(f"  ✓ 已加载对话 {len(conversations)}/{num_samples}: "
                      f"{len(conversation)} 轮对话 (模型: {item.get('model', 'unknown')})")
        
        if conversations:
            print(f"\n✓ 成功下载 {len(conversations)} 条真实对话\n")
            return conversations
        else:
            print("\n⚠ 未找到足够长的对话，使用备用方案\n")
            return None
    
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        print("将使用模拟对话数据作为备用方案\n")
        return None

def generate_mock_conversations(num_samples=10):
    """
    生成模拟的真实编程对话
    """
    templates = [
        # 项目A：Express 鉴权系统
        {
            "id": "project_a",
            "project_name": "express-auth-api",
            "framework": "express",
            "files": ["auth.js", "middleware.js", "server.js"],
            "imports": ["express", "jsonwebtoken", "bcrypt"],
            "messages": [
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": "I'm building an Express API with JWT authentication. Here's my current auth.js:\n```javascript\n// auth.js\nconst jwt = require('jsonwebtoken');\nconst bcrypt = require('bcrypt');\n\nconst SECRET = 'my-secret';\n\nfunction login(req, res) {\n  // TODO\n}\n```\nHow do I implement the login function?"},
                {"role": "assistant", "content": "I'll help you implement the login function. Here's a complete implementation:\n\n```javascript\nasync function login(req, res) {\n  const { email, password } = req.body;\n  \n  // Find user in database\n  const user = await User.findOne({ email });\n  if (!user) {\n    return res.status(401).json({ error: 'Invalid credentials' });\n  }\n  \n  // Verify password\n  const valid = await bcrypt.compare(password, user.password);\n  if (!valid) {\n    return res.status(401).json({ error: 'Invalid credentials' });\n  }\n  \n  // Generate token\n  const token = jwt.sign({ userId: user._id }, SECRET, { expiresIn: '24h' });\n  res.json({ token });\n}\n```"},
                {"role": "user", "content": "Great! Now how do I create middleware to protect routes?"},
                {"role": "assistant", "content": "Here's an authentication middleware:\n\n```javascript\n// middleware.js\nfunction authMiddleware(req, res, next) {\n  const token = req.headers.authorization?.split(' ')[1];\n  \n  if (!token) {\n    return res.status(401).json({ error: 'No token provided' });\n  }\n  \n  try {\n    const decoded = jwt.verify(token, SECRET);\n    req.userId = decoded.userId;\n    next();\n  } catch (err) {\n    res.status(401).json({ error: 'Invalid token' });\n  }\n}\n```"},
                {"role": "user", "content": "How do I use this middleware in my routes?"},
            ]
        },
        
        # 项目B：React Dashboard
        {
            "id": "project_b",
            "project_name": "react-dashboard",
            "framework": "react",
            "files": ["Dashboard.jsx", "UserTable.jsx", "api.js"],
            "imports": ["react", "react-router-dom", "axios"],
            "messages": [
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": "I need to build a React dashboard with a user table. Here's my current structure:\n```jsx\n// Dashboard.jsx\nimport React from 'react';\nimport UserTable from './UserTable';\n\nfunction Dashboard() {\n  return <div>Dashboard</div>;\n}\n```\nHow should I fetch and display user data?"},
                {"role": "assistant", "content": "Here's how to fetch and display users:\n\n```jsx\nimport React, { useState, useEffect } from 'react';\nimport axios from 'axios';\nimport UserTable from './UserTable';\n\nfunction Dashboard() {\n  const [users, setUsers] = useState([]);\n  const [loading, setLoading] = useState(true);\n  \n  useEffect(() => {\n    axios.get('/api/users')\n      .then(res => {\n        setUsers(res.data);\n        setLoading(false);\n      });\n  }, []);\n  \n  if (loading) return <div>Loading...</div>;\n  \n  return (\n    <div className=\"dashboard\">\n      <h1>User Dashboard</h1>\n      <UserTable users={users} />\n    </div>\n  );\n}\n```"},
                {"role": "user", "content": "What should the UserTable component look like?"},
            ]
        },
        
        # 项目C：Python 数据处理
        {
            "id": "project_c",
            "project_name": "data-processor",
            "framework": "pandas",
            "files": ["processor.py", "cleaner.py", "main.py"],
            "imports": ["pandas", "numpy", "sklearn"],
            "messages": [
                {"role": "system", "content": "You are a helpful coding assistant."},
                {"role": "user", "content": "I have a CSV with sales data that needs cleaning. Here's my current code:\n```python\n# processor.py\nimport pandas as pd\n\ndf = pd.read_csv('sales.csv')\n# What's next?\n```\nHow do I handle missing values and outliers?"},
                {"role": "assistant", "content": "Here's a complete cleaning pipeline:\n\n```python\nimport pandas as pd\nimport numpy as np\n\ndef clean_data(df):\n    # Handle missing values\n    df = df.dropna(subset=['customer_id', 'amount'])\n    df['date'] = pd.to_datetime(df['date'], errors='coerce')\n    \n    # Remove outliers using IQR\n    Q1 = df['amount'].quantile(0.25)\n    Q3 = df['amount'].quantile(0.75)\n    IQR = Q3 - Q1\n    df = df[(df['amount'] >= Q1 - 1.5*IQR) & (df['amount'] <= Q3 + 1.5*IQR)]\n    \n    return df\n```"},
                {"role": "user", "content": "How do I aggregate this by month and product?"},
            ]
        }
    ]
    
    # 为每个项目生成完整对话（扩展到 40-50 条消息）
    conversations = []
    for template in templates[:num_samples]:
        messages = template["messages"].copy()
        
        # 扩展对话到 40+ 条消息
        follow_ups = [
            "Can you explain that code in more detail?",
            "What if I need to add error handling?",
            "How do I write tests for this?",
            "What about performance optimization?",
            "Can you show me the complete file?",
            "What are the best practices here?",
            "How do I deploy this?",
        ]
        
        for i in range(15):  # 添加更多轮对话
            messages.append({
                "role": "user",
                "content": random.choice(follow_ups) + f" (iteration {i+1})"
            })
            messages.append({
                "role": "assistant",
                "content": f"Here's the answer for iteration {i+1}... [detailed code and explanation]"
            })
        
        conversations.append({
            "id": template["id"],
            "project_name": template["project_name"],
            "framework": template["framework"],
            "files": template["files"],
            "imports": template["imports"],
            "messages": messages,
            "token_estimate": len(json.dumps(messages)) * 0.3  # 粗略估算
        })
    
    return conversations

def compress_conversation(conversation, method="truncate"):
    """
    模拟客户端的4种压缩方式
    """
    messages = conversation["messages"]
    
    if method == "truncate":
        # 只保留最后 10 条
        return messages[-10:]
    
    elif method == "summarize":
        # 前面总结，保留最后 15 条
        project_name = conversation.get('project_name', conversation.get('topic', 'a project'))
        framework = conversation.get('framework', 'various technologies')
        files = conversation.get('files', ['code files'])
        
        summary = {
            "role": "system",
            "content": f"[Previous conversation summary: User was working on {project_name} "
                      f"using {framework}. Discussed {', '.join(files[:2]) if files else 'implementation details'}.]"
        }
        return [messages[0], summary] + messages[-15:]
    
    elif method == "remove_code":
        # 删除代码块，只保留对话
        cleaned = []
        for msg in messages:
            content = msg["content"]
            # 简单移除代码块
            if "```" in content:
                content = content.split("```")[0] + " [code removed]"
            cleaned.append({"role": msg["role"], "content": content})
        return cleaned
    
    elif method == "mixed":
        # 混合：总结 + 删除部分代码 + 保留最近
        project_name = conversation.get('project_name', conversation.get('topic', 'a project'))
        framework = conversation.get('framework', 'various technologies')
        
        summary = {
            "role": "system",
            "content": f"Summary: Working on {project_name} with {framework}."
        }
        recent = messages[-20:]
        # 删除一半的代码
        for i, msg in enumerate(recent):
            if i % 2 == 0 and "```" in msg["content"]:
                recent[i]["content"] = msg["content"].split("```")[0] + " [code omitted]"
        
        return [messages[0], summary] + recent
    
    return messages

def main():
    output_dir = Path("../test_data")
    output_dir.mkdir(exist_ok=True)
    
    # 生成或下载对话数据
    print("生成测试数据...")
    conversations = download_real_conversations(num_samples=3)
    
    # 如果没有成功，使用模拟数据
    if not conversations:
        conversations = generate_mock_conversations(3)
    
    # 保存完整对话
    for conv in conversations:
        conv_id = conv["id"]
        
        # 保存完整版本
        with open(output_dir / f"{conv_id}_full.json", "w", encoding="utf-8") as f:
            json.dump(conv, f, indent=2, ensure_ascii=False)
        
        # 生成4种压缩版本
        compressed_versions = {}
        for method in ["truncate", "summarize", "remove_code", "mixed"]:
            compressed_versions[method] = compress_conversation(conv, method)
        
        with open(output_dir / f"{conv_id}_compressed.json", "w", encoding="utf-8") as f:
            json.dump(compressed_versions, f, indent=2, ensure_ascii=False)
        
        print(f"✓ 生成 {conv_id}: {len(conv['messages'])} 条消息")
        print(f"  压缩版本: truncate={len(compressed_versions['truncate'])}, "
              f"summarize={len(compressed_versions['summarize'])}, "
              f"remove_code={len(compressed_versions['remove_code'])}, "
              f"mixed={len(compressed_versions['mixed'])}")
    
    print(f"\n✓ 数据生成完成！保存在 {output_dir}/")

if __name__ == "__main__":
    main()
