const EXPERIMENT_PARAM = "experiment";

export function parseExperimentId(search: string): string | null {
  const id = new URLSearchParams(search).get(EXPERIMENT_PARAM);
  return id === null || id.trim() === "" ? null : id;
}

export function writeSelectedExperimentId(experimentId: string): void {
  const url = new URL(window.location.href);
  url.searchParams.set(EXPERIMENT_PARAM, experimentId);
  window.history.replaceState(window.history.state, "", url);
}
