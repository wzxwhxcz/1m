"""
使用公开的真实对话数据集进行测试
替代方案：使用不需要认证的数据集
"""
import json
import random
from pathlib import Path

def download_real_conversations_alternative(num_samples=10):
    """
    使用公开的对话数据集（不需要认证）
    """
    print(f"正在下载真实对话数据...")
    
    try:
        from datasets import load_dataset
        
        # 方案1：使用 OpenAssistant 对话数据集（公开）
        print("尝试使用 OpenAssistant Conversations 数据集...")
        dataset = load_dataset(
            "OpenAssistant/oasst1",
            split="train",
            streaming=True
        )
        
        conversations = []
        conversation_trees = {}  # 用于组装对话树
        
        print("正在提取对话...")
        for i, item in enumerate(dataset):
            if len(conversations) >= num_samples:
                break
            
            # OpenAssistant 数据是树状结构，需要组装
            message_id = item.get("message_id")
            parent_id = item.get("parent_id")
            text = item.get("text", "")
            role = item.get("role", "")
            
            if parent_id is None:
                # 这是对话的起点
                conversation_trees[message_id] = [{
                    "role": "user" if role == "prompter" else "assistant",
                    "content": text
                }]
            elif parent_id in conversation_trees:
                # 添加到现有对话树
                conversation_trees[message_id] = conversation_trees[parent_id] + [{
                    "role": "user" if role == "prompter" else "assistant",
                    "content": text
                }]
                
                # 如果对话足够长，保存它
                if len(conversation_trees[message_id]) >= 10:
                    conversations.append({
                        "id": f"oasst_{len(conversations)}",
                        "messages": conversation_trees[message_id],
                        "source": "OpenAssistant"
                    })
                    print(f"  ✓ 已加载对话 {len(conversations)}/{num_samples}: "
                          f"{len(conversation_trees[message_id])} 轮对话")
        
        if conversations:
            print(f"\n✓ 成功下载 {len(conversations)} 条真实对话\n")
            return conversations
        
        # 方案2：如果上面失败，尝试其他数据集
        print("\n尝试使用 Chatbot Arena 对话数据集...")
        dataset = load_dataset(
            "lmsys/chatbot_arena_conversations",
            split="train",
            streaming=True
        )
        
        conversations = []
        for i, item in enumerate(dataset):
            if i >= num_samples * 10:  # 多取一些，因为会过滤
                break
            
            conv = item.get("conversation_a", [])
            if len(conv) >= 6:  # 至少3轮完整对话
                conversations.append({
                    "id": f"arena_{len(conversations)}",
                    "messages": conv,
                    "source": "Chatbot Arena"
                })
                print(f"  ✓ 已加载对话 {len(conversations)}/{num_samples}: "
                      f"{len(conv)} 条消息")
                
                if len(conversations) >= num_samples:
                    break
        
        if conversations:
            print(f"\n✓ 成功下载 {len(conversations)} 条真实对话\n")
            return conversations
            
    except Exception as e:
        print(f"\n❌ 下载失败: {e}")
        print("网络或数据集可能不可用\n")
    
    return None


def generate_realistic_conversations(num_samples=10):
    """
    生成更真实的模拟对话（基于真实场景）
    """
    print("生成真实场景的模拟对话...")
    
    # 真实的编程问题模板
    real_scenarios = [
        {
            "id": "real_express_auth",
            "topic": "Express JWT Authentication",
            "messages": [
                {"role": "system", "content": "You are a helpful programming assistant."},
                {"role": "user", "content": "I'm building a REST API with Express and need to implement JWT authentication. Where should I start?"},
                {"role": "assistant", "content": "Great! Let's implement JWT authentication step by step. First, you'll need to install the required packages:\n\n```bash\nnpm install jsonwebtoken bcryptjs express-validator\n```\n\nHere's the basic structure:\n\n1. User registration endpoint\n2. Login endpoint that returns a JWT\n3. Middleware to verify the JWT\n4. Protected routes\n\nLet's start with the registration endpoint."},
                {"role": "user", "content": "Okay, can you show me the registration endpoint with password hashing?"},
                {"role": "assistant", "content": "Sure! Here's a secure registration endpoint:\n\n```javascript\nconst bcrypt = require('bcryptjs');\nconst { body, validationResult } = require('express-validator');\n\nrouter.post('/register',\n  [\n    body('email').isEmail(),\n    body('password').isLength({ min: 6 })\n  ],\n  async (req, res) => {\n    const errors = validationResult(req);\n    if (!errors.isEmpty()) {\n      return res.status(400).json({ errors: errors.array() });\n    }\n\n    const { email, password } = req.body;\n\n    try {\n      // Check if user exists\n      let user = await User.findOne({ email });\n      if (user) {\n        return res.status(400).json({ msg: 'User already exists' });\n      }\n\n      // Hash password\n      const salt = await bcrypt.genSalt(10);\n      const hashedPassword = await bcrypt.hash(password, salt);\n\n      // Create user\n      user = new User({\n        email,\n        password: hashedPassword\n      });\n\n      await user.save();\n      res.status(201).json({ msg: 'User created successfully' });\n    } catch (err) {\n      console.error(err.message);\n      res.status(500).send('Server error');\n    }\n  }\n);\n```"},
                {"role": "user", "content": "Great! Now what about the login endpoint that returns the JWT?"},
                {"role": "assistant", "content": "Here's the login endpoint:\n\n```javascript\nconst jwt = require('jsonwebtoken');\n\nrouter.post('/login',\n  [\n    body('email').isEmail(),\n    body('password').exists()\n  ],\n  async (req, res) => {\n    const errors = validationResult(req);\n    if (!errors.isEmpty()) {\n      return res.status(400).json({ errors: errors.array() });\n    }\n\n    const { email, password } = req.body;\n\n    try {\n      // Check if user exists\n      const user = await User.findOne({ email });\n      if (!user) {\n        return res.status(400).json({ msg: 'Invalid credentials' });\n      }\n\n      // Verify password\n      const isMatch = await bcrypt.compare(password, user.password);\n      if (!isMatch) {\n        return res.status(400).json({ msg: 'Invalid credentials' });\n      }\n\n      // Create JWT payload\n      const payload = {\n        user: {\n          id: user.id\n        }\n      };\n\n      // Sign token\n      jwt.sign(\n        payload,\n        process.env.JWT_SECRET,\n        { expiresIn: '1h' },\n        (err, token) => {\n          if (err) throw err;\n          res.json({ token });\n        }\n      );\n    } catch (err) {\n      console.error(err.message);\n      res.status(500).send('Server error');\n    }\n  }\n);\n```\n\nMake sure to set `JWT_SECRET` in your `.env` file!"},
                {"role": "user", "content": "Perfect! Now how do I create the middleware to verify the token?"},
                {"role": "assistant", "content": "Here's the authentication middleware:\n\n```javascript\n// middleware/auth.js\nconst jwt = require('jsonwebtoken');\n\nmodule.exports = function(req, res, next) {\n  // Get token from header\n  const token = req.header('Authorization')?.replace('Bearer ', '');\n\n  // Check if no token\n  if (!token) {\n    return res.status(401).json({ msg: 'No token, authorization denied' });\n  }\n\n  try {\n    // Verify token\n    const decoded = jwt.verify(token, process.env.JWT_SECRET);\n    \n    // Add user from payload\n    req.user = decoded.user;\n    next();\n  } catch (err) {\n    res.status(401).json({ msg: 'Token is not valid' });\n  }\n};\n```\n\nAnd here's how to use it:\n\n```javascript\nconst auth = require('./middleware/auth');\n\n// Protected route\nrouter.get('/profile', auth, async (req, res) => {\n  try {\n    const user = await User.findById(req.user.id).select('-password');\n    res.json(user);\n  } catch (err) {\n    console.error(err.message);\n    res.status(500).send('Server Error');\n  }\n});\n```"},
                {"role": "user", "content": "This is excellent! One more question - how should I handle token refresh?"},
                {"role": "assistant", "content": "Good question! Here's a token refresh implementation:\n\n```javascript\n// In your login endpoint, return both access and refresh tokens\nconst accessToken = jwt.sign(payload, process.env.JWT_SECRET, { expiresIn: '15m' });\nconst refreshToken = jwt.sign(payload, process.env.REFRESH_TOKEN_SECRET, { expiresIn: '7d' });\n\n// Store refresh token in database\nawait user.update({ refreshToken });\n\nres.json({ accessToken, refreshToken });\n\n// Create refresh endpoint\nrouter.post('/refresh', async (req, res) => {\n  const { refreshToken } = req.body;\n  \n  if (!refreshToken) {\n    return res.status(401).json({ msg: 'Refresh token required' });\n  }\n  \n  try {\n    // Verify refresh token\n    const decoded = jwt.verify(refreshToken, process.env.REFRESH_TOKEN_SECRET);\n    \n    // Check if refresh token exists in database\n    const user = await User.findById(decoded.user.id);\n    if (!user || user.refreshToken !== refreshToken) {\n      return res.status(403).json({ msg: 'Invalid refresh token' });\n    }\n    \n    // Generate new access token\n    const payload = { user: { id: user.id } };\n    const newAccessToken = jwt.sign(payload, process.env.JWT_SECRET, { expiresIn: '15m' });\n    \n    res.json({ accessToken: newAccessToken });\n  } catch (err) {\n    res.status(403).json({ msg: 'Invalid refresh token' });\n  }\n});\n```"},
                {"role": "user", "content": "Thank you! Should I also implement a logout endpoint?"},
                {"role": "assistant", "content": "Yes, definitely! Here's a logout endpoint:\n\n```javascript\nrouter.post('/logout', auth, async (req, res) => {\n  try {\n    // Remove refresh token from database\n    await User.findByIdAndUpdate(req.user.id, { refreshToken: null });\n    \n    res.json({ msg: 'Logged out successfully' });\n  } catch (err) {\n    console.error(err.message);\n    res.status(500).send('Server Error');\n  }\n});\n```\n\nFor a more robust solution, you might want to implement a token blacklist using Redis:\n\n```javascript\nconst redis = require('redis');\nconst client = redis.createClient();\n\nrouter.post('/logout', auth, async (req, res) => {\n  const token = req.header('Authorization')?.replace('Bearer ', '');\n  \n  try {\n    // Add token to blacklist with expiry matching token expiry\n    await client.setex(token, 900, 'blacklisted'); // 15 minutes\n    \n    // Remove refresh token from database\n    await User.findByIdAndUpdate(req.user.id, { refreshToken: null });\n    \n    res.json({ msg: 'Logged out successfully' });\n  } catch (err) {\n    console.error(err.message);\n    res.status(500).send('Server Error');\n  }\n});\n```"}
            ]
        },
        # 更多真实场景...
    ]
    
    # 扩展每个场景，添加更多真实的后续问题
    conversations = []
    for scenario in real_scenarios[:num_samples]:
        conv = scenario.copy()
        conversations.append(conv)
        print(f"  ✓ 生成真实场景: {scenario['topic']} ({len(scenario['messages'])} 条消息)")
    
    return conversations


def main():
    output_dir = Path("../test_data_real")
    output_dir.mkdir(exist_ok=True)
    
    print("=" * 60)
    print("使用真实对话数据进行测试")
    print("=" * 60)
    print()
    
    # 尝试下载真实数据
    conversations = download_real_conversations_alternative(num_samples=5)
    
    # 如果下载失败，使用真实场景模拟
    if not conversations or len(conversations) < 3:
        print("使用真实场景的模拟对话...")
        conversations = generate_realistic_conversations(num_samples=3)
    
    if not conversations:
        print("❌ 无法获取对话数据")
        return
    
    # 保存并生成压缩版本
    from data_generator import compress_conversation
    
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
        
        print(f"✓ 保存 {conv_id}: {len(conv['messages'])} 条消息")
        print(f"  压缩版本: truncate={len(compressed_versions['truncate'])}, "
              f"summarize={len(compressed_versions['summarize'])}, "
              f"remove_code={len(compressed_versions['remove_code'])}, "
              f"mixed={len(compressed_versions['mixed'])}")
    
    print(f"\n✓ 真实数据生成完成！保存在 {output_dir}/")
    print(f"\n现在运行: python benchmark_real.py")

if __name__ == "__main__":
    main()
