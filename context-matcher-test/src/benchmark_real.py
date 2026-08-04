"""
使用真实对话数据测试匹配策略
"""
import sys
sys.path.append('.')

from pathlib import Path
from benchmark import MatcherBenchmark

def main():
    print("=" * 80)
    print("使用真实对话数据测试匹配策略")
    print("=" * 80)
    print()
    
    # 检查数据目录
    test_data_dir = Path("../test_data_real")
    
    if not test_data_dir.exists():
        print(f"❌ 测试数据目录不存在: {test_data_dir}")
        print("请先运行: python data_generator_real.py")
        return
    
    # 统计测试数据
    full_files = list(test_data_dir.glob("*_full.json"))
    print(f"找到 {len(full_files)} 个真实对话测试用例\n")
    
    if len(full_files) == 0:
        print("❌ 没有测试数据，请先运行 data_generator_real.py")
        return
    
    # 运行 benchmark
    benchmark = MatcherBenchmark(str(test_data_dir))
    benchmark.run_benchmark()
    
    print("\n" + "=" * 80)
    print("测试完成！查看上面的结果分析。")
    print("=" * 80)

if __name__ == "__main__":
    main()
