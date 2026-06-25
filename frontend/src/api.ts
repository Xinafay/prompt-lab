import type {
  Case,
  CaseInclusionUpdateRequest,
  CaseInclusionUpdateResponse,
  CaseRunInclusionRequest,
  CaseSetUpdateRequest,
  CaseSetUpdateResponse,
  CaseSuite,
  CaseSuiteCasesUpdateResponse,
  CaseSuiteCreateRequest,
  CaseSuiteUpdateRequest,
  CaseUploadRequest,
  CompareMatrixResponse,
  CreatedVersionResponse,
  Experiment,
  ExperimentCloneRequest,
  ExperimentCreateRequest,
  ExperimentDeleteResponse,
  FindingDecisionSet,
  GlobalSettings,
  JobEvent,
  JobStatus,
  JudgmentResponse,
  PromptPreviewResponse,
  ProposalResponse,
  ReviewState,
  RunVersionRequest,
  RunsResponse,
  ValidationInclusionUpdate,
  ValidationState,
  VersionOverview,
  VersionSourceUpdateRequest,
  VersionSourceUpdateResponse,
  VersionValidatorsUpdateRequest,
  VersionValidatorsUpdateResponse,
  VersionsResponse
} from "./types";

function detailToMessage(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (
          item !== null &&
          typeof item === "object" &&
          "msg" in item &&
          typeof item.msg === "string"
        ) {
          return item.msg;
        }
        return null;
      })
      .filter((item): item is string => item !== null);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  return null;
}

async function readErrorMessage(response: Response): Promise<string> {
  const text = await response.text();
  if (text.trim().length === 0) {
    return `${response.status} ${response.statusText}`.trim();
  }
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed !== null && typeof parsed === "object" && "detail" in parsed) {
      const message = detailToMessage(parsed.detail);
      if (message !== null) return message;
    }
  } catch {
    return text;
  }
  return text;
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}

export function getVersionOverview(
  experimentId: string,
  version: string
): Promise<VersionOverview> {
  return apiGet<VersionOverview>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}`
  );
}

export function updateExperiment(
  experimentId: string,
  experiment: Experiment
): Promise<Experiment> {
  return apiPut<Experiment>(
    `/api/experiments/${encodeURIComponent(experimentId)}`,
    experiment
  );
}

export function createExperiment(
  request: ExperimentCreateRequest
): Promise<Experiment> {
  return apiPost<Experiment>("/api/experiments", request);
}

export function cloneExperiment(
  experimentId: string,
  request: ExperimentCloneRequest
): Promise<Experiment> {
  return apiPost<Experiment>(
    `/api/experiments/${encodeURIComponent(experimentId)}/clone`,
    request
  );
}

export function deleteExperiment(
  experimentId: string
): Promise<ExperimentDeleteResponse> {
  return apiDelete<ExperimentDeleteResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}`
  );
}

export function getCaseSuites(): Promise<CaseSuite[]> {
  return apiGet<CaseSuite[]>("/api/case-suites");
}

export function createCaseSuite(
  request: CaseSuiteCreateRequest
): Promise<CaseSuite> {
  return apiPost<CaseSuite>("/api/case-suites", request);
}

export function updateCaseSuite(
  suiteId: string,
  request: CaseSuiteUpdateRequest
): Promise<CaseSuite> {
  return apiPatch<CaseSuite>(
    `/api/case-suites/${encodeURIComponent(suiteId)}`,
    request
  );
}

export function deleteCaseSuite(suiteId: string): Promise<{ suite_id: string }> {
  return apiDelete<{ suite_id: string }>(
    `/api/case-suites/${encodeURIComponent(suiteId)}`
  );
}

export function getCaseSuiteCases(suiteId: string): Promise<Case[]> {
  return apiGet<Case[]>(
    `/api/case-suites/${encodeURIComponent(suiteId)}/cases`
  );
}

export function saveCaseSuiteCases(
  suiteId: string,
  request: { cases: CaseUploadRequest[] }
): Promise<CaseSuiteCasesUpdateResponse> {
  return apiPut<CaseSuiteCasesUpdateResponse>(
    `/api/case-suites/${encodeURIComponent(suiteId)}/cases`,
    request
  );
}

export function createCaseSuiteCase(
  suiteId: string,
  request: CaseUploadRequest
): Promise<CaseSuiteCasesUpdateResponse> {
  return apiPost<CaseSuiteCasesUpdateResponse>(
    `/api/case-suites/${encodeURIComponent(suiteId)}/cases`,
    request
  );
}

export function updateCaseSuiteCase(
  suiteId: string,
  caseId: string,
  request: CaseUploadRequest
): Promise<CaseSuiteCasesUpdateResponse> {
  return apiPut<CaseSuiteCasesUpdateResponse>(
    `/api/case-suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(
      caseId
    )}`,
    request
  );
}

export function deleteCaseSuiteCase(
  suiteId: string,
  caseId: string
): Promise<CaseSuiteCasesUpdateResponse> {
  return apiDelete<CaseSuiteCasesUpdateResponse>(
    `/api/case-suites/${encodeURIComponent(suiteId)}/cases/${encodeURIComponent(
      caseId
    )}`
  );
}

export function saveCaseInclusion(
  experimentId: string,
  request: CaseInclusionUpdateRequest
): Promise<CaseInclusionUpdateResponse> {
  return apiPut<CaseInclusionUpdateResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/case-inclusion`,
    request
  );
}

export function uploadCase(
  experimentId: string,
  request: CaseUploadRequest
): Promise<Case> {
  return apiPost<Case>(
    `/api/experiments/${encodeURIComponent(experimentId)}/cases`,
    request
  );
}

export function deleteCase(
  experimentId: string,
  caseId: string
): Promise<{ case_id: string }> {
  return apiDelete<{ case_id: string }>(
    `/api/experiments/${encodeURIComponent(experimentId)}/cases/${encodeURIComponent(
      caseId
    )}`
  );
}

export function updateCaseRunInclusion(
  experimentId: string,
  caseId: string,
  request: CaseRunInclusionRequest
): Promise<Case> {
  return apiPatch<Case>(
    `/api/experiments/${encodeURIComponent(experimentId)}/cases/${encodeURIComponent(
      caseId
    )}/run-inclusion`,
    request
  );
}

export function saveCases(
  experimentId: string,
  request: CaseSetUpdateRequest
): Promise<CaseSetUpdateResponse> {
  return apiPut<CaseSetUpdateResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/cases`,
    request
  );
}

export function getGlobalSettings(): Promise<GlobalSettings> {
  return apiGet<GlobalSettings>("/api/settings");
}

export function updateGlobalSettings(
  settings: GlobalSettings
): Promise<GlobalSettings> {
  return apiPut<GlobalSettings>("/api/settings", settings);
}

export function getExperimentVersions(
  experimentId: string
): Promise<VersionsResponse> {
  return apiGet<VersionsResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions`
  );
}

export function getVersionRuns(
  experimentId: string,
  version: string
): Promise<RunsResponse> {
  return apiGet<RunsResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/runs`
  );
}

export function runVersion(
  experimentId: string,
  version: string,
  request?: RunVersionRequest
): Promise<JobStatus> {
  return apiPost<JobStatus>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/runs`,
    request
  );
}

export function previewRunPrompts(
  experimentId: string,
  version: string
): Promise<PromptPreviewResponse> {
  return apiPost<PromptPreviewResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/runs/preview-prompts`
  );
}

export function validateVersion(
  experimentId: string,
  version: string,
  dryRun = false
): Promise<ValidationState> {
  return apiPost<ValidationState>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validations`,
    dryRun ? { dry_run: true } : undefined
  );
}

export function previewValidationPrompts(
  experimentId: string,
  version: string
): Promise<PromptPreviewResponse> {
  return apiPost<PromptPreviewResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validations/preview-prompts`
  );
}

export function getJob(jobId: string): Promise<JobStatus> {
  return apiGet<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export async function getActiveJob(): Promise<JobStatus | null> {
  const response = await apiGet<{ job: JobStatus | null }>("/api/jobs/active");
  return response.job;
}

export function cancelJob(jobId: string): Promise<JobStatus> {
  return apiPost<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`);
}

export function getJobEvents(jobId: string): Promise<JobEvent[]> {
  return apiGet<JobEvent[]>(`/api/jobs/${encodeURIComponent(jobId)}/events`);
}

export function jobEventsStreamUrl(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}/events/stream`;
}

export function judgeVersion(
  experimentId: string,
  version: string,
  dryRun = false
): Promise<JudgmentResponse> {
  return apiPost<JudgmentResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/judgments`,
    dryRun ? { dry_run: true } : undefined
  );
}

export function previewJudgePrompts(
  experimentId: string,
  version: string
): Promise<PromptPreviewResponse> {
  return apiPost<PromptPreviewResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/judgments/preview-prompts`
  );
}

export function getReviewState(
  experimentId: string,
  version: string,
  reviewId: string
): Promise<ReviewState> {
  return apiGet<ReviewState>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/${encodeURIComponent(reviewId)}`
  );
}

export async function getLatestReviewState(
  experimentId: string,
  version: string
): Promise<ReviewState | null> {
  const response = await fetch(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/latest`
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<ReviewState>;
}

export async function getLatestValidationState(
  experimentId: string,
  version: string
): Promise<ValidationState | null> {
  const response = await fetch(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validations/latest`
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<ValidationState>;
}

export function updateValidationInclusion(
  experimentId: string,
  version: string,
  validationBatchId: string,
  update: ValidationInclusionUpdate
): Promise<ValidationState> {
  return apiPut<ValidationState>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validations/${encodeURIComponent(validationBatchId)}/inclusion`,
    update
  );
}

export function updateReviewDecisions(
  experimentId: string,
  version: string,
  reviewId: string,
  decisions: FindingDecisionSet
): Promise<FindingDecisionSet> {
  return apiPut<FindingDecisionSet>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/${encodeURIComponent(reviewId)}/decisions`,
    decisions
  );
}

export function updateHumanNotes(
  experimentId: string,
  version: string,
  reviewId: string,
  notes: string
): Promise<{ human_notes: string }> {
  return apiPut<{ human_notes: string }>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/${encodeURIComponent(reviewId)}/human-notes`,
    { notes }
  );
}

export function generateProposal(
  experimentId: string,
  version: string,
  reviewId: string,
  dryRun = false
): Promise<ProposalResponse> {
  return apiPost<ProposalResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/${encodeURIComponent(reviewId)}/proposal`,
    dryRun ? { dry_run: true } : undefined
  );
}

export function previewProposalPrompts(
  experimentId: string,
  version: string,
  reviewId: string
): Promise<PromptPreviewResponse> {
  return apiPost<PromptPreviewResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/${encodeURIComponent(reviewId)}/proposal/preview-prompts`
  );
}

export async function getReviewProposal(
  experimentId: string,
  version: string,
  reviewId: string
): Promise<ProposalResponse | null> {
  const response = await fetch(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/${encodeURIComponent(reviewId)}/proposal`
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<ProposalResponse>;
}

export function createProposalVersion(
  experimentId: string,
  version: string,
  reviewId: string
): Promise<CreatedVersionResponse> {
  return apiPost<CreatedVersionResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/reviews/${encodeURIComponent(reviewId)}/proposal/create-version`
  );
}

export function updateVersionSource(
  experimentId: string,
  version: string,
  request: VersionSourceUpdateRequest
): Promise<VersionSourceUpdateResponse> {
  return apiPost<VersionSourceUpdateResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/source`,
    request
  );
}

export function updateVersionValidators(
  experimentId: string,
  version: string,
  request: VersionValidatorsUpdateRequest
): Promise<VersionValidatorsUpdateResponse> {
  return apiPost<VersionValidatorsUpdateResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/validators`,
    request
  );
}

export function compareVersions(
  experimentId: string,
  baselineVersion: string,
  candidateVersion: string,
  dryRun = false
): Promise<CompareMatrixResponse> {
  return apiPost<CompareMatrixResponse>(
    `/api/experiments/${encodeURIComponent(experimentId)}/comparisons`,
    {
      baseline_version: baselineVersion,
      candidate_version: candidateVersion,
      dry_run: dryRun
    }
  );
}

async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}

async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}

async function apiDelete<T>(path: string): Promise<T> {
  const response = await fetch(path, { method: "DELETE" });
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}
