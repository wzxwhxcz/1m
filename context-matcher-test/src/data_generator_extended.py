"""
扩展真实对话场景，生成更多测试数据
"""
import json
from pathlib import Path

# 真实的编程对话场景
REAL_CONVERSATIONS = [
    {
        "id": "react_hooks_state",
        "topic": "React Hooks useState",
        "messages": [
            {"role": "system", "content": "You are a helpful programming assistant."},
            {"role": "user", "content": "I'm confused about React useState. When should I use multiple useState vs one useState with an object?"},
            {"role": "assistant", "content": "Great question! Here are the guidelines:\n\n**Use multiple useState when:**\n- Values are independent\n- You update them separately\n- Simple primitive values\n\n```jsx\nconst [name, setName] = useState('');\nconst [age, setAge] = useState(0);\nconst [email, setEmail] = useState('');\n```\n\n**Use single useState with object when:**\n- Values are related\n- Often updated together\n- Represent a single entity\n\n```jsx\nconst [user, setUser] = useState({\n  name: '',\n  age: 0,\n  email: ''\n});\n```"},
            {"role": "user", "content": "Okay, but if I use an object, how do I update just one field?"},
            {"role": "assistant", "content": "You need to use the spread operator to preserve other fields:\n\n```jsx\n// ❌ Wrong - overwrites entire object\nsetUser({ name: 'John' });\n\n// ✅ Correct - merges with existing state\nsetUser(prev => ({\n  ...prev,\n  name: 'John'\n}));\n\n// Or with multiple fields\nsetUser(prev => ({\n  ...prev,\n  name: 'John',\n  age: 30\n}));\n```\n\nAlways use the functional update form when the new state depends on the previous state!"},
            {"role": "user", "content": "What about arrays? How do I add an item to an array in state?"},
            {"role": "assistant", "content": "Here are the common array operations:\n\n```jsx\nconst [items, setItems] = useState([]);\n\n// Add item to end\nsetItems(prev => [...prev, newItem]);\n\n// Add item to beginning\nsetItems(prev => [newItem, ...prev]);\n\n// Remove item by id\nsetItems(prev => prev.filter(item => item.id !== idToRemove));\n\n// Update item\nsetItems(prev => prev.map(item => \n  item.id === targetId \n    ? { ...item, field: newValue }\n    : item\n));\n\n// Replace entire array\nsetItems(newArray);\n```\n\nNever mutate state directly with `.push()`, `.splice()`, etc!"},
            {"role": "user", "content": "Why can't I mutate state directly?"},
            {"role": "assistant", "content": "React uses shallow comparison to detect changes. If you mutate state directly:\n\n```jsx\n// ❌ This won't trigger re-render!\nconst [items, setItems] = useState([1, 2, 3]);\nitems.push(4);\nsetItems(items); // Same reference!\n```\n\nReact sees the same array reference and thinks nothing changed, so it doesn't re-render.\n\n```jsx\n// ✅ This creates new reference\nsetItems([...items, 4]); // New array!\n```\n\nAlways create a new array/object when updating state."},
            {"role": "user", "content": "Got it! One more thing - when should I use useReducer instead of useState?"},
            {"role": "assistant", "content": "Use `useReducer` when:\n\n1. **Complex state logic** with multiple sub-values\n2. **Next state depends on previous state**\n3. **Multiple related updates**\n\n```jsx\nconst reducer = (state, action) => {\n  switch (action.type) {\n    case 'INCREMENT':\n      return { count: state.count + 1 };\n    case 'DECREMENT':\n      return { count: state.count - 1 };\n    case 'RESET':\n      return { count: 0 };\n    default:\n      return state;\n  }\n};\n\nconst [state, dispatch] = useReducer(reducer, { count: 0 });\n\n// Usage\ndispatch({ type: 'INCREMENT' });\n```\n\n`useState` is simpler for most cases. `useReducer` shines when you have complex state transitions."},
            {"role": "user", "content": "Perfect! This really clarifies things. Thank you!"},
            {"role": "assistant", "content": "You're welcome! Here's a quick cheat sheet:\n\n**useState:**\n- Simple state\n- Independent values\n- Easy to understand\n\n**useReducer:**\n- Complex state logic\n- Multiple related actions\n- Easier to test\n\n**State updates:**\n- Always immutable\n- Use spread operator\n- Functional form for dependent updates\n\nHappy coding! 🚀"}
        ]
    },
    {
        "id": "python_async_await",
        "topic": "Python Async/Await",
        "messages": [
            {"role": "system", "content": "You are a helpful programming assistant."},
            {"role": "user", "content": "I keep seeing async/await in Python code. What exactly is it and when should I use it?"},
            {"role": "assistant", "content": "`async`/`await` enables concurrent programming in Python. Use it for I/O-bound operations:\n\n```python\nimport asyncio\nimport aiohttp\n\n# Regular function - runs sequentially\ndef fetch_data():\n    response = requests.get('https://api.example.com')\n    return response.json()\n\n# Async function - can run concurrently\nasync def fetch_data_async():\n    async with aiohttp.ClientSession() as session:\n        async with session.get('https://api.example.com') as response:\n            return await response.json()\n```\n\n**Use async when:**\n- Making API calls\n- Database queries\n- File I/O\n- Network operations\n\n**Don't use async for:**\n- CPU-intensive tasks (use multiprocessing)\n- Simple scripts\n- When libraries don't support it"},
            {"role": "user", "content": "How do I run an async function?"},
            {"role": "assistant", "content": "You need an event loop:\n\n```python\nimport asyncio\n\n# Method 1: asyncio.run() (Python 3.7+)\nasync def main():\n    result = await fetch_data_async()\n    print(result)\n\nasyncio.run(main())\n\n# Method 2: get_event_loop() (older code)\nloop = asyncio.get_event_loop()\nresult = loop.run_until_complete(fetch_data_async())\n\n# Method 3: In Jupyter notebooks\nawait fetch_data_async()  # Works directly!\n```\n\nMost modern code uses `asyncio.run()`."},
            {"role": "user", "content": "Can I run multiple async functions at once?"},
            {"role": "assistant", "content": "Yes! That's the power of async:\n\n```python\nimport asyncio\n\n# Run multiple coroutines concurrently\nasync def main():\n    # gather() runs all at once\n    results = await asyncio.gather(\n        fetch_user(1),\n        fetch_user(2),\n        fetch_user(3)\n    )\n    print(results)  # [user1, user2, user3]\n\n# Run with timeout\nasync def fetch_with_timeout():\n    try:\n        result = await asyncio.wait_for(\n            fetch_data_async(),\n            timeout=5.0\n        )\n    except asyncio.TimeoutError:\n        print('Request timed out!')\n\n# Run as tasks\nasync def main():\n    task1 = asyncio.create_task(fetch_user(1))\n    task2 = asyncio.create_task(fetch_user(2))\n    \n    user1 = await task1\n    user2 = await task2\n```"},
            {"role": "user", "content": "What's the difference between asyncio.gather() and asyncio.create_task()?"},
            {"role": "assistant", "content": "Good question!\n\n**asyncio.gather():**\n- Waits for all to complete\n- Returns results in order\n- If one fails, others continue (with return_exceptions=True)\n\n```python\nresults = await asyncio.gather(\n    task1(),\n    task2(),\n    task3()\n)\n```\n\n**asyncio.create_task():**\n- Schedules coroutine to run\n- Returns Task object immediately\n- More control over individual tasks\n\n```python\ntask1 = asyncio.create_task(do_something())\ntask2 = asyncio.create_task(do_something_else())\n\n# Do other work...\n\nresult1 = await task1\nresult2 = await task2\n```\n\nUse `gather()` when you want all results at once. Use `create_task()` when you need more control."},
            {"role": "user", "content": "Can I use async with regular synchronous code?"},
            {"role": "assistant", "content": "Yes, but be careful:\n\n```python\nimport asyncio\nfrom concurrent.futures import ThreadPoolExecutor\n\n# Run sync function in async context\nasync def main():\n    loop = asyncio.get_event_loop()\n    \n    # Run blocking function in thread pool\n    result = await loop.run_in_executor(\n        None,  # Uses default executor\n        blocking_function,\n        arg1, arg2\n    )\n\ndef blocking_function(arg1, arg2):\n    # Regular sync code\n    return slow_operation()\n\n# Or use a library like asyncio-compat\nimport requests\nfrom aiohttp import ClientSession\n\nasync def mixed():\n    # Sync requests (blocking)\n    sync_result = requests.get('https://api.example.com').json()\n    \n    # Async aiohttp (non-blocking)\n    async with ClientSession() as session:\n        async with session.get('https://api.example.com') as resp:\n            async_result = await resp.json()\n```\n\nPrefer async libraries when available!"},
            {"role": "user", "content": "This is super helpful! Any common mistakes to avoid?"},
            {"role": "assistant", "content": "Yes! Here are the top mistakes:\n\n**1. Forgetting await:**\n```python\n# ❌ Wrong - returns coroutine object\nresult = fetch_data_async()\n\n# ✅ Correct\nresult = await fetch_data_async()\n```\n\n**2. Using blocking code in async:**\n```python\n# ❌ Wrong - blocks event loop\nasync def bad():\n    time.sleep(1)  # Blocks!\n\n# ✅ Correct\nasync def good():\n    await asyncio.sleep(1)  # Async!\n```\n\n**3. Not using async context managers:**\n```python\n# ❌ Wrong - connection may not close\nresponse = await session.get(url)\ndata = await response.json()\n\n# ✅ Correct\nasync with session.get(url) as response:\n    data = await response.json()\n```\n\n**4. Mixing sync and async without executor:**\n```python\n# ❌ Wrong - blocks event loop\nasync def bad():\n    return requests.get(url)  # Sync call!\n\n# ✅ Correct\nasync def good():\n    async with aiohttp.ClientSession() as session:\n        async with session.get(url) as response:\n            return await response.json()\n```\n\nStick to async libraries and always `await` your coroutines!"}
        ]
    },
    {
        "id": "sql_join_types",
        "topic": "SQL JOIN Types",
        "messages": [
            {"role": "system", "content": "You are a helpful programming assistant."},
            {"role": "user", "content": "I'm always confused by SQL JOINs. Can you explain the different types?"},
            {"role": "assistant", "content": "Sure! Here are the main JOIN types:\n\n**1. INNER JOIN** (most common)\nReturns only matching rows from both tables:\n```sql\nSELECT users.name, orders.total\nFROM users\nINNER JOIN orders ON users.id = orders.user_id;\n```\nResult: Only users who have orders\n\n**2. LEFT JOIN (LEFT OUTER JOIN)**\nReturns all rows from left table, matched rows from right:\n```sql\nSELECT users.name, orders.total\nFROM users\nLEFT JOIN orders ON users.id = orders.user_id;\n```\nResult: All users, even those without orders (orders.total = NULL)\n\n**3. RIGHT JOIN (RIGHT OUTER JOIN)**\nReturns all rows from right table, matched rows from left:\n```sql\nSELECT users.name, orders.total\nFROM users\nRIGHT JOIN orders ON users.id = orders.user_id;\n```\nResult: All orders, even orphaned ones\n\n**4. FULL OUTER JOIN**\nReturns all rows from both tables:\n```sql\nSELECT users.name, orders.total\nFROM users\nFULL OUTER JOIN orders ON users.id = orders.user_id;\n```\nResult: Everything, with NULLs where no match"},
            {"role": "user", "content": "When would I use LEFT JOIN vs INNER JOIN?"},
            {"role": "assistant", "content": "**Use INNER JOIN when:**\n- You only want matching records\n- Relationship is required\n- Example: \"Show orders with customer details\" (every order must have a customer)\n\n```sql\n-- Only orders with valid customers\nSELECT o.id, c.name, o.total\nFROM orders o\nINNER JOIN customers c ON o.customer_id = c.id;\n```\n\n**Use LEFT JOIN when:**\n- You want all records from main table\n- Relationship is optional\n- Finding missing relationships\n\nExample: \"Show all users, including those without orders\"\n```sql\n-- All users, even without orders\nSELECT u.name, COUNT(o.id) as order_count\nFROM users u\nLEFT JOIN orders o ON u.id = o.user_id\nGROUP BY u.id;\n```\n\nExample: \"Find users who never ordered\"\n```sql\nSELECT u.name\nFROM users u\nLEFT JOIN orders o ON u.id = o.user_id\nWHERE o.id IS NULL;  -- No matching order\n```"},
            {"role": "user", "content": "Can I join more than two tables?"},
            {"role": "assistant", "content": "Absolutely! You can chain multiple JOINs:\n\n```sql\nSELECT \n    u.name as user_name,\n    p.title as product_title,\n    o.quantity,\n    o.price,\n    c.name as category_name\nFROM users u\nINNER JOIN orders o ON u.id = o.user_id\nINNER JOIN products p ON o.product_id = p.id\nLEFT JOIN categories c ON p.category_id = c.id\nWHERE o.created_at >= '2024-01-01'\nORDER BY o.created_at DESC;\n```\n\n**Tips:**\n- Use table aliases (u, o, p, c) for readability\n- Join order usually doesn't matter for INNER JOIN\n- For LEFT JOIN, order matters! (left table first)\n- Add WHERE clause after all JOINs"},
            {"role": "user", "content": "What about CROSS JOIN? When would I use that?"},
            {"role": "assistant", "content": "CROSS JOIN creates a Cartesian product (all combinations):\n\n```sql\nSELECT colors.name, sizes.name\nFROM colors\nCROSS JOIN sizes;\n```\n\nIf you have 3 colors and 4 sizes, you get 12 rows:\n```\nRed     Small\nRed     Medium\nRed     Large\nRed     XL\nBlue    Small\nBlue    Medium\n...\n```\n\n**Real use cases:**\n\n1. **Product variants:**\n```sql\nINSERT INTO product_variants (product_id, color_id, size_id)\nSELECT p.id, c.id, s.id\nFROM products p\nCROSS JOIN colors c\nCROSS JOIN sizes s\nWHERE p.type = 'clothing';\n```\n\n2. **Date range generation:**\n```sql\nSELECT \n    dates.date,\n    users.name,\n    COALESCE(activity.count, 0) as activity_count\nFROM (\n    SELECT generate_series('2024-01-01', '2024-01-31', '1 day')::date as date\n) dates\nCROSS JOIN users\nLEFT JOIN user_activity activity \n    ON activity.user_id = users.id \n    AND activity.date = dates.date;\n```\n\n3. **Testing/scaffolding:**\n```sql\n-- Generate test data\nINSERT INTO test_cases (env, browser, feature)\nSELECT e.name, b.name, f.name\nFROM environments e\nCROSS JOIN browsers b\nCROSS JOIN features f;\n```\n\n⚠️ Be careful! CROSS JOIN can create massive result sets."},
            {"role": "user", "content": "Great! Last question - what's the difference between WHERE and ON in JOINs?"},
            {"role": "assistant", "content": "Excellent question! They behave differently:\n\n**ON clause:**\n- Filters BEFORE the join\n- Defines the relationship\n- For OUTER JOINs, affects which rows are kept from the preserved table\n\n**WHERE clause:**\n- Filters AFTER the join\n- Filters the final result\n- Can turn OUTER JOIN into INNER JOIN\n\n**Example showing the difference:**\n\n```sql\n-- Scenario: Find all users and their orders from 2024\n\n-- Method 1: Filter in ON clause\nSELECT u.name, o.created_at\nFROM users u\nLEFT JOIN orders o \n    ON u.id = o.user_id \n    AND o.created_at >= '2024-01-01';\n-- Result: All users, with 2024 orders or NULL\n\n-- Method 2: Filter in WHERE clause  \nSELECT u.name, o.created_at\nFROM users u\nLEFT JOIN orders o ON u.id = o.user_id\nWHERE o.created_at >= '2024-01-01';\n-- Result: Only users who have 2024 orders (no NULLs)\n-- This turned LEFT JOIN into INNER JOIN!\n```\n\n**For INNER JOIN, it doesn't matter:**\n```sql\n-- These are equivalent\nSELECT * FROM users u\nINNER JOIN orders o \n    ON u.id = o.user_id \n    AND o.total > 100;\n\nSELECT * FROM users u\nINNER JOIN orders o ON u.id = o.user_id\nWHERE o.total > 100;\n```\n\n**Best practice:**\n- Use ON for join conditions\n- Use WHERE for filtering results\n- Only put extra filters in ON when you specifically need LEFT JOIN behavior"}
        ]
    }
]

def main():
    output_dir = Path("../test_data_real")
    output_dir.mkdir(exist_ok=True)
    
    from data_generator import compress_conversation
    
    print("=" * 60)
    print("生成扩展的真实对话测试数据")
    print("=" * 60)
    print()
    
    for conv in REAL_CONVERSATIONS:
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
        print(f"  主题: {conv['topic']}")
        print(f"  压缩版本: truncate={len(compressed_versions['truncate'])}, "
              f"summarize={len(compressed_versions['summarize'])}, "
              f"remove_code={len(compressed_versions['remove_code'])}, "
              f"mixed={len(compressed_versions['mixed'])}")
        print()
    
    print(f"✓ 扩展数据生成完成！共 {len(REAL_CONVERSATIONS)} 个真实对话场景")
    print(f"保存在 {output_dir}/")
    print(f"\n现在运行: python benchmark_real.py")

if __name__ == "__main__":
    main()
