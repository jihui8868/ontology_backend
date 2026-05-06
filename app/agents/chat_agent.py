"""对话式多智能体系统 - 使用LangChain + Deepseek"""

import json
import logging
import uuid
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, AsyncGenerator, Any
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool

from app.core.config import settings
from app.agents.log_parser import log_parser_agent
from app.agents.ontology_query import ontology_query_agent
from app.agents.similar_case import similar_case_agent
from app.agents.reasoning import reasoning_agent
from app.agents.report import report_agent

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """聊天会话上下文"""
    session_id: str
    messages: List[BaseMessage] = field(default_factory=list)
    db_type: Optional[str] = None
    problem_description: Optional[str] = None
    document_content: Optional[str] = None
    uploaded_filename: Optional[str] = None
    analysis_done: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ChatAgent:
    """对话式数据库故障分析Agent - 使用Deepseek LLM"""

    def __init__(self):
        """初始化Chat Agent"""
        self.llm = ChatOpenAI(
            model=settings.deepseek_model,
            openai_api_key=settings.deepseek_api_key,
            openai_api_base=settings.deepseek_api_base,
            streaming=True,
            temperature=0.7,
        )
        self.sessions: Dict[str, ChatContext] = {}

        # 系统提示词
        self.system_prompt = """你是一名专业的数据库故障分析专家，具备丰富的PostgreSQL和MySQL故障诊断经验。

## 任务流程

### 信息收集阶段
在进行深入分析之前，请按以下顺序确认信息（每次最多问2个问题）：
1. **数据库类型** - PostgreSQL 还是 MySQL？
2. **故障描述** - 报错信息是什么？影响范围？何时发生？频率如何？
3. **日志文档** - 是否有相关日志文件可以上传？（大幅提升分析精度）

### 分析阶段（当有日志文档时立即启动）
使用以下结构化格式输出分析结果：

```
## 根因分析报告

### 🔍 Top 1 根因 (置信度: XX%)
- **故障类型**: [Type]
- **涉及组件**: [Component]
- **因果链路**: [Step1] → [Step2] → [Step3]
- **关键证据**: 日志第X行："..."

### 修复建议
1. [Action]
   - 执行: `SQL command`
   - 预期效果: [Expected outcome]
2. [Action 2]

### 🔗 相关错误码
- [PG:40P01] - Deadlock detected
- [MY:1213] - Deadlock found
```

### 回答策略
- 如果信息不完整：礼貌地逐步引导用户提供信息，一次最多2个问题
- 有日志文档时：立即进行深度分析，提供详细的根因、证据和修复步骤
- 没有日志时：根据描述提供基本的故障排查思路

### 语言要求
- 使用清晰的中文Markdown格式
- 代码和命令放在代码块中（标注语言类型）
- 重要信息用 **粗体** 或 ### 标题 标注
- 列表使用符号（✓, ✗, →, etc.）增强可读性
"""

    def create_session(self) -> str:
        """创建新的聊天会话"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = ChatContext(session_id=session_id)
        logger.info(f"Created chat session: {session_id}")
        return session_id

    def get_session(self, session_id: str) -> Optional[ChatContext]:
        """获取会话上下文"""
        return self.sessions.get(session_id)

    def attach_file(self, session_id: str, filename: str, content: str) -> bool:
        """附加日志文件到会话"""
        ctx = self.get_session(session_id)
        if not ctx:
            return False

        ctx.uploaded_filename = filename
        ctx.document_content = content
        logger.info(f"Attached file {filename} to session {session_id}")
        return True

    def _detect_db_type(self, text: str) -> Optional[str]:
        """从对话文本中检测数据库类型"""
        text_lower = text.lower()
        if re.search(r'postgres|pg|postgresql', text_lower):
            return 'postgresql'
        elif re.search(r'mysql|mariadb', text_lower):
            return 'mysql'
        return None

    def _extract_problem_description(self, text: str) -> str:
        """从文本中提取问题描述（简单版）"""
        # 去除问候语和非实质内容
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        # 连接保留问题相关的行
        return '\n'.join(lines[-3:])  # 简单地取最后3行

    def _assess_context(self, ctx: ChatContext) -> Dict[str, Any]:
        """评估当前上下文是否足以进行分析"""
        has_db_type = ctx.db_type is not None
        has_description = bool(ctx.problem_description and len(ctx.problem_description) > 5)
        has_document = bool(ctx.document_content)

        missing = []
        if not has_db_type:
            missing.append("数据库类型")
        if not has_description:
            missing.append("故障描述")

        return {
            "ready_for_analysis": has_db_type and has_description,
            "has_document": has_document,
            "missing": missing,
            "need_document": has_db_type and has_description and not has_document,
        }

    async def _run_analysis_pipeline(
        self, ctx: ChatContext
    ) -> str:
        """运行完整的分析管道并返回结果"""
        if not ctx.document_content:
            return "❌ 没有可用的日志文档"

        try:
            # 步骤1: 日志解析
            parse_result = await log_parser_agent.execute(
                ctx.document_content, ctx.db_type or "unknown"
            )
            key_errors = parse_result.get("key_errors", [])
            key_patterns = parse_result.get("key_patterns", [])
            log_summary = parse_result.get("summary", "")

            # 步骤2+3: 并行查询本体和相似案例（尽力而为，可能失败）
            try:
                ontology_result = await ontology_query_agent.execute(
                    error_codes=[
                        e.get("error_code") for e in key_errors
                        if e.get("error_code")
                    ],
                    db_type=ctx.db_type or "unknown",
                    key_patterns=key_patterns,
                )
            except Exception as e:
                logger.warning(f"Ontology query failed: {e}")
                ontology_result = {"matches": [], "fault_types": {}}

            try:
                similar_result = await similar_case_agent.execute(
                    log_summary=log_summary,
                    db_type=ctx.db_type or "unknown",
                    key_errors=key_errors,
                    top_k=3,
                )
            except Exception as e:
                logger.warning(f"Similar case search failed: {e}")
                similar_result = {"similar_cases": []}

            # 步骤4: 推理
            try:
                reasoning_result = await reasoning_agent.execute(
                    ontology_matches=ontology_result.get("matches", []),
                    fault_types=ontology_result.get("fault_types", {}),
                    similar_cases=similar_result.get("similar_cases", []),
                    key_patterns=key_patterns,
                    log_entries=[],
                )
            except Exception as e:
                logger.warning(f"Reasoning failed: {e}")
                reasoning_result = {"root_causes": [], "primary_cause": "Unknown"}

            # 步骤5: 报告生成
            try:
                report_result = await report_agent.execute(
                    analysis_id=f"chat_{ctx.session_id}",
                    db_type=ctx.db_type or "unknown",
                    root_causes=reasoning_result.get("root_causes", []),
                    similar_cases=similar_result.get("similar_cases", []),
                    key_errors=key_errors,
                    log_summary=log_summary,
                )
                ctx.analysis_done = True
                return report_result.get("report_markdown", "分析失败")
            except Exception as e:
                logger.error(f"Report generation failed: {e}")
                return f"❌ 报告生成失败: {str(e)}"

        except Exception as e:
            logger.error(f"Analysis pipeline failed: {e}", exc_info=True)
            return f"❌ 分析过程出错: {str(e)}"

    async def stream_response(
        self, session_id: str, user_message: str
    ) -> AsyncGenerator[str, None]:
        """流式生成对话响应"""
        ctx = self.get_session(session_id)
        if not ctx:
            yield f"error: Session {session_id} not found"
            return

        # 1. 添加用户消息到历史
        ctx.messages.append(HumanMessage(content=user_message))

        # 2. 从消息中自动检测DB类型和问题描述
        detected_db_type = self._detect_db_type(user_message)
        if detected_db_type:
            ctx.db_type = detected_db_type

        if user_message and not ctx.problem_description:
            ctx.problem_description = self._extract_problem_description(user_message)

        # 3. 评估上下文是否足以进行分析
        assessment = self._assess_context(ctx)

        # 4. 构建消息列表用于LLM调用
        messages = [SystemMessage(content=self.system_prompt)]
        messages.extend(ctx.messages)

        # 5. 根据上下文决定是否运行分析管道
        accumulated = ""

        if assessment["ready_for_analysis"] and ctx.document_content:
            # 有足够信息且有日志文档 → 运行分析
            analysis_result = await self._run_analysis_pipeline(ctx)
            full_response = (
                f"## 分析完成\n\n我已经接收到您上传的日志文件"
                f"（{ctx.uploaded_filename}），现在为您进行根因分析：\n\n"
                f"{analysis_result}"
            )
            accumulated = full_response

            # 逐字符流式输出
            for char in full_response:
                yield char

        else:
            # 信息不完整或没有日志 → 对话式引导
            # 构建对话提示
            if not assessment["ready_for_analysis"]:
                follow_up = f"请您补充以下信息（缺少: {', '.join(assessment['missing'])}）"
            elif assessment["need_document"]:
                follow_up = (
                    "我已经了解了您的问题，现在请上传相关的日志文件，"
                    "这样我可以进行更深入的分析。"
                )
            else:
                follow_up = "请提供更多详细信息"

            # 使用LLM生成对话回应
            try:
                async for chunk in self.llm.astream(messages):
                    if chunk.content:
                        accumulated += chunk.content
                        yield chunk.content
            except Exception as e:
                logger.error(f"LLM streaming error: {e}")
                yield f"\n\n❌ 生成回应失败: {str(e)}"
                return

        # 6. 将AI响应添加到历史
        ctx.messages.append(AIMessage(content=accumulated))


# 全局Chat Agent实例
chat_agent = ChatAgent()
