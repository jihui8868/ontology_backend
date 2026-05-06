from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class RootCauseDetail(BaseModel):
    rank: int
    confidence: float
    fault_type: str
    component: str
    causal_chain: List[str]
    evidence_lines: List[int]
    symptoms: List[str]
    resolutions: List[str]


class SimilarCase(BaseModel):
    case_id: str
    db_type: str
    root_cause: str
    resolution: str
    similarity: float


class AnalysisReport(BaseModel):
    analysis_id: str
    db_type: str
    created_at: datetime
    log_time_range: Optional[Dict[str, str]] = None
    key_errors: List[Dict[str, Any]]
    root_causes: List[RootCauseDetail]
    similar_cases: List[SimilarCase]
    resolutions: List[str]
    report_markdown: str


class ReportResponse(BaseModel):
    analysis_id: str
    db_type: str
    created_at: datetime
    root_causes: List[RootCauseDetail]
    similar_cases: List[SimilarCase]
    resolutions: List[str]
    report_markdown: str
