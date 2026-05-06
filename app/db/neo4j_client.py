from neo4j import AsyncGraphDatabase, AsyncSession
from typing import Optional, List, Dict, Any
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    def __init__(self):
        self.uri = settings.neo4j_uri
        self.username = settings.neo4j_username
        self.password = settings.neo4j_password
        self.timeout = settings.neo4j_timeout
        self.driver = None

    async def connect(self):
        """Initialize Neo4j connection."""
        try:
            self.driver = AsyncGraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password),
                connection_timeout=self.timeout,
            )
            await self.driver.verify_connectivity()
            logger.info(f"Connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    async def close(self):
        """Close Neo4j connection."""
        if self.driver:
            await self.driver.close()
            logger.info("Neo4j connection closed")

    async def execute_query(
        self, query: str, parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results."""
        async with self.driver.session() as session:
            result = await session.run(query, parameters or {})
            records = await result.fetch(0)
            return [dict(record) for record in records]

    async def query_error_code(self, error_code: str, db_type: str) -> Optional[Dict]:
        """Query error code details from ontology."""
        query = """
        MATCH (e:ErrorCode {code: $code, db: $db_type})
        OPTIONAL MATCH (e)-[:BELONGS_TO]->(f:FaultType)
        RETURN {
            code: e.code,
            description: e.description,
            fault_type: f.name
        } as result
        """
        result = await self.execute_query(query, {"code": error_code, "db_type": db_type})
        return result[0]["result"] if result else None

    async def query_fault_type_chain(self, fault_type: str, db_type: str) -> Dict:
        """Query fault type and its causal chain."""
        query = """
        MATCH (f:FaultType {name: $fault_type, db: $db_type})
        OPTIONAL MATCH (f)-[:CAUSED_BY]->(rc:RootCause)
        OPTIONAL MATCH (f)-[:MANIFESTS_AS]->(s:Symptom)
        OPTIONAL MATCH (f)-[:RESOLVED_BY]->(res:Resolution)
        RETURN {
            fault_type: f.name,
            root_causes: collect(DISTINCT rc.name),
            symptoms: collect(DISTINCT s.name),
            resolutions: collect(DISTINCT res.action)
        } as chain
        """
        result = await self.execute_query(
            query, {"fault_type": fault_type, "db_type": db_type}
        )
        return result[0]["chain"] if result else {}

    async def load_ontology_from_file(self, cypher_file: str) -> bool:
        """Load ontology from a Cypher file."""
        try:
            with open(cypher_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Split by semicolon and execute each statement
            statements = [s.strip() for s in content.split(";") if s.strip()]

            async with self.driver.session() as session:
                for statement in statements:
                    if statement:
                        await session.run(statement)

            logger.info(f"Loaded ontology from {cypher_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load ontology: {e}")
            return False


neo4j_client = Neo4jClient()
