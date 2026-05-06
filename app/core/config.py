from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application
    environment: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Neo4j
    neo4j_uri: str = "bolt://192.168.2.133:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "Kylin123$"
    neo4j_timeout: int = 30

    # Milvus
    milvus_host: str = "192.168.2.133"
    milvus_port: int = 19530
    milvus_user: str = "minioadmin"
    milvus_password: str = "minioadmin"

    # LLM - Anthropic (legacy)
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"

    # LLM - Deepseek
    deepseek_api_key: str = "sk-cdc20dfe3ce744cdbec75961e87b7336"
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # File Storage
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 50

    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()
