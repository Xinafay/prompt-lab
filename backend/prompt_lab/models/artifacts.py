from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


JsonObject = dict[str, Any]


class TemplateConfig(BaseModel):
    """Prompt template configuration for an experiment version."""

    model_config = ConfigDict(extra="forbid")

    engine: Literal["jinja2", "jinjax"] = "jinjax"
    path: str = "prompt.md"


class OutputConfig(BaseModel):
    """Output mode for an experiment."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["text", "pydantic"]
    model_file: str | None = Field(default=None, min_length=1)
    model_entrypoint: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_mode_fields(self) -> Self:
        if self.type == "pydantic":
            if self.model_file is None or self.model_entrypoint is None:
                raise ValueError(
                    "pydantic output requires model_file and model_entrypoint"
                )
        elif self.model_file is not None or self.model_entrypoint is not None:
            raise ValueError("text output cannot include pydantic-only fields")
        return self


class ModelConfig(BaseModel):
    """Generator, validator, and judge model references."""

    model_config = ConfigDict(extra="forbid")

    generator_model: str
    validator_model: str
    judge_model: str


class RunDefaults(BaseModel):
    """Default repeated-run behavior."""

    model_config = ConfigDict(extra="forbid")

    repeat_count: int = Field(default=3, ge=1)
    llm_cache: Literal["disabled"] = "disabled"
    case_order: Literal["case-major"] = "case-major"
    excluded_case_ids: list[str] = Field(default_factory=list)


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


class CaseArtifact(BaseModel):
    """One prompt input case."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    payload: JsonObject
    enabled: bool = True


class RunBatchArtifact(BaseModel):
    """Metadata for a batch of repeated runs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.run_batch/v1"]
    run_batch_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    status: Literal["running", "completed", "failed", "cancelled", "interrupted"]
    repeat_count: int = Field(ge=1)
    case_order: Literal["case-major"]
    llm_cache: Literal["disabled"]
    started_at: str
    finished_at: str | None = None
    total_runs: int = Field(ge=0)
    completed_runs: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.completed_runs > self.total_runs:
            raise ValueError("completed_runs cannot exceed total_runs")
        return self


class RunArtifact(BaseModel):
    """One generator output for one case/repeat."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["prompt_lab.run/v1"]
    run_id: str = Field(min_length=1)
    run_batch_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
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

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status == "validation_error":
            if self.validation_error is None:
                raise ValueError(
                    "validation_error status requires validation_error"
                )
            if self.execution_error is not None:
                raise ValueError(
                    "validation_error status cannot include execution_error"
                )
        elif self.status == "execution_error":
            if self.execution_error is None:
                raise ValueError("execution_error status requires execution_error")
            if self.validation_error is not None:
                raise ValueError(
                    "execution_error status cannot include validation_error"
                )
        elif self.validation_error is not None or self.execution_error is not None:
            raise ValueError(
                "ok status cannot include validation_error or execution_error"
            )
        return self

    @model_validator(mode="after")
    def validate_output_fields(self) -> Self:
        if self.output_type == "text":
            if self.status == "ok" and self.output_text is None:
                raise ValueError("ok text output requires output_text")
            if self.output_json is not None:
                raise ValueError("text output cannot include output_json")
        else:
            if self.status == "ok" and self.output_json is None:
                raise ValueError("ok pydantic output requires output_json")
            if self.output_text is not None:
                raise ValueError("pydantic output cannot include output_text")
        return self
