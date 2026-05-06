from pydantic import BaseModel
from typing import List, Optional


class ErrorCodeNode(BaseModel):
    code: str
    description: str
    db: str


class FaultTypeNode(BaseModel):
    name: str
    component: str
    db: str


class RootCauseNode(BaseModel):
    name: str


class SymptomNode(BaseModel):
    name: str


class ResolutionNode(BaseModel):
    action: str
    detail: Optional[str] = None


class CausalChain(BaseModel):
    fault_type: str
    root_causes: List[str]
    symptoms: List[str]
    resolutions: List[str]


class OntologyMatch(BaseModel):
    error_code: str
    description: str
    fault_type: str
    confidence: float
