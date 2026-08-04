"""
真实的 LLM 压缩场景生成器
模拟 Claude /compact 和 ChatGPT 的实际压缩行为
"""
import json
import hashlib
from pathlib import Path
from typing import List, Dict

def realistic_llm_summarization(messages: List[Dict], compression_ratio: float = 0.2) -> List[Dict]:
    """
    模拟真实的 LLM 压缩：用语义总结替换早期对话
    
    Args:
        messages: 完整消息列表
        compression_ratio: 压缩后保留的比例（Claude /compact 是 15-20%）
    
    Returns:
        压缩后的消息列表
    """
    if len(messages) <= 5:
        return messages
    
    # 保留 system 消息
    system_msg = [msg for msg in messages if msg.get("role") == "system"]
    non_system = [msg for msg in messages if msg.get("role") != "system"]
    
    # 计算需要压缩的消息数量
    target_count = max(5, int(len(non_system) * compression_ratio))
    keep_recent = max(3, target_count // 2)  # 保留最近几条完整消息
    
    # 早期对话（需要总结）
    early_messages = non_system[:-keep_recent]
    recent_messages = non_system[-keep_recent:]
    
    # 生成真实的总结（模拟 LLM 的总结风格）
    summary_content = _generate_realistic_summary(early_messages)
    
    summary_msg = {
        "role": "assistant",
        "content": f"[Conversation Summary]\n\n{summary_content}\n\n[Continuing from here with full message history...]"
    }
    
    return system_msg + [summary_msg] + recent_messages


def _generate_realistic_summary(messages: List[Dict]) -> str:
    """
    生成真实风格的对话总结
    模拟 Claude /compact 或 ChatGPT 的总结方式
    """
    # 提取关键信息
    topics = set()
    technologies = set()
    key_decisions = []
    
    for msg in messages:
        content = msg.get("content", "").lower()
        
        # 识别技术栈
        tech_keywords = {
            "react": "React", "vue": "Vue", "express": "Express", 
            "python": "Python", "async": "async/await", "jwt": "JWT",
            "sql": "SQL", "join": "SQL JOINs", "hooks": "React Hooks"
        }
        for keyword, tech in tech_keywords.items():
            if keyword in content:
                technologies.add(tech)
        
        # 识别关键决策点
        if "decided" in content or "we'll" in content or "use" in content:
            # 提取第一句话作为决策
            first_sentence = content.split('.')[0][:100]
            if len(first_sentence) > 20:
                key_decisions.append(first_sentence)
    
    # 构建总结
    parts = []
    
    if technologies:
        parts.append(f"Technologies discussed: {', '.join(technologies)}")
    
    parts.append(f"The user asked {len([m for m in messages if m.get('role') == 'user'])} questions over {len(messages)} messages.")
    
    if key_decisions:
        parts.append(f"Key decisions made:\n- " + "\n- ".join(key_decisions[:3]))
    
    # 提取最后讨论的主题
    last_user_messages = [m.get("content", "")[:200] for m in messages[-5:] if m.get("role") == "user"]
    if last_user_messages:
        parts.append(f"Most recent topics:\n- " + "\n- ".join(last_user_messages[:2]))
    
    return "\n\n".join(parts)


def generate_realistic_test_data():
    """生成真实的压缩测试数据"""
    output_dir = Path("../test_data_realistic")
    output_dir.mkdir(exist_ok=True)
    
    # 读取现有的真实对话
    real_data_dir = Path("../test_data_real")
    
    if not real_data_dir.exists():
        print("❌ 请先运行 data_generator_extended.py 生成真实对话数据")
        return
    
    print("=" * 60)
    print("生成真实的 LLM 压缩测试数据")
    print("=" * 60)
    print()
    
    full_files = list(real_data_dir.glob("*_full.json"))
    
    for full_file in full_files:
        conv_id = full_file.stem.replace("_full", "")
        
        # 读取完整对话
        with open(full_file, 'r', encoding='utf-8') as f:
            conversation = json.load(f)
        
        messages = conversation["messages"]
        
        # 生成真实的压缩版本
        compressed_versions = {
            "llm_compact_20": realistic_llm_summarization(messages, compression_ratio=0.20),
            "llm_compact_15": realistic_llm_summarization(messages, compression_ratio=0.15),
            "llm_compact_30": realistic_llm_summarization(messages, compression_ratio=0.30),
            "aggressive_summary": realistic_llm_summarization(messages, compression_ratio=0.10),
        }
        
        # 保存
        output_full = output_dir / f"{conv_id}_full.json"
        output_compressed = output_dir / f"{conv_id}_compressed.json"
        
        with open(output_full, 'w', encoding='utf-8') as f:
            json.dump(conversation, f, indent=2, ensure_ascii=False)
        
        with open(output_compressed, 'w', encoding='utf-8') as f:
            json.dump(compressed_versions, f, indent=2, ensure_ascii=False)
        
        print(f"✓ {conv_id}")
        print(f"  完整消息: {len(messages)} 条")
        for method, compressed in compressed_versions.items():
            ratio = len(compressed) / len(messages) * 100
            print(f"  {method}: {len(compressed)} 条 ({ratio:.1f}%)")
        print()
    
    print(f"✓ 真实压缩数据生成完成！保存在 {output_dir}/")
    print(f"\n下一步: python benchmark_realistic.py")


if __name__ == "__main__":
    generate_realistic_test_data()
