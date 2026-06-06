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

export type FindingSeverity =
  | "recommended"
  | "optional"
  | "do_not_change_yet"
  | "regression_risk";

export type FindingDecisionValue = "accepted" | "rejected" | "deferred";

export interface EvidenceFinding {
  finding_id: string;
  description: string;
  evidence: string[];
}

export interface JudgmentFinding {
  finding_id: string;
  severity: FindingSeverity;
  area: string;
  category: string;
  description: string;
  evidence: string[];
  suggested_change: string;
}

export interface DecisionPoint {
  decision_id: string;
  description: string;
  options: string[];
  recommended_option: string;
}

export interface JudgmentArtifact {
  schema_version: "prompt_lab.judgment/v1";
  judgment_id: string;
  version: string;
  run_batch_ids: string[];
  judge_model: string;
  summary: string;
  what_looks_correct: EvidenceFinding[];
  findings: JudgmentFinding[];
  decision_points: DecisionPoint[];
}

export interface FindingDecision {
  decision: FindingDecisionValue;
  reason?: string | null;
}

export interface FindingDecisionSet {
  schema_version: "prompt_lab.decisions/v1";
  finding_decisions: Record<string, FindingDecision>;
}

export interface ReviewState {
  review_id: string;
  judgment: JudgmentArtifact;
  decisions: FindingDecisionSet;
  human_notes: string;
  judgment_markdown: string;
  rubric_snapshot: string;
}

export interface JudgmentResponse {
  review_id: string;
  run_batch_id: string;
  judgment: JudgmentArtifact;
}

export interface ProposalDraft {
  prompt_md: string;
  model_py?: string | null;
  rationale_md: string;
}

export interface ProposalResponse {
  proposal_dir: string;
  proposal: ProposalDraft;
  source: Record<string, unknown>;
}

export interface CreatedVersionResponse {
  version: string;
  source_version: string;
  review_id: string;
  version_dir: string;
}

export type ComparisonRecommendation =
  | "keep_new_version"
  | "revise_new_version"
  | "revert_to_baseline"
  | "inconclusive";

export interface ComparisonArtifact {
  schema_version: "prompt_lab.comparison/v1";
  comparison_id: string;
  baseline_version: string;
  candidate_version: string;
  baseline_run_batch_ids: string[];
  candidate_run_batch_ids: string[];
  judge_model: string;
  summary: string;
  improvements: string[];
  regressions: string[];
  unchanged_problems: string[];
  new_problems: string[];
  stability_changes: string[];
  recommendation: ComparisonRecommendation;
  decision_points: DecisionPoint[];
}

export interface ComparisonResponse {
  comparison_id: string;
  baseline_run_batch_id: string;
  candidate_run_batch_id: string;
  comparison: ComparisonArtifact;
}
