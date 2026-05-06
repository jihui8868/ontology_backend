from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class MilvusClient:
    def __init__(self):
        self.host = settings.milvus_host
        self.port = settings.milvus_port
        self.user = settings.milvus_user
        self.password = settings.milvus_password
        self.collection_name = "fault_cases"
        self.embedding_dim = 768  # Claude embedding dimension

    def connect(self):
        """Initialize Milvus connection."""
        try:
            connections.connect(
                alias="default",
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
            )
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise

    def disconnect(self):
        """Close Milvus connection."""
        try:
            connections.disconnect(alias="default")
            logger.info("Milvus connection closed")
        except Exception as e:
            logger.error(f"Failed to disconnect from Milvus: {e}")

    def create_collection_if_not_exists(self) -> bool:
        """Create fault_cases collection if it doesn't exist."""
        try:
            if utility.has_collection(self.collection_name, using="default"):
                logger.info(f"Collection {self.collection_name} already exists")
                return True

            # Define fields
            fields = [
                FieldSchema(
                    name="case_id",
                    dtype=DataType.VARCHAR,
                    max_length=256,
                    is_primary=True,
                ),
                FieldSchema(
                    name="db_type",
                    dtype=DataType.VARCHAR,
                    max_length=50,
                ),
                FieldSchema(
                    name="summary_embedding",
                    dtype=DataType.FLOAT_VECTOR,
                    dim=self.embedding_dim,
                ),
                FieldSchema(
                    name="raw_log_snippet",
                    dtype=DataType.VARCHAR,
                    max_length=65535,
                ),
                FieldSchema(
                    name="root_cause",
                    dtype=DataType.VARCHAR,
                    max_length=500,
                ),
                FieldSchema(
                    name="resolution",
                    dtype=DataType.VARCHAR,
                    max_length=1000,
                ),
                FieldSchema(
                    name="created_at",
                    dtype=DataType.INT64,
                ),
            ]

            schema = CollectionSchema(
                fields=fields,
                description="Collection for storing fault analysis cases",
            )

            collection = Collection(
                name=self.collection_name,
                schema=schema,
                using="default",
            )

            # Create index on embedding field
            collection.create_index(
                field_name="summary_embedding",
                index_params={
                    "metric_type": "L2",
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 128},
                },
            )

            logger.info(f"Created collection {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            return False

    def insert_case(
        self,
        case_id: str,
        db_type: str,
        summary_embedding: List[float],
        raw_log_snippet: str,
        root_cause: str,
        resolution: str,
    ) -> bool:
        """Insert a fault case into Milvus."""
        try:
            collection = Collection(
                name=self.collection_name,
                using="default",
            )

            data = [
                [case_id],
                [db_type],
                [summary_embedding],
                [raw_log_snippet],
                [root_cause],
                [resolution],
                [int(datetime.now().timestamp())],
            ]

            collection.insert(data)
            collection.flush()
            logger.info(f"Inserted case {case_id} into Milvus")
            return True
        except Exception as e:
            logger.error(f"Failed to insert case: {e}")
            return False

    def search_similar_cases(
        self,
        query_embedding: List[float],
        db_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search for similar fault cases."""
        try:
            collection = Collection(
                name=self.collection_name,
                using="default",
            )

            search_params = {
                "metric_type": "L2",
                "params": {"nprobe": 10},
            }

            # Build filter expression if db_type is specified
            expr = None
            if db_type:
                expr = f'db_type == "{db_type}"'

            results = collection.search(
                data=[query_embedding],
                anns_field="summary_embedding",
                param=search_params,
                limit=top_k,
                expr=expr,
                output_fields=[
                    "case_id",
                    "db_type",
                    "root_cause",
                    "resolution",
                    "created_at",
                ],
            )

            similar_cases = []
            for hit in results[0]:
                similar_cases.append(
                    {
                        "case_id": hit.entity.get("case_id"),
                        "db_type": hit.entity.get("db_type"),
                        "root_cause": hit.entity.get("root_cause"),
                        "resolution": hit.entity.get("resolution"),
                        "similarity": float(1 / (1 + hit.distance)),  # Convert L2 to similarity
                    }
                )

            logger.info(f"Found {len(similar_cases)} similar cases")
            return similar_cases
        except Exception as e:
            logger.error(f"Failed to search similar cases: {e}")
            return []


milvus_client = MilvusClient()
