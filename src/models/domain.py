from pydantic import BaseModel, Field
from typing import List

class PageQuality(BaseModel):
    page_number: int
    quality: str
    issues: List[str] = Field(default_factory=list)

class QuestionGrade(BaseModel):
    question_id: str
    score: float
    max_score: float
    comment: str
    confidence: float = 0.0
    requires_teacher_review: bool = False

class CopyGrade(BaseModel):
    student_copy_id: str
    total_score: float
    max_score: float
    questions: List[QuestionGrade]
