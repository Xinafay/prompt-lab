const EXPERIMENT_PARAM = "experiment";
const EXPERIMENTS_SEGMENT = "experiments";
const CASE_SUITES_SEGMENT = "case-suites";
const GLOBAL_SETTINGS_SEGMENT = "global-settings";

export const workbenchTabs = [
  "prompt",
  "settings",
  "validators",
  "cases",
  "runs",
  "validation",
  "review",
  "proposal",
  "compare"
] as const;

export type WorkbenchTab = (typeof workbenchTabs)[number];

export const caseSuiteTabs = ["cases", "settings"] as const;
export type CaseSuiteTab = (typeof caseSuiteTabs)[number];

export interface ExperimentRoute {
  experimentId: string | null;
  tab: WorkbenchTab;
}

export interface CaseSuitesRoute {
  suiteId: string | null;
  tab: CaseSuiteTab;
}

const DEFAULT_TAB: WorkbenchTab = "prompt";
const DEFAULT_CASE_SUITE_TAB: CaseSuiteTab = "cases";

function isWorkbenchTab(value: string | undefined): value is WorkbenchTab {
  return workbenchTabs.includes(value as WorkbenchTab);
}

function isCaseSuiteTab(value: string | undefined): value is CaseSuiteTab {
  return caseSuiteTabs.includes(value as CaseSuiteTab);
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
  const isCanonicalRoute = segments[0] === EXPERIMENTS_SEGMENT;
  const experimentSegment = isCanonicalRoute ? segments[1] : segments[0];
  const tabSegment = isCanonicalRoute ? segments[2] : segments[1];
  const experimentId =
    decodePathSegment(experimentSegment) ?? parseExperimentId(url.search);
  const tab = isWorkbenchTab(tabSegment) ? tabSegment : DEFAULT_TAB;
  return { experimentId, tab };
}

export function isGlobalSettingsRoute(url: URL): boolean {
  const firstSegment = url.pathname
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment !== "")[0];
  return firstSegment === GLOBAL_SETTINGS_SEGMENT;
}

export function isCaseSuitesRoute(url: URL): boolean {
  const firstSegment = url.pathname
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment !== "")[0];
  return firstSegment === CASE_SUITES_SEGMENT;
}

export function parseCaseSuitesRoute(url: URL): CaseSuitesRoute {
  const segments = url.pathname
    .split("/")
    .map((segment) => segment.trim())
    .filter((segment) => segment !== "");
  const tab = isCaseSuiteTab(segments[2])
    ? segments[2]
    : DEFAULT_CASE_SUITE_TAB;
  return { suiteId: decodePathSegment(segments[1]), tab };
}

export function buildGlobalSettingsPath(): string {
  return `/${GLOBAL_SETTINGS_SEGMENT}`;
}

export function buildCaseSuitesPath(
  suiteId: string | null = null,
  tab: CaseSuiteTab = DEFAULT_CASE_SUITE_TAB
): string {
  if (suiteId === null) {
    return `/${CASE_SUITES_SEGMENT}`;
  }
  return `/${CASE_SUITES_SEGMENT}/${encodeURIComponent(suiteId)}/${tab}`;
}

export function buildExperimentPath(
  experimentId: string,
  tab: WorkbenchTab
): string {
  return `/${EXPERIMENTS_SEGMENT}/${encodeURIComponent(experimentId)}/${tab}`;
}
