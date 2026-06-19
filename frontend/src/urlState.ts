const EXPERIMENT_PARAM = "experiment";
const GLOBAL_SETTINGS_SEGMENT = "global-settings";

export const workbenchTabs = [
  "overview",
  "settings",
  "cases",
  "runs",
  "validation",
  "review",
  "proposal",
  "compare"
] as const;

export type WorkbenchTab = (typeof workbenchTabs)[number];

export interface ExperimentRoute {
  experimentId: string | null;
  tab: WorkbenchTab;
}

const DEFAULT_TAB: WorkbenchTab = "overview";

function isWorkbenchTab(value: string | undefined): value is WorkbenchTab {
  return workbenchTabs.includes(value as WorkbenchTab);
}

function decodePathSegment(segment: string | undefined): string | null {
  if (segment === undefined || segment.trim() === "") {
    return null;
  }
  return decodeURIComponent(segment);
}

export function parseExperimentId(search: string): string | null {
  const id = new URLSearchParams(search).get(EXPERIMENT_PARAM);
  return id === null || id.trim() === "" ? null : id;
}

export function parseExperimentRoute(url: URL): ExperimentRoute {
  const segments = url.pathname
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment !== "");
  const experimentId = decodePathSegment(segments[0]) ?? parseExperimentId(url.search);
  const tab = isWorkbenchTab(segments[1]) ? segments[1] : DEFAULT_TAB;
  return { experimentId, tab };
}

export function isGlobalSettingsRoute(url: URL): boolean {
  const firstSegment = url.pathname
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment !== "")[0];
  return firstSegment === GLOBAL_SETTINGS_SEGMENT;
}

export function buildGlobalSettingsPath(): string {
  return `/${GLOBAL_SETTINGS_SEGMENT}`;
}

export function buildExperimentPath(
  experimentId: string,
  tab: WorkbenchTab
): string {
  return `/${encodeURIComponent(experimentId)}/${tab}`;
}
