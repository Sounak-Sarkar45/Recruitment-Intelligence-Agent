from typing import TypedDict, Dict, Any

class AgentState(TypedDict):
    job_description: str
    jd_summary: Dict[str, str]
    resume_file: str
    resume_text: str
    resume_summary: Dict[str, str]
    attribute_scores: Dict[str, float]
    similarity_score: float
    rating: str
    comments: str
