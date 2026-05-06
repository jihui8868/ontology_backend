"""分析流水线 - 编排多个智能体成完整的根因分析流程"""

import asyncio
import logging
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime

from app.agents.log_parser import log_parser_agent
from app.agents.ontology_query import ontology_query_agent
from app.agents.similar_case import similar_case_agent
from app.agents.reasoning import reasoning_agent
from app.agents.report import report_agent

logger = logging.getLogger(__name__)


class AnalysisPipeline:
    """根因分析流水线 - 协调多个 Agent 进行分析"""

    def __init__(self):
        self.log_parser = log_parser_agent
        self.ontology_query = ontology_query_agent
        self.similar_case = similar_case_agent
        self.reasoning = reasoning_agent
        self.report = report_agent
        self.progress_callbacks = []

    def add_progress_callback(self, callback: Callable) -> None:
        """添加进度回调"""
        self.progress_callbacks.append(callback)

    async def _emit_progress(
        self, step: str, percentage: int, message: str
    ) -> None:
        """触发进度更新"""
        logger.info(f"Progress: {step} ({percentage}%) - {message}")
        for callback in self.progress_callbacks:
            try:
                await callback(step=step, percentage=percentage, message=message)
            except Exception as e:
                logger.error(f"Progress callback failed: {e}")

    async def analyze(self, log_content: str, db_type: str) -> Dict[str, Any]:
        """
        执行完整的根因分析流水线

        Args:
            log_content: 日志文件内容
            db_type: 数据库类型 ('postgresql' 或 'mysql')

        Returns:
            {
                'root_causes': List[Dict],
                'report': str,
                'analysis_metadata': Dict,
                'action_items': List[str],
                'execution_time': float
            }
        """
        start_time = datetime.now()

        try:
            await self._emit_progress(
                "init", 5, "初始化分析流程..."
            )

            # Step 1: 日志解析
            await self._emit_progress(
                "parsing", 10, "正在解析日志文件..."
            )
            parse_result = await self.log_parser.execute(log_content, db_type)
            await self._emit_progress(
                "parsing", 20, f"已解析 {len(parse_result['entries'])} 条日志"
            )

            # 提取关键数据
            entries = parse_result.get("entry_objects", [])
            key_errors = parse_result.get("key_errors", [])
            key_patterns = parse_result.get("key_patterns", [])
            log_summary = parse_result.get("summary", "")
            time_range = parse_result.get("time_range", {})

            # Step 2 & 3: 并行执行本体查询和相似案例检索
            await self._emit_progress(
                "ontology", 30, "查询本体知识图谱..."
            )
            await self._emit_progress(
                "similarity", 30, "检索相似历史案例..."
            )

            # 并行执行
            ontology_result, similarity_result = await asyncio.gather(
                self.ontology_query.execute(
                    error_codes=[e.get("error_code") for e in key_errors if e.get("error_code")],
                    db_type=db_type,
                    key_patterns=key_patterns,
                ),
                self.similar_case.execute(
                    log_summary=log_summary,
                    db_type=db_type,
                    key_errors=key_errors,
                    top_k=5,
                ),
            )

            await self._emit_progress(
                "ontology", 50, f"找到 {len(ontology_result.get('matches', []))} 个本体匹配"
            )
            await self._emit_progress(
                "similarity", 50, f"找到 {len(similarity_result.get('similar_cases', []))} 个相似案例"
            )

            # Step 4: 根因推理
            await self._emit_progress(
                "reasoning", 60, "进行根因推理..."
            )

            ontology_matches = ontology_result.get("matches", [])
            fault_types = ontology_result.get("fault_types", {})
            similar_cases = similarity_result.get("similar_cases", [])

            reasoning_result = await self.reasoning.execute(
                ontology_matches=ontology_matches,
                fault_types=fault_types,
                similar_cases=similar_cases,
                key_patterns=key_patterns,
                log_entries=[e.to_dict() if hasattr(e, 'to_dict') else e for e in entries],
            )

            await self._emit_progress(
                "reasoning", 75, f"生成了 {len(reasoning_result.get('root_causes', []))} 个根因假设"
            )

            # Step 5: 报告生成
            await self._emit_progress(
                "report", 80, "生成分析报告..."
            )

            report_result = await self.report.execute(
                analysis_id="analysis_" + str(int(start_time.timestamp())),
                db_type=db_type,
                root_causes=reasoning_result.get("root_causes", []),
                similar_cases=similar_cases,
                key_errors=key_errors,
                log_summary=log_summary,
                time_range=time_range,
                key_patterns=key_patterns,
            )

            await self._emit_progress(
                "report", 90, "报告生成完成"
            )

            # 可选：存储案例到 Milvus（供后续检索）
            primary_cause = reasoning_result.get("primary_cause", "Unknown")
            primary_resolutions = []
            for cause in reasoning_result.get("root_causes", []):
                if cause.get("rank") == 1:
                    primary_resolutions = cause.get("resolutions", [])
                    break

            resolution_text = "; ".join(primary_resolutions) if primary_resolutions else "待定"

            try:
                await similar_case_agent.store_current_case(
                    analysis_id="analysis_" + str(int(start_time.timestamp())),
                    db_type=db_type,
                    log_summary=log_summary,
                    root_cause=primary_cause,
                    resolution=resolution_text,
                )
                logger.info("Case stored to Milvus for future reference")
            except Exception as e:
                logger.warning(f"Failed to store case to Milvus: {e}")

            await self._emit_progress(
                "completed", 100, "分析完成"
            )

            # 计算执行时间
            execution_time = (datetime.now() - start_time).total_seconds()

            return {
                "status": "completed",
                "root_causes": reasoning_result.get("root_causes", []),
                "primary_cause": primary_cause,
                "report": report_result.get("report_markdown", ""),
                "report_json": report_result.get("report_json", {}),
                "action_items": report_result.get("action_items", []),
                "analysis_metadata": {
                    "db_type": db_type,
                    "log_entries_count": len(entries),
                    "key_errors_count": len(key_errors),
                    "ontology_matches": len(ontology_matches),
                    "similar_cases_count": len(similar_cases),
                    "execution_time": execution_time,
                    "started_at": start_time.isoformat(),
                    "completed_at": datetime.now().isoformat(),
                },
            }

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}", exc_info=True)
            await self._emit_progress(
                "error", 0, f"分析失败: {str(e)}"
            )
            return {
                "status": "failed",
                "error": str(e),
                "execution_time": (datetime.now() - start_time).total_seconds(),
            }

    async def analyze_with_streaming(
        self,
        log_content: str,
        db_type: str,
        progress_queue: Optional[asyncio.Queue] = None,
    ) -> Dict[str, Any]:
        """
        支持流式进度推送的分析

        Args:
            log_content: 日志内容
            db_type: 数据库类型
            progress_queue: 用于接收进度更新的异步队列

        Returns:
            分析结果
        """
        async def queue_callback(step: str, percentage: int, message: str) -> None:
            if progress_queue:
                await progress_queue.put({
                    "step": step,
                    "percentage": percentage,
                    "message": message,
                })

        self.add_progress_callback(queue_callback)
        return await self.analyze(log_content, db_type)


# 创建全局流水线实例
analysis_pipeline = AnalysisPipeline()
