"""报告生成 Agent - 生成结构化 Markdown 报告"""

from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportAgent:
    """报告生成智能体 - 生成结构化的 Markdown 根因分析报告"""

    def __init__(self):
        pass

    async def execute(
        self,
        analysis_id: str,
        db_type: str,
        root_causes: List[Dict[str, Any]],
        similar_cases: List[Dict[str, Any]],
        key_errors: List[Dict[str, Any]],
        log_summary: str,
        time_range: Optional[Dict[str, Optional[str]]] = None,
        key_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        生成分析报告

        Args:
            analysis_id: 分析 ID
            db_type: 数据库类型
            root_causes: 根因列表
            similar_cases: 相似案例列表
            key_errors: 关键错误列表
            log_summary: 日志摘要
            time_range: 日志时间范围
            key_patterns: 日志关键模式

        Returns:
            {
                'report_markdown': str,
                'report_json': Dict,
                'summary': str,
                'action_items': List[str]
            }
        """
        logger.info(f"Generating report for analysis {analysis_id}...")

        # 生成 Markdown 报告
        markdown_report = self._generate_markdown_report(
            analysis_id=analysis_id,
            db_type=db_type,
            root_causes=root_causes,
            similar_cases=similar_cases,
            key_errors=key_errors,
            log_summary=log_summary,
            time_range=time_range,
            key_patterns=key_patterns,
        )

        # 提取关键行动项
        action_items = self._extract_action_items(root_causes)

        # 生成简明摘要
        summary = self._generate_summary(root_causes, action_items)

        logger.info(f"Report generated successfully ({len(markdown_report)} chars)")

        return {
            "report_markdown": markdown_report,
            "report_json": {
                "analysis_id": analysis_id,
                "db_type": db_type,
                "created_at": datetime.now().isoformat(),
                "root_causes": root_causes,
                "similar_cases": similar_cases,
                "action_items": action_items,
            },
            "summary": summary,
            "action_items": action_items,
        }

    def _generate_markdown_report(
        self,
        analysis_id: str,
        db_type: str,
        root_causes: List[Dict[str, Any]],
        similar_cases: List[Dict[str, Any]],
        key_errors: List[Dict[str, Any]],
        log_summary: str,
        time_range: Optional[Dict[str, Optional[str]]] = None,
        key_patterns: Optional[List[str]] = None,
    ) -> str:
        """生成 Markdown 报告"""

        md = []
        md.append("# 数据库故障根因分析报告")
        md.append("")

        # 基本信息
        md.append("## 📋 基本信息")
        md.append(f"- **分析 ID**: `{analysis_id}`")
        md.append(f"- **数据库类型**: {db_type.upper()}")
        md.append(f"- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        if time_range:
            if time_range.get("start"):
                md.append(f"- **日志起始时间**: {time_range.get('start')}")
            if time_range.get("end"):
                md.append(f"- **日志结束时间**: {time_range.get('end')}")

        md.append("")

        # 日志摘要
        md.append("## 📊 日志摘要")
        md.append(log_summary)
        md.append("")

        # 关键错误
        if key_errors:
            md.append("## ⚠️ 关键错误")
            md.append("| 行号 | 错误码 | 级别 | 消息 |")
            md.append("|------|--------|------|------|")

            for error in key_errors[:10]:
                line = error.get("line", "-")
                code = error.get("error_code", "-")
                level = error.get("level", "-")
                msg = error.get("message", "")[:50].replace("|", "\\|")
                md.append(f"| {line} | {code} | {level} | {msg} |")

            md.append("")

        # 根因分析
        md.append("## 🔍 根因分析")

        if root_causes:
            for cause in root_causes[:3]:  # 只显示前 3 个根因
                rank = cause.get("rank", "?")
                root_cause = cause.get("root_cause", "Unknown")
                fault_type = cause.get("fault_type", "Unknown")
                component = cause.get("component", "Unknown")
                confidence = cause.get("confidence", 0)
                causal_chain = cause.get("causal_chain", [])
                symptoms = cause.get("symptoms", [])
                resolutions = cause.get("resolutions", [])

                md.append(f"### 根因 {rank} （置信度 {confidence*100:.0f}%）")
                md.append(f"**{root_cause}**")
                md.append("")

                md.append("#### 故障信息")
                md.append(f"- **故障类型**: {fault_type}")
                md.append(f"- **涉及组件**: {component}")
                md.append("")

                if causal_chain:
                    md.append("#### 因果链")
                    md.append(" → ".join(causal_chain))
                    md.append("")

                if symptoms:
                    md.append("#### 症状")
                    for symptom in symptoms:
                        md.append(f"- {symptom}")
                    md.append("")

                if resolutions:
                    md.append("#### 修复建议")
                    for resolution in resolutions:
                        md.append(f"- {resolution}")
                    md.append("")

                md.append("---")
                md.append("")
        else:
            md.append("无法确定根因。请检查日志内容和配置。")
            md.append("")

        # 相似历史案例
        if similar_cases:
            md.append("## 📚 相似历史案例")
            md.append(f"共找到 {len(similar_cases)} 个相似案例：")
            md.append("")

            for idx, case in enumerate(similar_cases[:5], 1):
                similarity = case.get("similarity", 0)
                root_cause = case.get("root_cause", "Unknown")
                resolution = case.get("resolution", "Unknown")

                md.append(f"### 案例 {idx} （相似度 {similarity*100:.0f}%）")
                md.append(f"- **根因**: {root_cause}")
                md.append(f"- **解决方案**: {resolution[:100]}")
                md.append("")
        else:
            md.append("## 📚 相似历史案例")
            md.append("未找到相似的历史案例。")
            md.append("")

        # 日志关键模式
        if key_patterns:
            md.append("## 🎯 日志关键模式")
            for pattern in key_patterns[:5]:
                md.append(f"- {pattern}")
            md.append("")

        # 建议的后续步骤
        md.append("## 📌 建议的后续步骤")
        md.append("")
        md.append("1. **验证根因** - 根据上述分析结果验证主要根因")
        md.append("2. **执行修复** - 参考修复建议执行相应操作")
        md.append("3. **监控改进** - 实施修复后持续监控系统状态")
        md.append("4. **文档更新** - 记录本次故障和解决方案供未来参考")
        md.append("")

        # 页脚
        md.append("---")
        md.append(
            f"*本报告由数据库故障分析系统自动生成。生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        )

        return "\n".join(md)

    def _extract_action_items(self, root_causes: List[Dict[str, Any]]) -> List[str]:
        """从根因中提取行动项"""
        action_items = []

        if not root_causes:
            return ["检查日志配置", "验证数据库连接"]

        primary_cause = root_causes[0]
        resolutions = primary_cause.get("resolutions", [])

        # 添加解决方案作为行动项
        for resolution in resolutions[:3]:
            action_items.append(f"执行: {resolution}")

        # 添加通用检查项
        fault_type = primary_cause.get("fault_type", "")
        if "deadlock" in fault_type.lower():
            action_items.append("检查长事务和锁等待配置")
            action_items.append("分析活跃连接和锁持有者")
        elif "connection" in fault_type.lower():
            action_items.append("检查最大连接数配置")
            action_items.append("排查连接泄漏")
        elif "memory" in fault_type.lower():
            action_items.append("检查缓冲池大小和内存使用")
            action_items.append("优化查询和索引")

        return action_items[:5]

    def _generate_summary(self, root_causes: List[Dict[str, Any]], action_items: List[str]) -> str:
        """生成简明摘要"""
        if not root_causes:
            return "分析未能确定根因，需要进一步调查。"

        primary = root_causes[0]
        root_cause = primary.get("root_cause", "Unknown")
        confidence = primary.get("confidence", 0)

        summary = f"故障根因初步判定为: {root_cause}（置信度 {confidence*100:.0f}%）。"

        if action_items:
            summary += f"建议首先 {action_items[0].lower().replace('执行: ', '')}。"

        return summary


report_agent = ReportAgent()
