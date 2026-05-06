import logging
from typing import Dict, Any, Optional
import uuid
from datetime import datetime

from app.db import neo4j_client, milvus_client

logger = logging.getLogger(__name__)


class AnalysisService:
    """分析业务逻辑服务"""

    def __init__(self):
        self.neo4j_client = neo4j_client
        self.milvus_client = milvus_client

    async def detect_db_type(self, log_content: str) -> str:
        """
        从日志内容自动检测数据库类型

        Returns:
            'postgresql', 'mysql', 或 'unknown'
        """
        # PostgreSQL 特征
        pg_keywords = ["LOG:", "ERROR:", "FATAL:", "PANIC:", "deadlock detected"]
        # MySQL 特征
        mysql_keywords = ["[ERROR]", "[Warning]", "InnoDB"]

        pg_count = sum(1 for keyword in pg_keywords if keyword in log_content)
        mysql_count = sum(1 for keyword in mysql_keywords if keyword in log_content)

        if pg_count > mysql_count and pg_count > 0:
            return "postgresql"
        elif mysql_count > pg_count and mysql_count > 0:
            return "mysql"
        else:
            return "unknown"

    async def parse_logs(self, log_content: str) -> list:
        """
        解析日志内容为结构化数据

        Returns:
            List of parsed log entries
        """
        lines = log_content.split("\n")
        parsed_logs = []

        for idx, line in enumerate(lines):
            if not line.strip():
                continue

            parsed_logs.append(
                {
                    "line_number": idx + 1,
                    "content": line,
                    "timestamp": None,  # 待 LLM 解析
                    "level": self._extract_log_level(line),
                    "error_code": self._extract_error_code(line),
                }
            )

        return parsed_logs

    def _extract_log_level(self, line: str) -> str:
        """提取日志级别"""
        if "ERROR" in line or "[ERROR]" in line:
            return "ERROR"
        elif "FATAL" in line or "CRITICAL" in line:
            return "FATAL"
        elif "PANIC" in line:
            return "PANIC"
        elif "WARNING" in line or "[Warning]" in line:
            return "WARNING"
        else:
            return "INFO"

    def _extract_error_code(self, line: str) -> Optional[str]:
        """提取错误码"""
        import re

        # PostgreSQL 错误码格式 (如 40P01)
        pg_match = re.search(r"\b[A-Z0-9]{5}\b", line)
        if pg_match:
            return pg_match.group(0)

        # MySQL 错误码格式 (如 1213)
        mysql_match = re.search(r"error (\d{4})", line)
        if mysql_match:
            return mysql_match.group(1)

        return None

    async def query_ontology(self, error_code: str, db_type: str) -> Dict:
        """查询本体知识图谱"""
        try:
            result = await self.neo4j_client.query_error_code(error_code, db_type)
            if result:
                fault_chain = await self.neo4j_client.query_fault_type_chain(
                    result["fault_type"], db_type
                )
                result.update(fault_chain)
            return result or {}
        except Exception as e:
            logger.error(f"Failed to query ontology: {e}")
            return {}

    def search_similar_cases(
        self,
        query_embedding: list,
        db_type: Optional[str] = None,
        top_k: int = 5,
    ) -> list:
        """在 Milvus 中搜索相似案例"""
        try:
            cases = self.milvus_client.search_similar_cases(
                query_embedding=query_embedding,
                db_type=db_type,
                top_k=top_k,
            )
            return cases
        except Exception as e:
            logger.error(f"Failed to search similar cases: {e}")
            return []

    def store_case(
        self,
        case_id: str,
        db_type: str,
        summary_embedding: list,
        raw_log_snippet: str,
        root_cause: str,
        resolution: str,
    ) -> bool:
        """存储分析案例到 Milvus"""
        try:
            return self.milvus_client.insert_case(
                case_id=case_id,
                db_type=db_type,
                summary_embedding=summary_embedding,
                raw_log_snippet=raw_log_snippet,
                root_cause=root_cause,
                resolution=resolution,
            )
        except Exception as e:
            logger.error(f"Failed to store case: {e}")
            return False


analysis_service = AnalysisService()
