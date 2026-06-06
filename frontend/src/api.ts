import type { JobEvent, JobStatus, RunsResponse, VersionOverview } from "./types";

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
  version: string
): Promise<JobStatus> {
  return apiPost<JobStatus>(
    `/api/experiments/${encodeURIComponent(experimentId)}/versions/${encodeURIComponent(
      version
    )}/runs`
  );
}

export function getJob(jobId: string): Promise<JobStatus> {
  return apiGet<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function getJobEvents(jobId: string): Promise<JobEvent[]> {
  return apiGet<JobEvent[]>(`/api/jobs/${encodeURIComponent(jobId)}/events`);
}
