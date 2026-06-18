from pydantic import BaseModel
from typing import List, Dict, Any

class QueryRequest(BaseModel):
    user_id: int
    question: str
    context: Dict[str, Any] = {}

class QueryResponse(BaseModel):
    answer: str
    charts: List[Dict[str, Any]]
    status: str

class DashboardSummaryResponse(BaseModel):
    total_emissions_tCO2: float
    cbam_liabilities_eur: float
    top_emitting_supplier: str
    compliant_ratio: float
