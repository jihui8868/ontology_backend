"""推理 Agent - 综合图谱和案例进行根因推理"""

from typing import List, Dict, Any, Optional
import logging
import json
from langchain_anthropic import ChatAnthropic

logger = logging.getLogger(__name__)


class RootCauseHypothesis:
    """根因假设"""

    def __init__(
        self,
        rank: int,
        root_cause: str,
        fault_type: str,
        component: str,
        causal_chain: List[str],
        confidence: float,
        evidence: List[str],
        symptoms: List[str],
        resolutions: List[str],
    ):
        self.rank = rank
        self.root_cause = root_cause
        self.fault_type = fault_type
        self.component = component
        self.causal_chain = causal_chain
        self.confidence = confidence
        self.evidence = evidence
        self.symptoms = symptoms
        self.resolutions = resolutions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rank": self.rank,
            "root_cause": self.root_cause,
            "fault_type": self.fault_type,
            "component": self.component,
            "causal_chain": self.causal_chain,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "symptoms": self.symptoms,
            "resolutions": self.resolutions,
        }


class ReasoningAgent:
    """推理智能体 - 综合本体查询结果和相似案例进行根因分析"""

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-6")

    async def execute(
        self,
        ontology_matches: List[Dict[str, Any]],
        fault_types: Dict[str, Dict[str, Any]],
        similar_cases: List[Dict[str, Any]],
        key_patterns: List[str],
        log_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        根因推理分析

        Args:
            ontology_matches: 本体匹配的错误码列表
            fault_types: 故障类型及其因果链
            similar_cases: 相似历史案例
            key_patterns: 日志中的关键模式
            log_entries: 日志条目（用于证据提取）

        Returns:
            {
                'root_causes': List[RootCauseHypothesis],
                'primary_cause': str,
                'reasoning_summary': str,
                'confidence_score': float
            }
        """
        logger.info("Starting root cause reasoning...")

        # 第一步：提取证据
        evidence_dict = self._extract_evidence(log_entries or [])

        # 第二步：使用 LLM 进行推理
        reasoning_result = await self._llm_reasoning(
            ontology_matches, fault_types, similar_cases, key_patterns, evidence_dict
        )

        # 第三步：生成根因假设列表
        root_causes = self._generate_hypotheses(
            reasoning_result, fault_types, evidence_dict, similar_cases
        )

        # 排序：按置信度降序
        root_causes.sort(key=lambda x: x.confidence, reverse=True)

        # 重新标记排名
        for idx, cause in enumerate(root_causes):
            cause.rank = idx + 1

        primary_cause = root_causes[0].root_cause if root_causes else "Unknown"
        avg_confidence = (
            sum(cause.confidence for cause in root_causes) / len(root_causes)
            if root_causes
            else 0.0
        )

        logger.info(f"Generated {len(root_causes)} root cause hypotheses")

        return {
            "root_causes": [cause.to_dict() for cause in root_causes],
            "primary_cause": primary_cause,
            "reasoning_summary": reasoning_result.get("summary", ""),
            "confidence_score": avg_confidence,
        }

    def _extract_evidence(self, log_entries: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """从日志条目中提取证据"""
        evidence_dict = {
            "critical_errors": [],
            "repeated_patterns": [],
            "timestamps": [],
            "affected_components": [],
        }

        error_code_count = {}
        component_keywords = {
            "connection": ["connection", "connect", "pool"],
            "lock": ["deadlock", "lock", "wait"],
            "memory": ["memory", "oom", "buffer", "cache"],
            "disk": ["disk", "space", "full"],
            "index": ["index", "scan", "search"],
        }

        for entry in log_entries:
            message = entry.get("message", "").lower()
            level = entry.get("level", "")
            error_code = entry.get("error_code")

            # 收集错误码
            if error_code:
                error_code_count[error_code] = error_code_count.get(error_code, 0) + 1

            # 提取关键错误
            if level in ["ERROR", "FATAL", "PANIC"]:
                evidence_dict["critical_errors"].append(entry.get("message", "")[:100])

            # 识别组件关键词
            for component, keywords in component_keywords.items():
                if any(kw in message for kw in keywords):
                    evidence_dict["affected_components"].append(component)

        # 处理重复出现的错误码
        for code, count in sorted(error_code_count.items(), key=lambda x: x[1], reverse=True):
            if count >= 2:
                evidence_dict["repeated_patterns"].append(f"Error {code} ({count} times)")

        # 去重
        for key in evidence_dict:
            evidence_dict[key] = list(set(evidence_dict[key]))

        return evidence_dict

    async def _llm_reasoning(
        self,
        ontology_matches: List[Dict[str, Any]],
        fault_types: Dict[str, Dict[str, Any]],
        similar_cases: List[Dict[str, Any]],
        key_patterns: List[str],
        evidence: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """使用 LLM 进行推理"""
        try:
            prompt = f"""
基于以下信息进行数据库故障根因分析：

## 本体匹配错误码
{json.dumps(ontology_matches, ensure_ascii=False, indent=2)[:1000]}

## 故障类型及因果链
{json.dumps(fault_types, ensure_ascii=False, indent=2)[:1000]}

## 相似历史案例
{json.dumps(similar_cases[:3], ensure_ascii=False, indent=2)}

## 日志关键模式
{', '.join(key_patterns) if key_patterns else 'None'}

## 提取的证据
{json.dumps(evidence, ensure_ascii=False, indent=2)}

请进行以下分析：
1. 根据错误码和关键模式，最可能的根因是什么？
2. 根因与错误码之间的因果关系是什么？
3. 与历史案例的相似度如何影响分析？
4. 整体置信度是多少（0-1 之间）？

请用 JSON 格式返回：
{{
    "primary_hypothesis": "根因假设",
    "causal_relationship": "因果关系说明",
    "historical_relevance": "历史案例相关性",
    "confidence": 0.85,
    "summary": "简明总结（50 字以内）"
}}
"""
            response = self.llm.invoke(prompt)

            # 尝试解析 JSON
            try:
                result = json.loads(response.content)
                return result
            except json.JSONDecodeError:
                logger.warning("Failed to parse LLM response as JSON")
                return {
                    "primary_hypothesis": "LLM 推理失败",
                    "causal_relationship": "",
                    "historical_relevance": "",
                    "confidence": 0.5,
                    "summary": response.content[:100],
                }
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}")
            return {
                "primary_hypothesis": "推理异常",
                "causal_relationship": "",
                "historical_relevance": "",
                "confidence": 0.0,
                "summary": f"Error: {str(e)[:50]}",
            }

    def _generate_hypotheses(
        self,
        reasoning_result: Dict[str, Any],
        fault_types: Dict[str, Dict[str, Any]],
        evidence: Dict[str, List[str]],
        similar_cases: List[Dict[str, Any]],
    ) -> List[RootCauseHypothesis]:
        """生成根因假设列表"""
        hypotheses = []

        # 第一个假设：基于 LLM 推理的主要假设
        for fault_type, chain in fault_types.items():
            root_causes = chain.get("root_causes", [])
            symptoms = chain.get("symptoms", [])
            resolutions = chain.get("resolutions", [])
            component = chain.get("component", "Unknown")

            confidence = reasoning_result.get("confidence", 0.5)

            # 如果有相似案例，增加置信度
            if similar_cases:
                confidence = min(0.95, confidence + 0.1)

            hypothesis = RootCauseHypothesis(
                rank=1,  # 临时排名
                root_cause=root_causes[0] if root_causes else reasoning_result.get(
                    "primary_hypothesis", "Unknown"
                ),
                fault_type=fault_type,
                component=component,
                causal_chain=[root_causes[0], fault_type] + symptoms if root_causes else [fault_type],
                confidence=confidence,
                evidence=evidence.get("critical_errors", [])[:3],
                symptoms=symptoms[:3],
                resolutions=resolutions[:3],
            )

            hypotheses.append(hypothesis)

        # 如果没有从本体图谱生成假设，基于 LLM 生成一个
        if not hypotheses:
            hypothesis = RootCauseHypothesis(
                rank=1,
                root_cause=reasoning_result.get("primary_hypothesis", "Unknown Root Cause"),
                fault_type="Unknown",
                component="Unknown",
                causal_chain=[reasoning_result.get("primary_hypothesis", "Unknown")],
                confidence=reasoning_result.get("confidence", 0.5),
                evidence=evidence.get("critical_errors", [])[:3],
                symptoms=[],
                resolutions=[],
            )
            hypotheses.append(hypothesis)

        return hypotheses


reasoning_agent = ReasoningAgent()
