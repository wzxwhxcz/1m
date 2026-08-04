"""
生成压缩前后的详细对比报告
包含每个策略的分数变化分析
"""
import json
from pathlib import Path
from matcher import SessionMatcher
import time

def analyze_score_degradation():
    """分析压缩前后的分数变化"""
    
    print("=" * 80)
    print("压缩前后匹配分数对比分析")
    print("=" * 80)
    print()
    
    test_data_dir = Path("../test_data_realistic")
    
    # 加载测试数据
    test_cases = []
    for full_file in test_data_dir.glob("*_full.json"):
        conv_id = full_file.stem.replace("_full", "")
        compressed_file = test_data_dir / f"{conv_id}_compressed.json"
        
        if compressed_file.exists():
            with open(full_file, "r", encoding="utf-8") as f:
                full_data = json.load(f)
            with open(compressed_file, "r", encoding="utf-8") as f:
                compressed_data = json.load(f)
            
            test_cases.append({
                "id": conv_id,
                "full": full_data["messages"],
                "compressed": compressed_data
            })
    
    if not test_cases:
        print("❌ 没有测试数据")
        return
    
    print(f"加载了 {len(test_cases)} 个测试用例\n")
    
    # 结果存储
    results = {
        "time_window": [],
        "anchor": [],
        "features": [],
        "vector": [],
        "hybrid": []
    }
    
    # 对每个测试用例
    for case in test_cases:
        session_id = case["id"]
        full_messages = case["full"]
        
        print(f"\n{'='*80}")
        print(f"测试: {session_id}")
        print(f"完整消息: {len(full_messages)} 条")
        print(f"{'='*80}")
        
        # 测试压缩前（完整消息）
        matcher_full = SessionMatcher()
        
        # 存储多个会话作为干扰
        for other_case in test_cases:
            matcher_full.store_session("user", other_case["id"], other_case["full"])
        
        print(f"\n📊 压缩前（完整消息 {len(full_messages)} 条）:")
        print("-" * 80)
        
        full_scores = {}
        strategies = {
            "time_window": matcher_full.match_by_time_window,
            "anchor": matcher_full.match_by_anchor,
            "features": matcher_full.match_by_features,
            "vector": matcher_full.match_by_vector,
            "hybrid": matcher_full.match_by_hybrid
        }
        
        for strategy_name, strategy_func in strategies.items():
            matched_id, score = strategy_func("user", full_messages)
            correct = "✓" if matched_id == session_id else "✗"
            full_scores[strategy_name] = {
                "matched": matched_id,
                "score": score,
                "correct": matched_id == session_id
            }
            print(f"  {correct} {strategy_name:12s}: 匹配={matched_id or 'None':20s} 分数={score:.4f}")
        
        # 测试压缩后的各个版本
        for compress_method, compressed_messages in case["compressed"].items():
            compression_ratio = len(compressed_messages) / len(full_messages) * 100
            
            print(f"\n📊 压缩后 - {compress_method} ({len(compressed_messages)} 条, {compression_ratio:.1f}%):")
            print("-" * 80)
            
            matcher_compressed = SessionMatcher()
            
            # 存储多个会话作为干扰
            for other_case in test_cases:
                matcher_compressed.store_session("user", other_case["id"], other_case["full"])
            
            compressed_scores = {}
            for strategy_name, strategy_func in strategies.items():
                matched_id, score = strategy_func("user", compressed_messages)
                correct = "✓" if matched_id == session_id else "✗"
                compressed_scores[strategy_name] = {
                    "matched": matched_id,
                    "score": score,
                    "correct": matched_id == session_id
                }
                
                # 计算分数变化
                full_score = full_scores[strategy_name]["score"]
                score_diff = score - full_score
                score_change_pct = (score_diff / full_score * 100) if full_score > 0 else 0
                
                # 判断是否保持正确
                was_correct = full_scores[strategy_name]["correct"]
                is_correct = matched_id == session_id
                
                if was_correct and is_correct:
                    status = "✓ 保持正确"
                elif was_correct and not is_correct:
                    status = "✗ 压缩后失败"
                elif not was_correct and is_correct:
                    status = "⚠ 压缩后变正确"
                else:
                    status = "✗ 依然错误"
                
                print(f"  {correct} {strategy_name:12s}: 匹配={matched_id or 'None':20s} "
                      f"分数={score:.4f} (变化={score_diff:+.4f}, {score_change_pct:+.1f}%) {status}")
                
                # 记录结果
                results[strategy_name].append({
                    "session": session_id,
                    "compress_method": compress_method,
                    "full_score": full_score,
                    "compressed_score": score,
                    "score_diff": score_diff,
                    "score_change_pct": score_change_pct,
                    "was_correct": was_correct,
                    "is_correct": is_correct,
                    "compression_ratio": compression_ratio
                })
    
    # 生成汇总报告
    print("\n\n" + "=" * 80)
    print("汇总报告：压缩对匹配分数的影响")
    print("=" * 80)
    
    for strategy_name, records in results.items():
        print(f"\n{'='*80}")
        print(f"策略: {strategy_name.upper()}")
        print(f"{'='*80}")
        
        if not records:
            print("  无数据")
            continue
        
        # 统计
        total_tests = len(records)
        kept_correct = sum(1 for r in records if r["was_correct"] and r["is_correct"])
        became_wrong = sum(1 for r in records if r["was_correct"] and not r["is_correct"])
        became_correct = sum(1 for r in records if not r["was_correct"] and r["is_correct"])
        kept_wrong = sum(1 for r in records if not r["was_correct"] and not r["is_correct"])
        
        avg_score_change = sum(r["score_change_pct"] for r in records) / total_tests
        avg_full_score = sum(r["full_score"] for r in records) / total_tests
        avg_compressed_score = sum(r["compressed_score"] for r in records) / total_tests
        
        print(f"\n  总测试数: {total_tests}")
        print(f"  ✓ 保持正确: {kept_correct} ({kept_correct/total_tests*100:.1f}%)")
        print(f"  ✗ 压缩后失败: {became_wrong} ({became_wrong/total_tests*100:.1f}%)")
        print(f"  ⚠ 压缩后变正确: {became_correct} ({became_correct/total_tests*100:.1f}%)")
        print(f"  ✗ 依然错误: {kept_wrong} ({kept_wrong/total_tests*100:.1f}%)")
        
        print(f"\n  平均分数变化: {avg_score_change:+.2f}%")
        print(f"  压缩前平均分数: {avg_full_score:.4f}")
        print(f"  压缩后平均分数: {avg_compressed_score:.4f}")
        
        # 按压缩方法分组
        by_method = {}
        for r in records:
            method = r["compress_method"]
            if method not in by_method:
                by_method[method] = []
            by_method[method].append(r)
        
        print(f"\n  按压缩方法分析:")
        for method, method_records in by_method.items():
            method_kept = sum(1 for r in method_records if r["was_correct"] and r["is_correct"])
            method_total = len(method_records)
            method_avg_change = sum(r["score_change_pct"] for r in method_records) / method_total
            
            print(f"    {method:20s}: 保持正确率 {method_kept}/{method_total} ({method_kept/method_total*100:.1f}%), "
                  f"分数变化 {method_avg_change:+.2f}%")
    
    # 生成最终推荐
    print("\n\n" + "=" * 80)
    print("最终推荐")
    print("=" * 80)
    print()
    
    for strategy_name, records in results.items():
        if not records:
            continue
        
        kept_correct_rate = sum(1 for r in records if r["was_correct"] and r["is_correct"]) / len(records) * 100
        avg_score_change = sum(r["score_change_pct"] for r in records) / len(records)
        
        # 评级
        if kept_correct_rate >= 95:
            rating = "🏆 优秀"
        elif kept_correct_rate >= 80:
            rating = "✅ 良好"
        elif kept_correct_rate >= 60:
            rating = "⚠️  一般"
        else:
            rating = "❌ 较差"
        
        print(f"{strategy_name:15s}: {rating} | 保持正确率 {kept_correct_rate:.1f}% | 分数变化 {avg_score_change:+.1f}%")
    
    print()

if __name__ == "__main__":
    analyze_score_degradation()
