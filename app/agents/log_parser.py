"""日志解析 Agent - 结构化提取日志条目"""

import re
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


class LogEntry:
    """日志条目数据结构"""

    def __init__(
        self,
        line_number: int,
        timestamp: Optional[datetime],
        level: str,
        error_code: Optional[str],
        message: str,
        raw_line: str,
    ):
        self.line_number = line_number
        self.timestamp = timestamp
        self.level = level
        self.error_code = error_code
        self.message = message
        self.raw_line = raw_line

    def to_dict(self) -> Dict[str, Any]:
        return {
            "line_number": self.line_number,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "level": self.level,
            "error_code": self.error_code,
            "message": self.message,
        }


class LogParserAgent:
    """日志解析智能体"""

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-6")
        self.db_type = None

    async def execute(self, log_content: str, db_type: str) -> Dict[str, Any]:
        """
        解析日志文件

        Args:
            log_content: 日志文件内容
            db_type: 数据库类型 ('postgresql' 或 'mysql')

        Returns:
            {
                'entries': List[LogEntry],
                'error_count': int,
                'time_range': {'start': datetime, 'end': datetime},
                'key_patterns': List[str],
                'summary': str
            }
        """
        self.db_type = db_type
        logger.info(f"Parsing logs for {db_type}...")

        # 第一步：预解析日志获取基本结构
        entries = self._pre_parse_logs(log_content)
        logger.info(f"Pre-parsed {len(entries)} log entries")

        # 第二步：使用 LLM 进行高级解析
        summary = await self._llm_parse_summary(log_content)
        logger.info(f"LLM parsing completed")

        # 第三步：提取关键错误
        key_errors = self._extract_key_errors(entries)

        # 计算时间范围
        time_range = self._get_time_range(entries)

        # 识别关键模式
        key_patterns = self._identify_key_patterns(entries)

        return {
            "entries": [e.to_dict() for e in entries],
            "entry_objects": entries,  # 保留原始对象供后续使用
            "error_count": len([e for e in entries if e.level in ["ERROR", "FATAL"]]),
            "time_range": time_range,
            "key_patterns": key_patterns,
            "key_errors": key_errors,
            "summary": summary,
        }

    def _pre_parse_logs(self, log_content: str) -> List[LogEntry]:
        """预解析日志，提取基本结构"""
        entries = []
        lines = log_content.split("\n")

        if self.db_type == "postgresql":
            entries = self._parse_postgresql_logs(lines)
        elif self.db_type == "mysql":
            entries = self._parse_mysql_logs(lines)

        return entries

    def _parse_postgresql_logs(self, lines: List[str]) -> List[LogEntry]:
        """PostgreSQL 日志格式解析"""
        entries = []
        # PostgreSQL 日志格式示例：
        # 2026-05-06 12:34:56.123 UTC [1234] ERROR:  deadlock detected
        pg_pattern = r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \w+)\s+\[(\d+)\]\s+([A-Z]+):\s+(.*)$"

        for idx, line in enumerate(lines):
            if not line.strip():
                continue

            match = re.match(pg_pattern, line)
            if match:
                timestamp_str, pid, level, message = match.groups()
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace(" UTC", "+00:00"))
                except ValueError:
                    timestamp = None

                error_code = self._extract_error_code_pg(line)
                entries.append(
                    LogEntry(
                        line_number=idx + 1,
                        timestamp=timestamp,
                        level=level,
                        error_code=error_code,
                        message=message,
                        raw_line=line,
                    )
                )
            else:
                # 不匹配格式的行
                if "ERROR" in line or "FATAL" in line or "PANIC" in line:
                    entries.append(
                        LogEntry(
                            line_number=idx + 1,
                            timestamp=None,
                            level="ERROR" if "ERROR" in line else "INFO",
                            error_code=self._extract_error_code_pg(line),
                            message=line,
                            raw_line=line,
                        )
                    )

        return entries

    def _parse_mysql_logs(self, lines: List[str]) -> List[LogEntry]:
        """MySQL 日志格式解析"""
        entries = []
        # MySQL 日志格式示例：
        # 2026-05-06T12:34:56.123456Z 1234 [ERROR] [Server] Error message
        mysql_pattern = r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+(\d+)\s+\[([A-Z]+)\].*:\s+(.*)$"

        for idx, line in enumerate(lines):
            if not line.strip():
                continue

            match = re.match(mysql_pattern, line)
            if match:
                timestamp_str, thread_id, level, message = match.groups()
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except ValueError:
                    timestamp = None

                error_code = self._extract_error_code_mysql(line)
                entries.append(
                    LogEntry(
                        line_number=idx + 1,
                        timestamp=timestamp,
                        level=level,
                        error_code=error_code,
                        message=message,
                        raw_line=line,
                    )
                )
            else:
                if "[ERROR]" in line or "[Warning]" in line:
                    level = "ERROR" if "[ERROR]" in line else "WARNING"
                    entries.append(
                        LogEntry(
                            line_number=idx + 1,
                            timestamp=None,
                            level=level,
                            error_code=self._extract_error_code_mysql(line),
                            message=line,
                            raw_line=line,
                        )
                    )

        return entries

    def _extract_error_code_pg(self, line: str) -> Optional[str]:
        """提取 PostgreSQL 错误码（如 40P01）"""
        # PostgreSQL SQLSTATE 格式：5位字母数字
        match = re.search(r"\b([A-Z0-9]{5})\b", line)
        if match:
            code = match.group(1)
            # 确保是有效的 SQLSTATE 码
            if re.match(r"^[0-9]{2}[A-Z0-9]{3}$", code):
                return code
        return None

    def _extract_error_code_mysql(self, line: str) -> Optional[str]:
        """提取 MySQL 错误码（如 1213）"""
        # MySQL 错误码格式：4-5位数字
        match = re.search(r"error (\d{4,5})", line, re.IGNORECASE)
        if match:
            return match.group(1)

        # 备用格式：[Err] NNNN
        match = re.search(r"\[Err\]\s+(\d{4,5})", line)
        if match:
            return match.group(1)

        return None

    async def _llm_parse_summary(self, log_content: str) -> str:
        """使用 LLM 生成日志摘要"""
        try:
            prompt = f"""
分析以下数据库日志，生成简明摘要（最多 200 字）：

数据库类型: {self.db_type}

日志内容（前 2000 字符）:
{log_content[:2000]}

请总结：
1. 主要问题类型
2. 出现的关键错误码
3. 问题的严重性（Critical/High/Medium/Low）
4. 建议的初步检查点
"""
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            logger.error(f"LLM parsing failed: {e}")
            return "LLM 解析失败"

    def _extract_key_errors(self, entries: List[LogEntry]) -> List[Dict[str, Any]]:
        """提取关键错误"""
        key_errors = []
        seen_codes = set()

        for entry in entries:
            if entry.level in ["ERROR", "FATAL", "PANIC"] and entry.error_code:
                if entry.error_code not in seen_codes:
                    key_errors.append(
                        {
                            "line": entry.line_number,
                            "error_code": entry.error_code,
                            "message": entry.message[:100],  # 截断长消息
                            "level": entry.level,
                        }
                    )
                    seen_codes.add(entry.error_code)

        return key_errors[:10]  # 最多返回 10 个关键错误

    def _get_time_range(self, entries: List[LogEntry]) -> Dict[str, Optional[str]]:
        """获取日志时间范围"""
        timestamped_entries = [e for e in entries if e.timestamp]

        if not timestamped_entries:
            return {"start": None, "end": None}

        return {
            "start": timestamped_entries[0].timestamp.isoformat(),
            "end": timestamped_entries[-1].timestamp.isoformat(),
        }

    def _identify_key_patterns(self, entries: List[LogEntry]) -> List[str]:
        """识别日志中的关键模式"""
        patterns = []
        error_codes = {}

        for entry in entries:
            if entry.error_code:
                error_codes[entry.error_code] = error_codes.get(entry.error_code, 0) + 1

        # 返回出现超过 3 次的错误码
        for code, count in sorted(error_codes.items(), key=lambda x: x[1], reverse=True):
            if count >= 2:
                patterns.append(f"ErrorCode {code} appeared {count} times")

        # 识别特定关键词
        keywords = ["deadlock", "timeout", "connection", "memory", "disk", "lock"]
        for keyword in keywords:
            count = sum(
                1
                for e in entries
                if keyword.lower() in e.message.lower() and e.level in ["ERROR", "FATAL"]
            )
            if count > 0:
                patterns.append(f"{keyword.capitalize()} mentioned {count} times")

        return patterns


log_parser_agent = LogParserAgent()
