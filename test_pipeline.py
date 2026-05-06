#!/usr/bin/env python
"""
测试脚本：验证分析流水线的完整功能

运行方法: uv run python test_pipeline.py
"""

import asyncio
import logging
from app.agents.pipeline import analysis_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 示例 PostgreSQL 日志
SAMPLE_PG_LOG = """
2026-05-06 12:34:56.123 UTC [1234] ERROR:  40P01: deadlock detected
2026-05-06 12:34:56.234 UTC [1234] DETAIL:  Process 1234 waits for ShareLock on transaction 5678
2026-05-06 12:34:56.345 UTC [1235] ERROR:  40P01: deadlock detected
2026-05-06 12:34:56.456 UTC [1235] DETAIL:  Process 1235 waits for ShareLock on transaction 5679
2026-05-06 12:34:57.123 UTC [1234] LOG:  statement: SELECT * FROM users WHERE id = 1 FOR UPDATE
2026-05-06 12:35:00.123 UTC [5678] WARNING:  connection timeout
2026-05-06 12:35:01.123 UTC [5679] ERROR:  57P03: cannot connect now - server is in recovery mode
"""

# 示例 MySQL 日志
SAMPLE_MYSQL_LOG = """
2026-05-06T12:34:56.123456Z 1234 [ERROR] [Server] Error detected
2026-05-06T12:34:56.234567Z 1235 [ERROR] [InnoDB] Deadlock found when trying to get lock; try restarting transaction
2026-05-06T12:34:56.345678Z 1236 [Warning] [Server] Too many connections
2026-05-06T12:34:57.123456Z 1237 [ERROR] [Server] Got error from storage engine
2026-05-06T12:34:58.123456Z 1238 [ERROR] [InnoDB] Lock wait timeout exceeded; try restarting transaction
"""


async def test_analysis():
    """测试分析流水线"""
    print("\n" + "=" * 60)
    print("数据库故障分析系统 - 流水线测试")
    print("=" * 60 + "\n")

    # 测试 PostgreSQL 日志
    print("【测试 1】PostgreSQL 日志分析")
    print("-" * 60)

    progress_log = []

    async def progress_callback(step: str, percentage: int, message: str) -> None:
        progress_log.append(f"{step:15} {percentage:3}% {message}")
        print(f"  {step:15} {percentage:3}% {message}")

    # 添加进度回调
    analysis_pipeline.add_progress_callback(progress_callback)

    try:
        result = await analysis_pipeline.analyze(SAMPLE_PG_LOG, "postgresql")

        print(f"\n✓ 分析完成")
        print(f"  状态: {result.get('status')}")
        print(f"  根因数: {len(result.get('root_causes', []))}")
        print(f"  执行时间: {result.get('analysis_metadata', {}).get('execution_time', 0):.2f}s")

        if result.get("root_causes"):
            primary = result["root_causes"][0]
            print(f"  主要根因: {primary.get('root_cause')} (置信度 {primary.get('confidence', 0)*100:.0f}%)")

        if result.get("report"):
            print(f"  报告长度: {len(result.get('report', ''))} 字符")

        # 打印完整报告摘要
        print(f"\n📄 报告摘要:")
        print("-" * 60)
        report_lines = result.get("report", "").split("\n")[:30]
        for line in report_lines:
            print(f"  {line}")

    except Exception as e:
        print(f"✗ 分析失败: {e}")
        import traceback
        traceback.print_exc()

    # 测试 MySQL 日志
    print("\n\n【测试 2】MySQL 日志分析")
    print("-" * 60)

    # 清空进度日志和回调
    progress_log.clear()
    analysis_pipeline.progress_callbacks.clear()
    analysis_pipeline.add_progress_callback(progress_callback)

    try:
        result = await analysis_pipeline.analyze(SAMPLE_MYSQL_LOG, "mysql")

        print(f"\n✓ 分析完成")
        print(f"  状态: {result.get('status')}")
        print(f"  根因数: {len(result.get('root_causes', []))}")
        print(f"  执行时间: {result.get('analysis_metadata', {}).get('execution_time', 0):.2f}s")

        if result.get("root_causes"):
            primary = result["root_causes"][0]
            print(f"  主要根因: {primary.get('root_cause')} (置信度 {primary.get('confidence', 0)*100:.0f}%)")

    except Exception as e:
        print(f"✗ 分析失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # 运行异步测试
    asyncio.run(test_analysis())
