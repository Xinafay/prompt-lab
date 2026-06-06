from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JsonObject = dict[str, Any]


class TemplateConfig(BaseModel):
    """Prompt template configuration for an experiment version."""

    model_config = ConfigDict(extra="forbid")

    engine: Literal["jinja2"] = "jinja2"
    path: str = "prompt.md"


class OutputConfig(BaseModel):
    """Output mode for an experiment."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "pydantic"]
    model_file: str | None = None
    model_entrypoint: str | None = None
    validation_context_from_case: str | None = None


class ModelConfig(BaseModel):
    """Generator and judge model references."""

    model_config = ConfigDict(extra="forbid")

    generator_model: str
    judge_model: str


class RunDefaults(BaseModel):
    """Default repeated-run behavior."""

    model_config = ConfigDict(extra="forbid")

    repeat_count: int = Field(default=3, ge=1)
    llm_cache: Literal["disabled"] = "disabled"
    case_order: Literal["case-major"] = "case-major"


class ExperimentArtifact(BaseModel):
    """Experiment manifest stored as `experiment.json`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.experiment/v1"]
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = ""
    active_version: str = Field(min_length=1)
    output: OutputConfig
    template: TemplateConfig
    models: ModelConfig
    run_defaults: RunDefaults = Field(default_factory=RunDefaults)


class CaseSource(BaseModel):
    """Optional source metadata for imported cases."""

    model_config = ConfigDict(extra="allow")

    type: str | None = None


class CaseArtifact(BaseModel):
    """One prompt input case."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.case/v1"]
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source: CaseSource | None = None
    variables: JsonObject
    structured_validation_context: JsonObject | None = None


class RunBatchArtifact(BaseModel):
    """Metadata for a batch of repeated runs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.run_batch/v1"]
    run_batch_id: str
    version: str
    status: Literal["running", "completed", "failed", "cancelled", "interrupted"]
    repeat_count: int = Field(ge=1)
    case_order: Literal["case-major"]
    llm_cache: Literal["disabled"]
    started_at: str
    finished_at: str | None = None
    total_runs: int
    completed_runs: int


class RunArtifact(BaseModel):
    """One generator output for one case/repeat."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.run/v1"]
    run_id: str
    run_batch_id: str
    version: str
    case_id: str
    repeat_index: int = Field(ge=1)
    generator_model: str
    status: Literal["ok", "validation_error", "execution_error"]
    rendered_prompt: str
    raw_output: str | None = None
    output_type: Literal["text", "pydantic"]
    output_json: Any = None
    output_text: str | None = None
    validation_error: str | None = None
    execution_error: str | None = None
    usage: JsonObject = Field(default_factory=dict)
