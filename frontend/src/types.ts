export type OutputType = "text" | "pydantic";
export type TemplateEngine = "jinja2" | "jinjax";

export interface TextOutputConfig {
  type: "text";
}

export interface PydanticOutputConfig {
  type: "pydantic";
  model_file?: string | null;
  model_entrypoint?: string | null;
}

export type OutputConfig = TextOutputConfig | PydanticOutputConfig;

export interface FlatFileTreeStore {
  kind: "flat_file_tree";
  values: Record<string, unknown>;
}

export interface StoreScopeBinding {
  kind: "store_scope";
  store: string;
  path: string;
}

export interface ValueBinding {
  kind: "value";
  value: unknown;
}

export type PromptBinding = StoreScopeBinding | ValueBinding;

export interface Experiment {
  schema_version: "prompt_lab.experiment/v1";
  id: string;
  title: string;
  description: string;
  active_version: string;
  output: OutputConfig;
  template: {
    engine: TemplateEngine;
    path: string;
  };
  models: {
    generator_model: string;
    validator_model: string;
    judge_model: string;
  };
  run_defaults: {
    repeat_count: number;
    llm_cache: "disabled";
    case_order: "case-major";
  };
}

export interface Case {
  schema_version: "prompt_lab.case/v2";
  id: string;
  title: string;
  source?: Record<string, unknown> | null;
  stores: Record<string, FlatFileTreeStore>;
  bindings: Record<string, PromptBinding>;
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
  status: "running" | "completed" | "failed" | "cancelled";
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
  model_py?: string | null;
  model_file?: string | null;
  rubric: string;
  cases: Case[];
  validators: ValidatorDefinition[];
}

export type VersionSourceSaveMode = "create_next" | "overwrite_current";

export interface VersionSourceDraft {
  prompt: string;
  model_py?: string | null;
}

export interface VersionSourceUpdateRequest extends VersionSourceDraft {
  mode: VersionSourceSaveMode;
}

export interface VersionSourceUpdateResponse {
  version: string;
  source_version: string;
  mode: VersionSourceSaveMode;
  version_dir: string;
}

export interface VersionSummary {
  version: string;
  is_active: boolean;
}

export interface VersionsResponse {
  active_version: string;
  versions: VersionSummary[];
}

export interface RunsResponse {
  run_batch_id: string | null;
  runs: RunArtifact[];
}

export type WorkflowMode = "live" | "dry-run";

export interface RunVersionRequest {
  dry_run?: boolean;
}

export interface PromptPreviewItem {
  kind: string;
  title: string;
  model: string;
  prompt: string;
  character_count: number;
  word_count: number;
  case_id?: string | null;
  repeat_index?: number | null;
  validator_id?: string | null;
}

export interface PromptPreviewResponse {
  workflow_kind: string;
  prompts: PromptPreviewItem[];
  warnings: string[];
}

export interface GlobalSettings {
  schema_version: "prompt_lab.settings/v1";
  default_generator_model: string;
  default_validator_model: string;
  default_judge_model: string;
  default_repeat_count: number;
}

export type ValidatorType = "llm_questionnaire" | "automatic";

export type InputScope =
  | "output_only"
  | "output_and_prompt"
  | "output_and_case"
  | "output_prompt_and_case";

export type ValidationBatchStatus =
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export type NonNullValidationGrade = 1 | 2 | 3 | 4 | 5;

export type ValidationGrade = NonNullValidationGrade | null;

export type ValidationResultStatus = "ok" | "error" | "skipped";

export interface LlmValidatorCheck {
  check_id: string;
  title: string;
  question: string;
  description: string;
}

export interface CountComparison {
  op: "lt" | "lte" | "gt" | "gte" | "eq" | "between";
  value?: number | null;
  min_value?: number | null;
  max_value?: number | null;
}

export interface AutomaticRule {
  kind:
    | "word_count"
    | "sentence_count"
    | "character_count"
    | "json_path_count"
    | "json_path_exists";
  source: "output_text" | "raw_output" | "output_json";
  path?: string | null;
  comparison?: CountComparison | null;
}

export interface AutomaticValidatorCheck {
  check_id: string;
  title: string;
  description: string;
  rule: AutomaticRule;
}

interface BaseValidatorDefinition {
  schema_version: "prompt_lab.validator/v1";
  validator_id: string;
  type: ValidatorType;
  title: string;
  description: string;
  enabled: boolean;
  input_scope: InputScope;
}

export interface LlmQuestionnaireValidatorDefinition
  extends BaseValidatorDefinition {
  type: "llm_questionnaire";
  checks: LlmValidatorCheck[];
}

export interface AutomaticValidatorDefinition extends BaseValidatorDefinition {
  type: "automatic";
  checks: AutomaticValidatorCheck[];
}

export type ValidatorDefinition =
  | LlmQuestionnaireValidatorDefinition
  | AutomaticValidatorDefinition;

export interface ValidationBatch {
  schema_version: "prompt_lab.validation_batch/v1";
  validation_batch_id: string;
  run_batch_id: string;
  version: string;
  status: ValidationBatchStatus;
  started_at: string;
  finished_at?: string | null;
  total_results: number;
  completed_results: number;
  validator_model: string;
  validator_ids: string[];
}

export interface ValidationCheckResult {
  check_id: string;
  grade: ValidationGrade;
  comment: string;
  included_in_judge: boolean;
  metrics: Record<string, unknown>;
}

export interface ValidationResult {
  schema_version: "prompt_lab.validation_result/v1";
  validation_result_id: string;
  validation_batch_id: string;
  run_batch_id: string;
  run_id: string;
  case_id: string;
  repeat_index: number;
  validator_id: string;
  validator_type: ValidatorType;
  status: ValidationResultStatus;
  included_in_judge: boolean;
  check_results: ValidationCheckResult[];
  usage: Record<string, unknown>;
  execution_error?: string | null;
}

export interface ValidationState {
  validation_batch: ValidationBatch;
  validators: ValidatorDefinition[];
  results: ValidationResult[];
}

export interface ValidationCheckInclusionUpdate {
  check_id: string;
  included_in_judge: boolean;
}

export interface ValidationResultInclusionUpdate {
  validation_result_id: string;
  included_in_judge: boolean;
  check_results: ValidationCheckInclusionUpdate[];
}

export interface ValidationInclusionUpdate {
  results: ValidationResultInclusionUpdate[];
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
  validation_batch_id: string;
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

export type ComparisonStatus = "pass" | "fail" | "mixed" | "empty";

export type CompareDetailStatus = "graded" | "not_assessable" | "error";

interface BaseCompareCellDetail {
  case_id: string;
  repeat_index: number;
  validation_result_id: string;
  comment: string;
}

export type CompareCellDetail =
  | (BaseCompareCellDetail & {
      status: "graded";
      grade: NonNullValidationGrade;
    })
  | (BaseCompareCellDetail & {
      status: "error";
      grade: null;
    })
  | (BaseCompareCellDetail & {
      status: "not_assessable";
      grade: null;
    });

export interface CompareMatrixCell {
  version: string;
  status: ComparisonStatus;
  grade_5: number;
  grade_4: number;
  grade_3: number;
  grade_2: number;
  grade_1: number;
  not_assessable: number;
  missing: number;
  error: number;
  total: number;
  details: CompareCellDetail[];
}

export interface CompareMatrixRow {
  validator_id: string;
  validator_title: string;
  check_id: string;
  check_title: string;
  check_description: string;
  cells: CompareMatrixCell[];
}

export interface CompareMatrixResponse {
  schema_version: "prompt_lab.compare_matrix/v1";
  experiment_id: string;
  versions: string[];
  rows: CompareMatrixRow[];
}

export type ComparisonResponse = CompareMatrixResponse;
