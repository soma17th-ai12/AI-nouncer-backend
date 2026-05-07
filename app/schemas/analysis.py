from pydantic import BaseModel

class AlignmentItem(BaseModel):
    expected: str
    heard: str
    type: str

class Candidate(BaseModel):
    index: int
    expected: str
    heard: str
    type: str

class Advice(BaseModel):
    focus: str
    drills: list[str]
    next_sentence: str | None = None

class AnalysisResponse(BaseModel):
    """POST /api/v1/analyze 응답 스키마."""

    transcript: str
    alignment: list[AlignmentItem]
    candidates: list[Candidate]
    advice: Advice
