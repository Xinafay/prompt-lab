export type OutputType = "text" | "pydantic";

export interface Experiment {
  schema_version: "prompt_lab.experiment/v1";
  id: string;
  title: string;
  description: string;
  active_version: string;
  output: {
    type: OutputType;
    model_file?: string | null;
    model_entrypoint?: string | null;
    validation_context_from_case?: string | null;
  };
  template: {
    engine: "jinja2";
    path: string;
  };
  models: {
    generator_model: string;
    judge_model: string;
  };
  run_defaults: {
    repeat_count: number;
    llm_cache: "disabled";
    case_order: "case-major";
  };
}

export interface Case {
  schema_version: "prompt_lab.case/v1";
  id: string;
  title: string;
  source?: Record<string, unknown> | null;
  variables: Record<string, unknown>;
  structured_validation_context?: Record<string, unknown> | null;
}

export interface RunArtifact {
  schema_version: "prompt_lab.run/v1";
  run_id: string;
  run_batch_id: string;
  version: string;
  case_id: string;
  repeat_index: number;
  generator_model: string;
  status: "ok" | "validation_error" | "execution_error";
  rendered_prompt: string;
  raw_output?: string | null;
  output_type: OutputType;
  output_json?: unknown;
  output_text?: string | null;
  validation_error?: string | null;
  execution_error?: string | null;
  usage: Record<string, unknown>;
}

export interface JobStatus {
  job_id: string;
  kind: string;
  experiment_id: string;
  version: string;
  status: "running" | "completed" | "failed";
  total_units: number;
  completed_units: number;
  message: string;
  started_at: string;
  finished_at?: string | null;
}

export interface JobEvent {
  event_id: number;
  job_id: string;
  status: JobStatus["status"];
  message: string;
  completed_units: number;
  total_units: number;
  created_at: string;
}

export interface VersionOverview {
  experiment: Experiment;
  version: string;
  prompt: string;
  rubric: string;
  cases: Case[];
}

export interface RunsResponse {
  run_batch_id: string | null;
  runs: RunArtifact[];
}
