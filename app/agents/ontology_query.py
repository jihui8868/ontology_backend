"""本体查询 Agent - 查询 Neo4j 知识图谱匹配故障类型"""

from typing import List, Dict, Any, Optional
import logging
from app.db import neo4j_client

logger = logging.getLogger(__name__)


class OntologyMatch:
    """本体匹配结果"""

    def __init__(
        self,
        error_code: str,
        description: str,
        fault_type: str,
        component: str,
        confidence: float,
    ):
        self.error_code = error_code
        self.description = description
        self.fault_type = fault_type
        self.component = component
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "description": self.description,
            "fault_type": self.fault_type,
            "component": self.component,
            "confidence": self.confidence,
        }


class OntologyQueryAgent:
    """本体查询智能体 - 从 Neo4j 图数据库查询错误码和故障类型的关系"""

    def __init__(self):
        self.neo4j_client = neo4j_client

    async def execute(
        self,
        error_codes: List[str],
        db_type: str,
        key_patterns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        查询本体知识图谱

        Args:
            error_codes: 从日志中提取的错误码列表
            db_type: 数据库类型 ('postgresql' 或 'mysql')
            key_patterns: 日志中识别的关键模式

        Returns:
            {
                'matches': List[OntologyMatch],
                'fault_types': Dict[str, CausalChain],
                'related_faults': List[str],
                'resolutions': List[str]
            }
        """
        logger.info(f"Querying ontology for {len(error_codes)} error codes...")

        matches = []
        fault_types_dict = {}
        all_resolutions = set()

        # 查询每个错误码
        for error_code in error_codes:
            match = await self._query_error_code(error_code, db_type)
            if match:
                matches.append(match)

                # 查询对应的故障类型链
                if match.fault_type not in fault_types_dict:
                    chain = await self._query_fault_chain(match.fault_type, db_type)
                    fault_types_dict[match.fault_type] = chain

                    # 收集所有修复建议
                    all_resolutions.update(chain.get("resolutions", []))

        # 查询相关的故障类型（基于关键模式）
        related_faults = await self._query_related_faults(fault_types_dict.keys(), db_type)

        logger.info(f"Found {len(matches)} ontology matches")

        return {
            "matches": [m.to_dict() for m in matches],
            "fault_types": fault_types_dict,
            "related_faults": related_faults,
            "resolutions": list(all_resolutions)[:10],  # 最多返回 10 个修复建议
        }

    async def _query_error_code(self, error_code: str, db_type: str) -> Optional[OntologyMatch]:
        """查询单个错误码"""
        try:
            query = """
            MATCH (e:ErrorCode {code: $code, db: $db_type})
            OPTIONAL MATCH (e)-[:BELONGS_TO]->(f:FaultType)
            RETURN {
                code: e.code,
                description: e.description,
                fault_type: f.name,
                component: f.component
            } as result
            """
            result = await self.neo4j_client.execute_query(
                query, {"code": error_code, "db_type": db_type}
            )

            if result and result[0].get("result"):
                data = result[0]["result"]
                # 置信度：如果找到错误码则为 0.9，否则为 0
                confidence = 0.9 if data.get("fault_type") else 0.5
                return OntologyMatch(
                    error_code=data.get("code", error_code),
                    description=data.get("description", "Unknown error"),
                    fault_type=data.get("fault_type", "Unknown"),
                    component=data.get("component", "Unknown"),
                    confidence=confidence,
                )

            return None
        except Exception as e:
            logger.error(f"Failed to query error code {error_code}: {e}")
            return None

    async def _query_fault_chain(self, fault_type: str, db_type: str) -> Dict[str, Any]:
        """查询故障类型的因果链"""
        try:
            query = """
            MATCH (f:FaultType {name: $fault_type, db: $db_type})
            OPTIONAL MATCH (f)-[:CAUSED_BY]->(rc:RootCause)
            OPTIONAL MATCH (f)-[:MANIFESTS_AS]->(s:Symptom)
            OPTIONAL MATCH (f)-[:RESOLVED_BY]->(res:Resolution)
            RETURN {
                fault_type: f.name,
                component: f.component,
                root_causes: collect(DISTINCT rc.name),
                symptoms: collect(DISTINCT s.name),
                resolutions: collect(DISTINCT res.action)
            } as chain
            """
            result = await self.neo4j_client.execute_query(
                query, {"fault_type": fault_type, "db_type": db_type}
            )

            if result:
                return result[0].get("chain", {})

            return {
                "fault_type": fault_type,
                "component": "Unknown",
                "root_causes": [],
                "symptoms": [],
                "resolutions": [],
            }
        except Exception as e:
            logger.error(f"Failed to query fault chain for {fault_type}: {e}")
            return {}

    async def _query_related_faults(
        self, fault_types: List[str], db_type: str
    ) -> List[str]:
        """查询相关的故障类型"""
        if not fault_types:
            return []

        try:
            related = set()

            for fault_type in fault_types:
                query = """
                MATCH (f:FaultType {name: $fault_type, db: $db_type})
                OPTIONAL MATCH (f)-[:RELATED_TO]->(rf:FaultType)
                RETURN collect(DISTINCT rf.name) as related_faults
                """
                result = await self.neo4j_client.execute_query(
                    query, {"fault_type": fault_type, "db_type": db_type}
                )

                if result:
                    faults = result[0].get("related_faults", [])
                    related.update(f for f in faults if f)

            return list(related)
        except Exception as e:
            logger.error(f"Failed to query related faults: {e}")
            return []

    async def build_causal_chain(
        self, fault_type: str, root_causes: List[str], symptoms: List[str]
    ) -> List[str]:
        """构建因果链"""
        if not root_causes:
            return [fault_type]

        # 简单的因果链：RootCause -> FaultType -> Symptom
        causal_chain = []

        if root_causes:
            causal_chain.append(f"{root_causes[0]} (根因)")

        causal_chain.append(f"{fault_type} (故障类型)")

        if symptoms:
            causal_chain.append(f"{symptoms[0]} (症状)")

        return causal_chain


ontology_query_agent = OntologyQueryAgent()
