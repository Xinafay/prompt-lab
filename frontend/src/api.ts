import type {
  ComparisonResponse,
  CreatedVersionResponse,
  Experiment,
  FindingDecisionSet,
  JobEvent,
  JobStatus,
  JudgmentResponse,
  ProposalResponse,
  ReviewState,
  RunVersionRequest,
  RunsResponse,
  VersionOverview
} from "./types";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: body === undefined ? undefined : { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  if (!response.ok) throw new Error(await response.text());
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

export function getJob(jobId: string): Promise<JobStatus> {
  return apiGet<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`);
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

export function compareVersions(
  experimentId: string,
  baselineVersion: string,
  candidateVersion: string,
  dryRun = false
): Promise<ComparisonResponse> {
  return apiPost<ComparisonResponse>(
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
  if (!response.ok) throw new Error(await response.text());
  return response.json() as Promise<T>;
}
