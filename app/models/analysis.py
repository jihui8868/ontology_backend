from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class AnalysisCreate(BaseModel):
    filename: str
    db_type: str


class AnalysisStatus(BaseModel):
    analysis_id: str
    status: str  # queued, parsing, ontology, similar_cases, reasoning, report_generation, completed, failed
    db_type: Optional[str] = None
    progress: int = 0
    message: Optional[str] = None


class AnalysisUploadResponse(BaseModel):
    analysis_id: str
    status: str
    db_type: str


class LogEntry(BaseModel):
    timestamp: datetime
    level: str  # ERROR, WARNING, INFO, DEBUG, FATAL, PANIC
    error_code: Optional[str] = None
    message: str
    line_number: int


class AnalysisHistoryItem(BaseModel):
    analysis_id: str
    filename: str
    db_type: str
    created_at: datetime
    primary_root_cause: Optional[str] = None
    status: str


class AnalysisHistoryResponse(BaseModel):
    items: List[AnalysisHistoryItem]
    total: int
