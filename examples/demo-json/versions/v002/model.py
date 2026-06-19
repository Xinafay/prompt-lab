from pydantic import BaseModel, Field


class DemoReport(BaseModel):
    summary: str
    tags: list[str] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    launch_ready: bool
