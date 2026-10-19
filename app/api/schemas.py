from pydantic import BaseModel


class ProgressEvent(BaseModel):
    stage: str
    progress: float
    message: str
    timestamp: float
