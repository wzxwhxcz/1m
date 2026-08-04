"""
使用真实 LLM 压缩数据测试匹配策略
"""
import sys
sys.path.append('.')

from pathlib import Path
from benchmark import MatcherBenchmark

def main():
    print("=" * 80)
    print("使用真实 LLM 压缩数据测试匹配策略")
    print("=" * 80)
    print()
    print("压缩方式说明：")
    print("  - llm_compact_20: 模拟 Claude /compact，保留 20% 内容")
    print("  - llm_compact_15: 更激进的压缩，保留 15%")
    print("  - llm_compact_30: 较温和的压缩，保留 30%")
    print("  - aggressive_summary: 极度压缩，保留 10%")
    print()
    
    # 检查数据目录
    test_data_dir = Path("../test_data_realistic")
    
    if not test_data_dir.exists():
        print(f"❌ 测试数据目录不存在: {test_data_dir}")
        print("请先运行: python data_generator_realistic.py")
        return
    
    # 统计测试数据
    full_files = list(test_data_dir.glob("*_full.json"))
    print(f"找到 {len(full_files)} 个真实对话测试用例\n")
    
    if len(full_files) == 0:
        print("❌ 没有测试数据，请先运行 data_generator_realistic.py")
        return
    
    # 运行 benchmark
    benchmark = MatcherBenchmark(str(test_data_dir))
    benchmark.run_benchmark()
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

if __name__ == "__main__":
    main()
