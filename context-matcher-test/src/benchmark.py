"""
Benchmark 测试脚本：测试 5 种匹配策略的准确率
"""
import json
import time
from pathlib import Path
from matcher import SessionMatcher
from typing import Dict, List, Tuple

class MatcherBenchmark:
    def __init__(self, test_data_dir: str):
        self.test_data_dir = Path(test_data_dir)
        self.results = {
            "time_window": {"correct": 0, "wrong": 0, "no_match": 0, "times": []},
            "anchor": {"correct": 0, "wrong": 0, "no_match": 0, "times": []},
            "features": {"correct": 0, "wrong": 0, "no_match": 0, "times": []},
            "vector": {"correct": 0, "wrong": 0, "no_match": 0, "times": []},
            "hybrid": {"correct": 0, "wrong": 0, "no_match": 0, "times": []}
        }
    
    def load_test_data(self) -> List[Dict]:
        """加载所有测试数据"""
        test_cases = []
        
        for full_file in self.test_data_dir.glob("*_full.json"):
            conv_id = full_file.stem.replace("_full", "")
            compressed_file = self.test_data_dir / f"{conv_id}_compressed.json"
            
            if compressed_file.exists():
                with open(full_file, "r", encoding="utf-8") as f:
                    full_data = json.load(f)
                
                with open(compressed_file, "r", encoding="utf-8") as f:
                    compressed_data = json.load(f)
                
                test_cases.append({
                    "id": conv_id,
                    "full": full_data,
                    "compressed": compressed_data
                })
        
        return test_cases
    
    def run_benchmark(self):
        """运行完整的 benchmark"""
        print("=" * 60)
        print("开始匹配策略 Benchmark 测试")
        print("=" * 60)
        
        test_cases = self.load_test_data()
        
        if not test_cases:
            print("❌ 没有找到测试数据！")
            return
        
        print(f"\n✓ 加载了 {len(test_cases)} 个项目的测试数据\n")
        
        # 自动检测压缩方法
        if test_cases:
            compression_methods = list(test_cases[0]["compressed"].keys())
            print(f"检测到压缩方法: {', '.join(compression_methods)}\n")
        else:
            compression_methods = []
        
        for method in compression_methods:
            print(f"\n{'='*60}")
            print(f"测试压缩方法: {method}")
            print(f"{'='*60}\n")
            
            self._test_compression_method(test_cases, method)
        
        # 输出最终结果
        self._print_final_results()
    
    def _test_compression_method(self, test_cases: List[Dict], method: str):
        """测试特定压缩方法"""
        matcher = SessionMatcher()
        
        # 阶段1：存储所有完整会话
        print("阶段1: 存储完整会话...")
        for case in test_cases:
            user_id = "test_user"
            session_id = case["id"]
            messages = case["full"].get("messages", [])
            
            matcher.store_session(user_id, session_id, messages)
            print(f"  ✓ 存储会话 {session_id}: {len(messages)} 条消息")
        
        # 模拟用户同时使用多个项目（增加干扰）
        print("\n阶段2: 测试压缩后的匹配...")
        
        for case in test_cases:
            true_session_id = case["id"]
            compressed_messages = case["compressed"].get(method, [])
            
            if not compressed_messages:
                print(f"  ⚠️  {true_session_id} 没有 {method} 压缩版本")
                continue
            
            print(f"\n  测试: {true_session_id} (压缩: {method}, {len(compressed_messages)} 条消息)")
            
            # 测试5种策略
            strategies = {
                "time_window": matcher.match_by_time_window,
                "anchor": matcher.match_by_anchor,
                "features": matcher.match_by_features,
                "vector": matcher.match_by_vector,
                "hybrid": matcher.match_by_hybrid
            }
            
            for strategy_name, strategy_func in strategies.items():
                start = time.time()
                matched_id, score = strategy_func("test_user", compressed_messages)
                elapsed = (time.time() - start) * 1000  # 转为毫秒
                
                # 记录结果
                self.results[strategy_name]["times"].append(elapsed)
                
                if matched_id == true_session_id:
                    self.results[strategy_name]["correct"] += 1
                    status = "✓"
                elif matched_id is None:
                    self.results[strategy_name]["no_match"] += 1
                    status = "○"
                else:
                    self.results[strategy_name]["wrong"] += 1
                    status = "✗"
                
                print(f"    {status} {strategy_name:12s}: 匹配={matched_id or 'None':15s} "
                      f"得分={score:.2f}  耗时={elapsed:.1f}ms")
    
    def _print_final_results(self):
        """打印最终结果表格"""
        print("\n" + "=" * 80)
        print("最终测试结果")
        print("=" * 80)
        
        # 表头
        print(f"\n{'策略':<15} {'准确率':<10} {'误匹配率':<12} {'无匹配率':<12} "
              f"{'平均耗时':<12} {'推荐度'}")
        print("-" * 80)
        
        # 计算每个策略的指标
        for strategy_name, stats in self.results.items():
            total = stats["correct"] + stats["wrong"] + stats["no_match"]
            
            if total == 0:
                continue
            
            accuracy = stats["correct"] / total * 100
            wrong_rate = stats["wrong"] / total * 100
            no_match_rate = stats["no_match"] / total * 100
            avg_time = sum(stats["times"]) / len(stats["times"]) if stats["times"] else 0
            
            # 推荐度评分（准确率高、耗时低、误匹配低）
            score = accuracy - wrong_rate * 2 - avg_time * 0.01
            stars = "⭐" * min(5, max(1, int(score / 20)))
            
            print(f"{strategy_name:<15} {accuracy:>6.1f}%    {wrong_rate:>6.1f}%       "
                  f"{no_match_rate:>6.1f}%       {avg_time:>6.1f}ms     {stars}")
        
        # 给出建议
        print("\n" + "=" * 80)
        print("推荐策略")
        print("=" * 80)
        
        # 找出准确率最高的
        best_accuracy = max(
            [(name, stats["correct"] / (stats["correct"] + stats["wrong"] + stats["no_match"]))
             for name, stats in self.results.items()
             if (stats["correct"] + stats["wrong"] + stats["no_match"]) > 0],
            key=lambda x: x[1]
        )
        
        # 找出最快的
        fastest = min(
            [(name, sum(stats["times"]) / len(stats["times"]))
             for name, stats in self.results.items()
             if stats["times"]],
            key=lambda x: x[1]
        )
        
        print(f"\n1. 最高准确率: {best_accuracy[0]} ({best_accuracy[1]*100:.1f}%)")
        print(f"2. 最快响应: {fastest[0]} ({fastest[1]:.1f}ms)")
        print(f"\n💡 建议:")
        print(f"   - 如果用户单项目使用: 选择 'time_window' (简单快速)")
        print(f"   - 如果用户多项目切换: 选择 'features' 或 'hybrid' (准确度高)")
        print(f"   - 如果追求极致准确: 选择 'hybrid' (综合评分)")
        print(f"   - 如果追求极致性能: 选择 'time_window' (几乎无计算)")

def main():
    benchmark = MatcherBenchmark("../test_data")
    benchmark.run_benchmark()

if __name__ == "__main__":
    main()
