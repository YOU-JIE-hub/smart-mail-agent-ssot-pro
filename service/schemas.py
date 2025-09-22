from typing import List, Literal, Optional
from pydantic import BaseModel, Field

Task = Literal["intent", "spam"]

class PredictIn(BaseModel):
    task: Task = Field(description="intent|spam")
    text: str = Field(min_length=1)
    top_k: int = Field(3, ge=1, le=10)

class TopKItem(BaseModel):
    label: str
    p: float

class PredictOut(BaseModel):
    task: Task
    text: str
    pred: Optional[str] = None
    topk: List[TopKItem] = []
    abstained: bool = False
