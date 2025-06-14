from typing import Optional
from pydantic import BaseModel, field_validator

class QueryRequest(BaseModel):
    question: str
    image: Optional[str] = None

    @field_validator("question")
    def question_length(cls, v):
        if len(v) > 2000:
            raise ValueError("Query too long. Limit to 2000 characters.")
        return v

    @field_validator("image")
    def image_size_limit(cls, v):
        if v and len(v) > 5_000_000:
            raise ValueError("Image input is too large. Limit to ~5MB base64 string.")
        return v
