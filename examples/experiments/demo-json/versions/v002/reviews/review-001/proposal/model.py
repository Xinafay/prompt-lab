from pydantic import BaseModel, Field


class DemoReport(BaseModel):
    summary: str
    tags: list[str] = Field(min_length=1, max_length=3)
    risks: list[str] = Field(default_factory=list, max_length=3)
    launch_ready: bool
