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
  VersionOverview,
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
  if (!response.ok) throw new Error(await readErrorMessage(response));
  return response.json() as Promise<T>;
}
