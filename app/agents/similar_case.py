"""相似案例检索 Agent - 从 Milvus 向量库检索历史相似案例"""

from typing import List, Dict, Any, Optional
import logging
from langchain_anthropic import ChatAnthropic
import json

from app.db import milvus_client

logger = logging.getLogger(__name__)


class SimilarCaseAgent:
    """相似案例检索智能体 - 从 Milvus 检索相似历史案例"""

    def __init__(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-6")
        self.milvus_client = milvus_client

    async def execute(
        self,
        log_summary: str,
        db_type: str,
        key_errors: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        检索相似的历史故障案例

        Args:
            log_summary: 日志摘要（用于向量化）
            db_type: 数据库类型
            key_errors: 关键错误列表
            top_k: 返回的相似案例数量

        Returns:
            {
                'similar_cases': List[Dict],
                'query_embedding': List[float],
                'retrieved_count': int,
                'avg_similarity': float
            }
        """
        logger.info(f"Searching for similar cases ({top_k} results)...")

        # 生成查询向量
        query_embedding = await self._generate_embedding(log_summary)
        logger.info(f"Generated query embedding (dim={len(query_embedding)})")

        # 在 Milvus 中搜索
        similar_cases = self._search_milvus(query_embedding, db_type, top_k)

        # 计算平均相似度
        avg_similarity = (
            sum(case.get("similarity", 0) for case in similar_cases) / len(similar_cases)
            if similar_cases
            else 0.0
        )

        logger.info(f"Found {len(similar_cases)} similar cases (avg similarity: {avg_similarity:.2f})")

        return {
            "similar_cases": similar_cases,
            "query_embedding": query_embedding,
            "retrieved_count": len(similar_cases),
            "avg_similarity": avg_similarity,
        }

    async def _generate_embedding(self, text: str) -> List[float]:
        """使用 Claude 生成文本向量"""
        try:
            prompt = f"""
请为以下数据库故障日志摘要生成一个语义向量表示。
你的回复应该是一个 768 维的浮点数数组（JSON 格式），表示这段文本的语义特征。

日志摘要：
{text}

返回格式：[0.1, 0.2, ..., 0.3]（768 个数字）
"""
            response = self.llm.invoke(prompt)

            # 尝试解析 JSON 数组
            content = response.content.strip()

            # 尝试直接解析
            try:
                embedding = json.loads(content)
                if isinstance(embedding, list) and len(embedding) == 768:
                    return embedding
            except json.JSONDecodeError:
                pass

            # 备用：如果 LLM 没有返回正确格式，生成伪向量
            logger.warning("Failed to parse embedding from LLM, using fallback vector")
            return self._generate_fallback_embedding(text)

        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return self._generate_fallback_embedding(text)

    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """生成伪向量（基于文本的哈希和词频）"""
        import hashlib
        import random

        # 使用文本哈希作为随机种子
        seed = int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**31)
        random.seed(seed)

        # 生成 768 维的伪向量
        embedding = [random.gauss(0, 0.1) for _ in range(768)]

        # 标准化向量
        norm = sum(x**2 for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def _search_milvus(
        self, query_embedding: List[float], db_type: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """在 Milvus 中搜索相似案例"""
        try:
            cases = self.milvus_client.search_similar_cases(
                query_embedding=query_embedding, db_type=db_type, top_k=top_k
            )

            # 格式化结果
            formatted_cases = []
            for case in cases:
                formatted_cases.append(
                    {
                        "case_id": case.get("case_id"),
                        "db_type": case.get("db_type"),
                        "root_cause": case.get("root_cause"),
                        "resolution": case.get("resolution"),
                        "similarity": case.get("similarity", 0),
                    }
                )

            return formatted_cases
        except Exception as e:
            logger.error(f"Milvus search failed: {e}")
            return []

    async def store_current_case(
        self,
        analysis_id: str,
        db_type: str,
        log_summary: str,
        root_cause: str,
        resolution: str,
    ) -> bool:
        """存储当前分析案例到 Milvus（供后续检索）"""
        try:
            # 生成摘要向量
            summary_embedding = await self._generate_embedding(log_summary)

            # 截断摘要和解决方案
            log_snippet = log_summary[:500]
            resolution_text = resolution[:500]

            success = self.milvus_client.insert_case(
                case_id=analysis_id,
                db_type=db_type,
                summary_embedding=summary_embedding,
                raw_log_snippet=log_snippet,
                root_cause=root_cause,
                resolution=resolution_text,
            )

            if success:
                logger.info(f"Stored case {analysis_id} to Milvus")
            else:
                logger.warning(f"Failed to store case {analysis_id}")

            return success
        except Exception as e:
            logger.error(f"Failed to store case: {e}")
            return False


similar_case_agent = SimilarCaseAgent()
