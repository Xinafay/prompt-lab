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
