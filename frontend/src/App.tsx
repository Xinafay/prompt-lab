import { useEffect, useMemo, useRef, useState } from "react";

import {
  apiGet,
  cancelJob,
  cloneExperiment,
  compareVersions,
  createCaseSuite,
  createExperiment,
  createProposalVersion,
  deleteCaseSuite,
  deleteExperiment,
  getCaseSuiteCases,
  generateProposal,
  getActiveJob,
  getCaseSuites,
  getExperimentVersions,
  getGlobalSettings,
  getJob,
  getLatestReviewState,
  getLatestValidationState,
  getReviewProposal,
  getReviewState,
  getVersionOverview,
  getVersionRuns,
  judgeVersion,
  jobEventsStreamUrl,
  previewJudgePrompts,
  previewProposalPrompts,
  previewRunPrompts,
  previewValidationPrompts,
  runVersion,
  saveCaseInclusion,
  saveCaseSuiteCases,
  validateVersion,
  updateCaseSuite,
  updateExperiment,
  updateGlobalSettings,
  updateHumanNotes,
  updateReviewDecisions,
  updateValidationInclusion,
  updateVersionSource,
  updateVersionValidators
} from "./api";
import { CaseBrowser } from "./components/CaseBrowser";
import { CaseSuiteManager } from "./components/CaseSuiteManager";
import { ComparisonView } from "./components/ComparisonView";
import {
  CloneExperimentModal,
  DeleteExperimentModal,
  NewExperimentModal
} from "./components/ExperimentManagementModals";
import { ExperimentSettings } from "./components/ExperimentSettings";
import { ExperimentsList } from "./components/ExperimentsList";
import { GlobalSettings } from "./components/GlobalSettings";
import { PromptView } from "./components/PromptView";
import { PromptPreviewModal } from "./components/PromptPreviewModal";
import { ProposalView } from "./components/ProposalView";
import { ReviewView } from "./components/ReviewView";
import { RunsView } from "./components/RunsView";
import { TooltipButton } from "./components/TooltipButton";
import {
  buildValidationInclusionUpdate,
  ValidationView
} from "./components/ValidationView";
import { ValidatorsView } from "./components/ValidatorsView";
import { snapshotReviewState } from "./components/reviewStateSnapshot";
import { snapshotValidationState } from "./components/validationStateSnapshot";
import { WorkbenchTabs } from "./components/WorkbenchTabs";
import { WorkflowToolbar } from "./components/WorkflowToolbar";
import type {
  Case,
  CaseSuite,
  CaseSuiteCreateRequest,
  CaseSuiteUpdateRequest,
  CompareMatrixResponse,
  CreatedVersionResponse,
  Experiment,
  ExperimentCloneRequest,
  ExperimentCreateRequest,
  FindingDecisionValue,
  GlobalSettings as GlobalSettingsModel,
  JobEvent,
  JobStatus,
  PromptPreviewResponse,
  ProposalResponse,
  ReviewState,
  RunsResponse,
  ValidationState,
  VersionOverview,
  VersionSourceDraft,
  VersionSourceSaveMode,
  VersionValidatorsDraft,
  VersionValidatorsSaveMode,
  VersionSummary,
  WorkflowMode
} from "./types";
import {
  buildGlobalSettingsPath,
  buildExperimentPath,
  isGlobalSettingsRoute,
  parseExperimentRoute,
  type WorkbenchTab
} from "./urlState";
import {
  getCompareActionState,
  getJudgeActionState,
  getProposalActionLabel,
  getRunActionLabel,
  getValidateActionState
} from "./workflowActions";
import "./components/PromptPreviewModal.css";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; experiments: Experiment[] }
  | { status: "error"; message: string };

type DetailState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; overview: VersionOverview; runs: RunsResponse }
  | { status: "error"; message: string };

type GlobalSettingsState =
  | { status: "loading" }
  | { status: "loaded"; settings: GlobalSettingsModel }
  | { status: "error"; message: string };

type HistoryMode = "push" | "replace";
type AppView = "experiment" | "globalSettings" | "caseSuites";
type PromptPreviewAction = () => void | Promise<void>;
type SourceViewMode = "edit" | "diff";
type UnsavedNavigationKind =
  | "settings"
  | "source"
  | "validators"
  | "cases"
  | "validation"
  | "review";

type ExperimentManagementDialog =
  | { kind: "new" }
  | { kind: "clone"; experiment: Experiment }
  | { kind: "delete"; experiment: Experiment };

type PendingNavigationTarget =
  | { kind: "experiment"; experiment: Experiment | null }
  | { kind: "experimentDialog"; dialog: ExperimentManagementDialog }
  | { kind: "caseSuites" }
  | { kind: "globalSettings" }
  | { kind: "route"; route: ReturnType<typeof currentExperimentRoute> }
  | { kind: "tab"; tab: WorkbenchTab }
  | { kind: "version"; version: string };

type PendingNavigation = PendingNavigationTarget & {
  unsavedKind: UnsavedNavigationKind;
};

type PendingSourceOverwrite = {
  navigation: PendingNavigation | null;
};

type PendingValidatorsOverwrite = {
  navigation: PendingNavigation | null;
};

function currentExperimentRoute() {
  return parseExperimentRoute(new URL(window.location.href));
}

const SHOW_DRY_RUN_CONTROLS =
  import.meta.env?.VITE_PROMPT_LAB_SHOW_DRY_RUN === "1";

function workflowCompletionMessage(kind: string): string {
  if (kind === "run_version") return "Active run completed.";
  if (kind === "validation") return "Validation loaded.";
  if (kind === "judge") return "Active review loaded.";
  if (kind === "proposal") return "Proposal generated.";
  if (kind === "compare") return "Comparison loaded.";
  return "Workflow action completed.";
}

function hasCompletedValidation(state: ValidationState | null): boolean {
  return state?.validation_batch.status === "completed";
}

function sourceDraftFromOverview(overview: VersionOverview): VersionSourceDraft {
  return {
    prompt: overview.prompt,
    model_py:
      overview.experiment.output.type === "pydantic"
        ? overview.model_py ?? ""
        : null
  };
}

function sourceDraftsMatch(
  left: VersionSourceDraft,
  right: VersionSourceDraft
): boolean {
  return (
    left.prompt === right.prompt &&
    (left.model_py ?? null) === (right.model_py ?? null)
  );
}

export function caseInclusionMatchesCases(
  nextCases: Case[],
  committedCases: Case[]
): boolean {
  if (nextCases.length !== committedCases.length) {
    return false;
  }
  const enabledByCaseId = new Map(
    committedCases.map((artifactCase) => [
      artifactCase.id,
      artifactCase.enabled
    ])
  );
  return nextCases.every(
    (artifactCase) =>
      enabledByCaseId.has(artifactCase.id) &&
      enabledByCaseId.get(artifactCase.id) === artifactCase.enabled
  );
}

function cloneCases(cases: Case[]): Case[] {
  return JSON.parse(JSON.stringify(cases)) as Case[];
}

function caseSuiteCasesMatch(left: Case[], right: Case[]): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [appView, setAppView] = useState<AppView>(() =>
    isGlobalSettingsRoute(new URL(window.location.href))
      ? "globalSettings"
      : "experiment"
  );
  const [selectedExperiment, setSelectedExperiment] =
    useState<Experiment | null>(null);
  const [caseSuites, setCaseSuites] = useState<CaseSuite[]>([]);
  const [selectedCaseSuiteId, setSelectedCaseSuiteId] = useState<string | null>(
    null
  );
  const [caseSuiteCases, setCaseSuiteCases] = useState<Case[]>([]);
  const [caseSuiteCasesBaseline, setCaseSuiteCasesBaseline] = useState<Case[]>(
    []
  );
  const [caseSuiteCasesDirty, setCaseSuiteCasesDirty] = useState(false);
  const [caseSuiteBusy, setCaseSuiteBusy] = useState(false);
  const [caseSuiteMessage, setCaseSuiteMessage] = useState<string | null>(null);
  const [detailState, setDetailState] = useState<DetailState>({ status: "idle" });
  const [globalSettingsState, setGlobalSettingsState] =
    useState<GlobalSettingsState>({ status: "loading" });
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [validationState, setValidationState] = useState<ValidationState | null>(
    null
  );
  const committedValidationStateRef = useRef<ValidationState | null>(null);
  const [validationDirty, setValidationDirty] = useState(false);
  const [compareValidationByVersion, setCompareValidationByVersion] = useState<
    Record<string, boolean>
  >({});
  const [reviewState, setReviewState] = useState<ReviewState | null>(null);
  const committedReviewStateRef = useRef<ReviewState | null>(null);
  const [proposalResponse, setProposalResponse] =
    useState<ProposalResponse | null>(null);
  const [createdVersion, setCreatedVersion] =
    useState<CreatedVersionResponse | null>(null);
  const [comparison, setComparison] = useState<CompareMatrixResponse | null>(null);
  const [versionSummaries, setVersionSummaries] = useState<VersionSummary[]>([]);
  const [activeTab, setActiveTab] = useState<WorkbenchTab>(
    () => currentExperimentRoute().tab
  );
  const [workflowMode, setWorkflowMode] = useState<WorkflowMode>("live");
  const [baselineVersion, setBaselineVersion] = useState("v001");
  const [candidateVersion, setCandidateVersion] = useState("v001");
  const [workflowBusy, setWorkflowBusy] = useState(false);
  const [workflowMessage, setWorkflowMessage] = useState<string | null>(null);
  const [promptPreview, setPromptPreview] =
    useState<PromptPreviewResponse | null>(null);
  const [promptPreviewAction, setPromptPreviewAction] =
    useState<PromptPreviewAction | null>(null);
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [settingsDirty, setSettingsDirty] = useState(false);
  const [settingsDraft, setSettingsDraft] = useState<Experiment | null>(null);
  const [experimentDialog, setExperimentDialog] =
    useState<ExperimentManagementDialog | null>(null);
  const [experimentActionBusy, setExperimentActionBusy] = useState(false);
  const [experimentActionError, setExperimentActionError] = useState<string | null>(
    null
  );
  const [sourceEditing, setSourceEditing] = useState(false);
  const [sourceDraft, setSourceDraft] = useState<VersionSourceDraft | null>(null);
  const [sourceViewMode, setSourceViewMode] = useState<SourceViewMode>("edit");
  const [pendingSourceOverwrite, setPendingSourceOverwrite] =
    useState<PendingSourceOverwrite | null>(null);
  const [validatorsDraft, setValidatorsDraft] =
    useState<VersionValidatorsDraft | null>(null);
  const [validatorsDirty, setValidatorsDirty] = useState(false);
  const [pendingValidatorsOverwrite, setPendingValidatorsOverwrite] =
    useState<PendingValidatorsOverwrite | null>(null);
  const [casesDraft, setCasesDraft] = useState<Case[] | null>(null);
  const [casesDirty, setCasesDirty] = useState(false);
  const [globalSettingsBusy, setGlobalSettingsBusy] = useState(false);
  const [globalSettingsMessage, setGlobalSettingsMessage] =
    useState<string | null>(null);
  const [globalSettingsDirty, setGlobalSettingsDirty] = useState(false);
  const [globalSettingsDraft, setGlobalSettingsDraft] =
    useState<GlobalSettingsModel | null>(null);
  const [pendingNavigation, setPendingNavigation] =
    useState<PendingNavigation | null>(null);
  const [navigationError, setNavigationError] = useState<string | null>(null);
  const [navigationSaving, setNavigationSaving] = useState(false);
  const [decisionsDirty, setDecisionsDirty] = useState(false);
  const [humanNotesDirty, setHumanNotesDirty] = useState(false);
  const selectedKeyRef = useRef<string | null>(null);
  const followedJobIdRef = useRef<string | null>(null);
  const runRequestIdRef = useRef(0);
  const workflowRequestIdRef = useRef(0);
  const baselineVersionRef = useRef("v001");
  const candidateVersionRef = useRef("v001");
  const preserveNextValidatorsCleanMessageRef = useRef(false);
  const sourceDirty = useMemo(() => {
    if (detailState.status !== "loaded" || sourceDraft === null) {
      return false;
    }
    return !sourceDraftsMatch(
      sourceDraft,
      sourceDraftFromOverview(detailState.overview)
    );
  }, [detailState, sourceDraft]);

  function writeExperimentRoute(
    experimentId: string,
    tab: WorkbenchTab,
    historyMode: HistoryMode
  ) {
    const url = new URL(window.location.href);
    url.pathname = buildExperimentPath(experimentId, tab);
    url.search = "";
    const method = historyMode === "push" ? "pushState" : "replaceState";
    window.history[method](window.history.state, "", url);
  }

  function writeGlobalSettingsRoute(historyMode: HistoryMode) {
    const url = new URL(window.location.href);
    url.pathname = buildGlobalSettingsPath();
    url.search = "";
    const method = historyMode === "push" ? "pushState" : "replaceState";
    window.history[method](window.history.state, "", url);
  }

  function writeCurrentRoute(historyMode: HistoryMode) {
    if (appView === "globalSettings") {
      writeGlobalSettingsRoute(historyMode);
      return;
    }
    if (selectedExperiment !== null) {
      writeExperimentRoute(selectedExperiment.id, activeTab, historyMode);
    }
  }

  function clearSourceEditor(
    options: { clearPendingOverwrite?: boolean } = {}
  ) {
    setSourceEditing(false);
    setSourceDraft(null);
    setSourceViewMode("edit");
    if (options.clearPendingOverwrite ?? true) {
      setPendingSourceOverwrite(null);
    }
  }

  function clearValidatorEditor(
    options: { clearPendingOverwrite?: boolean } = {}
  ) {
    setValidatorsDraft(null);
    setValidatorsDirty(false);
    preserveNextValidatorsCleanMessageRef.current = false;
    if (options.clearPendingOverwrite ?? true) {
      setPendingValidatorsOverwrite(null);
    }
  }

  function clearCaseEditor() {
    setCasesDraft(null);
    setCasesDirty(false);
  }

  function activateTab(tab: WorkbenchTab, historyMode: HistoryMode = "replace") {
    setActiveTab(tab);
    if (selectedExperiment !== null) {
      writeExperimentRoute(selectedExperiment.id, tab, historyMode);
    }
  }

  function selectExperiment(
    experiment: Experiment | null,
    options?: {
      historyMode?: HistoryMode;
      tab?: WorkbenchTab;
      updateUrl?: boolean;
    }
  ) {
    const nextTab = options?.tab ?? activeTab;
    selectedKeyRef.current =
      experiment === null ? null : `${experiment.id}:${experiment.active_version}`;
    runRequestIdRef.current += 1;
    workflowRequestIdRef.current += 1;
    setSelectedExperiment(experiment);
    setCommittedValidationState(null);
    setCompareValidationByVersion({});
    setCommittedReviewState(null);
    setProposalResponse(null);
    setCreatedVersion(null);
    setComparison(null);
    setVersionSummaries([]);
    setWorkflowMessage(null);
    setPromptPreview(null);
    setPromptPreviewAction(null);
    setSettingsMessage(null);
    setWorkflowBusy(false);
    setSettingsBusy(false);
    setSettingsDirty(false);
    setSettingsDraft(null);
    clearSourceEditor();
    clearValidatorEditor();
    clearCaseEditor();
    setPendingNavigation(null);
    setNavigationError(null);
    setNavigationSaving(false);
    setAppView("experiment");
    setActiveTab(nextTab);
    if (experiment !== null) {
      if (options?.updateUrl !== false) {
        writeExperimentRoute(
          experiment.id,
          nextTab,
          options?.historyMode ?? "replace"
        );
      }
      setCandidateVersion(experiment.active_version);
      setBaselineVersion("v001");
      candidateVersionRef.current = experiment.active_version;
      baselineVersionRef.current = "v001";
    }
  }

  function selectGlobalSettings(options?: { historyMode?: HistoryMode }) {
    selectedKeyRef.current = null;
    runRequestIdRef.current += 1;
    workflowRequestIdRef.current += 1;
    setAppView("globalSettings");
    setSelectedExperiment(null);
    setDetailState({ status: "idle" });
    setJobStatus(null);
    setCommittedValidationState(null);
    setCompareValidationByVersion({});
    setCommittedReviewState(null);
    setProposalResponse(null);
    setCreatedVersion(null);
    setComparison(null);
    setVersionSummaries([]);
    setWorkflowMessage(null);
    setPromptPreview(null);
    setPromptPreviewAction(null);
    setWorkflowBusy(false);
    setSettingsMessage(null);
    setSettingsBusy(false);
    setSettingsDirty(false);
    setSettingsDraft(null);
    clearSourceEditor();
    clearValidatorEditor();
    clearCaseEditor();
    setPendingNavigation(null);
    setNavigationError(null);
    setNavigationSaving(false);
    writeGlobalSettingsRoute(options?.historyMode ?? "replace");
  }

  function selectCaseSuites() {
    setAppView("caseSuites");
    setPendingNavigation(null);
    setNavigationError(null);
    setNavigationSaving(false);
    setCaseSuiteMessage(null);
  }

  function unsavedNavigationKind(): UnsavedNavigationKind | null {
    if (
      appView === "experiment" &&
      activeTab === "prompt" &&
      sourceDirty &&
      !workflowBusy
    ) {
      return "source";
    }
    if (
      appView === "experiment" &&
      activeTab === "validators" &&
      validatorsDirty &&
      !workflowBusy
    ) {
      return "validators";
    }
    if (
      appView === "experiment" &&
      activeTab === "validation" &&
      validationDirty &&
      !workflowBusy
    ) {
      return "validation";
    }
    if (
      appView === "experiment" &&
      activeTab === "cases" &&
      casesDirty &&
      !workflowBusy
    ) {
      return "cases";
    }
    if (
      appView === "experiment" &&
      activeTab === "review" &&
      (decisionsDirty || humanNotesDirty) &&
      !workflowBusy
    ) {
      return "review";
    }
    if (
      appView === "experiment" &&
      activeTab === "settings" &&
      settingsDirty &&
      !settingsBusy
    ) {
      return "settings";
    }
    if (
      appView === "globalSettings" &&
      globalSettingsDirty &&
      !globalSettingsBusy
    ) {
      return "settings";
    }
    return null;
  }

  function buildPendingNavigation(
    navigation: PendingNavigationTarget
  ): PendingNavigation | null {
    const unsavedKind = unsavedNavigationKind();
    if (unsavedKind === null) {
      return null;
    }
    return { ...navigation, unsavedKind };
  }

  function canSavePendingNavigation(
    kind: UnsavedNavigationKind | null
  ): boolean {
    if (kind === "validation") {
      return validationState !== null;
    }
    if (kind === "review") {
      return reviewState !== null;
    }
    if (kind === "source") {
      return sourceDraft !== null;
    }
    if (kind === "validators") {
      return validatorsDraft !== null;
    }
    if (kind === "cases") {
      return casesDraft !== null;
    }
    if (appView === "globalSettings") {
      return globalSettingsDraft !== null;
    }
    return settingsDraft !== null;
  }

  function pendingNavigationCopy(
    kind: UnsavedNavigationKind | null
  ): { title: string; body: string } {
    if (kind === "validation") {
      return {
        title: "Unsaved validation changes",
        body:
          "Save validation inclusion before leaving this view, or discard the unsaved changes."
      };
    }
    if (kind === "review") {
      return {
        title: "Unsaved review changes",
        body:
          "Save review changes before leaving this view, or discard the unsaved changes."
      };
    }
    if (kind === "source") {
      return {
        title: "Unsaved source changes",
        body:
          "Save the prompt and model as a new version, overwrite the current version, or discard the draft changes."
      };
    }
    if (kind === "validators") {
      return {
        title: "Unsaved validator changes",
        body:
          "Save validators as a new version, overwrite the current version, or discard the draft changes."
      };
    }
    if (kind === "cases") {
      return {
        title: "Unsaved case inclusion changes",
        body:
          "Save case inclusion before leaving this view, or discard the unsaved changes."
      };
    }
    return {
      title: "Unsaved settings changes",
      body:
        "Save the current settings before leaving this view, or discard the draft changes."
    };
  }

  function experimentForRoute(route: ReturnType<typeof currentExperimentRoute>) {
    if (state.status !== "loaded") {
      return null;
    }
    if (route.experimentId === null) {
      return state.experiments[0] ?? null;
    }
    return (
      state.experiments.find((experiment) => experiment.id === route.experimentId) ??
      state.experiments[0] ??
      null
    );
  }

  async function performPendingNavigation(navigation: PendingNavigation) {
    if (navigation.kind === "experiment") {
      selectExperiment(navigation.experiment, { historyMode: "push" });
      return;
    }
    if (navigation.kind === "experimentDialog") {
      openExperimentDialog(navigation.dialog);
      return;
    }
    if (navigation.kind === "globalSettings") {
      selectGlobalSettings({ historyMode: "push" });
      return;
    }
    if (navigation.kind === "caseSuites") {
      selectCaseSuites();
      return;
    }
    if (navigation.kind === "route") {
      selectExperiment(experimentForRoute(navigation.route), {
        historyMode: "push",
        tab: navigation.route.tab
      });
      return;
    }
    if (navigation.kind === "tab") {
      activateTab(navigation.tab, "push");
      return;
    }
    await performActiveVersionChange(navigation.version);
  }

  function requestExperimentSelection(experiment: Experiment | null) {
    if (appView === "experiment" && experiment?.id === selectedExperiment?.id) {
      return;
    }
    const navigation = buildPendingNavigation({ kind: "experiment", experiment });
    if (navigation !== null) {
      setNavigationError(null);
      setPendingNavigation(navigation);
      return;
    }
    selectExperiment(experiment, { historyMode: "push" });
  }

  function requestGlobalSettingsSelection() {
    if (appView === "globalSettings") {
      return;
    }
    const navigation = buildPendingNavigation({ kind: "globalSettings" });
    if (navigation !== null) {
      setNavigationError(null);
      setPendingNavigation(navigation);
      return;
    }
    selectGlobalSettings({ historyMode: "push" });
  }

  function requestCaseSuitesSelection() {
    if (appView === "caseSuites") {
      return;
    }
    const navigation = buildPendingNavigation({ kind: "caseSuites" });
    if (navigation !== null) {
      setNavigationError(null);
      setPendingNavigation(navigation);
      return;
    }
    selectCaseSuites();
  }

  function handleSelectCaseSuite(suiteId: string) {
    if (caseSuiteCasesDirty) {
      setCaseSuiteMessage("Save or reset case changes before switching suites.");
      return;
    }
    setSelectedCaseSuiteId(suiteId);
  }

  function requestTabChange(tab: WorkbenchTab) {
    if (tab === activeTab) {
      return;
    }
    const navigation = buildPendingNavigation({ kind: "tab", tab });
    if (navigation !== null) {
      setNavigationError(null);
      setPendingNavigation(navigation);
      return;
    }
    activateTab(tab, "push");
  }

  function openExperimentDialog(dialog: ExperimentManagementDialog) {
    setExperimentActionError(null);
    setExperimentDialog(dialog);
  }

  function requestExperimentDialog(dialog: ExperimentManagementDialog) {
    const navigation = buildPendingNavigation({
      kind: "experimentDialog",
      dialog
    });
    if (navigation !== null) {
      setNavigationError(null);
      setPendingNavigation(navigation);
      return;
    }
    openExperimentDialog(dialog);
  }

  async function routeAfterExperimentMutation(
    experiment: Experiment,
    tab: WorkbenchTab
  ) {
    const experiments = await apiGet<Experiment[]>("/api/experiments");
    setState({ status: "loaded", experiments });
    selectExperiment(experiment, {
      historyMode: "replace",
      tab
    });
  }

  async function refreshAfterExperimentDelete(deletedExperimentId: string) {
    const experiments = await apiGet<Experiment[]>("/api/experiments");
    setState({ status: "loaded", experiments });
    const deletedIndex =
      state.status === "loaded"
        ? state.experiments.findIndex(
            (experiment) => experiment.id === deletedExperimentId
          )
        : -1;
    const nextExperiment =
      experiments[deletedIndex] ??
      experiments[deletedIndex - 1] ??
      experiments[0] ??
      null;
    selectExperiment(nextExperiment, {
      historyMode: "replace",
      tab: "prompt"
    });
  }

  function requestNewExperiment() {
    requestExperimentDialog({ kind: "new" });
  }

  function requestCloneExperiment(experiment: Experiment) {
    requestExperimentDialog({ kind: "clone", experiment });
  }

  function requestDeleteExperiment(experiment: Experiment) {
    requestExperimentDialog({ kind: "delete", experiment });
  }

  function closeExperimentDialog() {
    if (experimentActionBusy) return;
    setExperimentDialog(null);
    setExperimentActionError(null);
  }

  function handleStayOnSettings() {
    setPendingNavigation(null);
    setNavigationError(null);
  }

  async function handleDiscardSettingsAndContinue() {
    if (pendingNavigation === null) {
      return;
    }
    const navigation = pendingNavigation;
    const kind = navigation.unsavedKind;
    if (kind === "validation") {
      restoreCommittedValidationState();
    } else if (kind === "review") {
      restoreCommittedReviewState();
    } else if (kind === "source") {
      clearSourceEditor();
    } else if (kind === "validators") {
      clearValidatorEditor();
    } else if (kind === "cases") {
      clearCaseEditor();
    } else if (appView === "globalSettings") {
      setGlobalSettingsDirty(false);
      setGlobalSettingsDraft(null);
    } else {
      setSettingsDirty(false);
      setSettingsDraft(null);
    }
    setPendingNavigation(null);
    setNavigationError(null);
    await performPendingNavigation(navigation);
  }

  async function handleSaveSettingsAndContinue() {
    if (pendingNavigation === null) {
      return;
    }
    const navigation = pendingNavigation;
    const kind = navigation.unsavedKind;
    setNavigationSaving(true);
    setNavigationError(null);
    try {
      if (kind === "validation") {
        await handleSaveValidationInclusion({ rethrow: true });
      } else if (kind === "review") {
        await handleSaveReviewChanges({ rethrow: true });
      } else if (kind === "source") {
        await handleSaveVersionSource("create_next", {
          navigation,
          rethrow: true
        });
        setPendingNavigation(null);
        return;
      } else if (kind === "validators") {
        await handleSaveVersionValidators("create_next", {
          navigation,
          rethrow: true
        });
        setPendingNavigation(null);
        return;
      } else if (kind === "cases") {
        await handleSaveCaseInclusion({ rethrow: true });
      } else if (appView === "globalSettings") {
        if (globalSettingsDraft === null) {
          return;
        }
        await handleSaveGlobalSettings(globalSettingsDraft);
        setGlobalSettingsDirty(false);
        setGlobalSettingsDraft(null);
      } else {
        if (settingsDraft === null) {
          return;
        }
        await handleSaveExperimentSettings(settingsDraft);
        setSettingsDirty(false);
        setSettingsDraft(null);
      }
      setPendingNavigation(null);
      await performPendingNavigation(navigation);
    } catch (error) {
      setNavigationError(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setNavigationSaving(false);
    }
  }

  function isSelectionCurrent(selectionKey: string): boolean {
    return selectedKeyRef.current === selectionKey;
  }

  function beginWorkflow(selectionKey: string, message?: string): number {
    const requestId = workflowRequestIdRef.current + 1;
    workflowRequestIdRef.current = requestId;
    setWorkflowBusy(true);
    if (message !== undefined) {
      setWorkflowMessage(message);
    }
    window.setTimeout(() => {
      void syncActiveWorkflowJob("Workflow action running.");
    }, 100);
    return requestId;
  }

  function setCommittedValidationState(state: ValidationState | null) {
    const displayState = snapshotValidationState(state);
    committedValidationStateRef.current = snapshotValidationState(state);
    setValidationState(displayState);
    setValidationDirty(false);
  }

  function restoreCommittedValidationState() {
    setValidationState(snapshotValidationState(committedValidationStateRef.current));
    setValidationDirty(false);
  }

  function setCommittedReviewState(state: ReviewState | null) {
    const displayState = snapshotReviewState(state);
    committedReviewStateRef.current = snapshotReviewState(state);
    setReviewState(displayState);
    setDecisionsDirty(false);
    setHumanNotesDirty(false);
  }

  function restoreCommittedReviewState() {
    setReviewState(snapshotReviewState(committedReviewStateRef.current));
    setDecisionsDirty(false);
    setHumanNotesDirty(false);
  }

  function isWorkflowCurrent(requestId: number, selectionKey: string): boolean {
    return (
      workflowRequestIdRef.current === requestId && isSelectionCurrent(selectionKey)
    );
  }

  async function refreshSelectedVersionArtifacts(job: JobStatus) {
    const selectionKey = `${job.experiment_id}:${job.version}`;
    if (!isSelectionCurrent(selectionKey)) {
      return;
    }
    const [overview, runs, latestValidation, latestReview] = await Promise.all([
      getVersionOverview(job.experiment_id, job.version),
      getVersionRuns(job.experiment_id, job.version),
      getLatestValidationState(job.experiment_id, job.version),
      getLatestReviewState(job.experiment_id, job.version)
    ]);
    const latestProposal =
      latestReview === null
        ? null
        : await getReviewProposal(
            job.experiment_id,
            job.version,
            latestReview.review_id
          );
    if (!isSelectionCurrent(selectionKey)) {
      return;
    }
    setDetailState({ status: "loaded", overview, runs });
    setCommittedValidationState(latestValidation);
    setCompareValidationByVersion((current) => ({
      ...current,
      [job.version]: hasCompletedValidation(latestValidation)
    }));
    setCommittedReviewState(latestReview);
    setProposalResponse(latestProposal);
    if (
      job.kind === "run_version" ||
      job.kind === "validation" ||
      job.kind === "judge"
    ) {
      setCreatedVersion(null);
      setComparison(null);
    }
  }

  async function followWorkflowJob(job: JobStatus, message: string) {
    if (job.status !== "running") {
      setJobStatus(job);
      return;
    }
    if (followedJobIdRef.current === job.job_id) {
      return;
    }
    followedJobIdRef.current = job.job_id;
    setJobStatus(job);
    setWorkflowBusy(true);
    setWorkflowMessage(message);
    try {
      const completedJob = await followJobEvents(
        job.job_id,
        job,
        () => followedJobIdRef.current === job.job_id
      );
      if (followedJobIdRef.current !== job.job_id) {
        return;
      }
      setJobStatus(completedJob);
      setWorkflowBusy(false);
      if (completedJob.status === "completed") {
        await refreshSelectedVersionArtifacts(completedJob);
        setWorkflowMessage(workflowCompletionMessage(completedJob.kind));
      } else if (completedJob.status === "cancelled") {
        setWorkflowMessage("Workflow job cancelled.");
      } else {
        setWorkflowMessage(completedJob.message || "Workflow job failed.");
      }
    } catch (error) {
      if (followedJobIdRef.current === job.job_id) {
        setWorkflowBusy(false);
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
    } finally {
      if (followedJobIdRef.current === job.job_id) {
        followedJobIdRef.current = null;
      }
    }
  }

  async function syncActiveWorkflowJob(message: string) {
    const activeJob = await getActiveJob();
    if (activeJob === null || activeJob.status !== "running") {
      return;
    }
    void followWorkflowJob(activeJob, message);
  }

  useEffect(() => {
    let cancelled = false;

    async function loadExperiments() {
      try {
        const experiments = await apiGet<Experiment[]>("/api/experiments");
        if (!cancelled) {
          setState({ status: "loaded", experiments });
          if (selectedKeyRef.current === null) {
            const requestedRoute = currentExperimentRoute();
            if (isGlobalSettingsRoute(new URL(window.location.href))) {
              selectGlobalSettings({ historyMode: "replace" });
            } else {
              const requestedExperiment =
                requestedRoute.experimentId === null
                  ? null
                  : experiments.find(
                      (experiment) => experiment.id === requestedRoute.experimentId
                    ) ?? null;
              selectExperiment(requestedExperiment ?? experiments[0] ?? null, {
                historyMode: "replace",
                tab: requestedRoute.tab
              });
            }
          }
        }
      } catch (error) {
        if (!cancelled) {
          setState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown error"
          });
        }
      }
    }

    void loadExperiments();

    return () => {
      cancelled = true;
    };
  }, []);

  async function refreshCaseSuites(preferredSuiteId?: string | null) {
    const suites = await getCaseSuites();
    setCaseSuites(suites);
    setSelectedCaseSuiteId((current) => {
      const preferred = preferredSuiteId ?? current;
      if (
        preferred !== null &&
        suites.some((suite) => suite.id === preferred)
      ) {
        return preferred;
      }
      return suites[0]?.id ?? null;
    });
    return suites;
  }

  useEffect(() => {
    let cancelled = false;

    async function loadCaseSuites() {
      try {
        const suites = await getCaseSuites();
        if (!cancelled) {
          setCaseSuites(suites);
          setSelectedCaseSuiteId((current) => {
            if (
              current !== null &&
              suites.some((suite) => suite.id === current)
            ) {
              return current;
            }
            return suites[0]?.id ?? null;
          });
        }
      } catch (error) {
        if (!cancelled) {
          setWorkflowMessage(
            error instanceof Error ? error.message : "Could not load case suites."
          );
        }
      }
    }

    void loadCaseSuites();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (selectedCaseSuiteId === null) {
      setCaseSuiteCases([]);
      setCaseSuiteCasesBaseline([]);
      setCaseSuiteCasesDirty(false);
      return;
    }

    let cancelled = false;
    setCaseSuiteBusy(true);

    async function loadSelectedSuiteCases(suiteId: string) {
      try {
        const loadedCases = await getCaseSuiteCases(suiteId);
        if (!cancelled) {
          setCaseSuiteCases(cloneCases(loadedCases));
          setCaseSuiteCasesBaseline(cloneCases(loadedCases));
          setCaseSuiteCasesDirty(false);
          setCaseSuiteMessage(null);
        }
      } catch (error) {
        if (!cancelled) {
          setCaseSuiteCases([]);
          setCaseSuiteCasesBaseline([]);
          setCaseSuiteCasesDirty(false);
          setCaseSuiteMessage(
            error instanceof Error ? error.message : "Could not load suite cases."
          );
        }
      } finally {
        if (!cancelled) {
          setCaseSuiteBusy(false);
        }
      }
    }

    void loadSelectedSuiteCases(selectedCaseSuiteId);

    return () => {
      cancelled = true;
    };
  }, [selectedCaseSuiteId]);

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      try {
        const settings = await getGlobalSettings();
        if (!cancelled) {
          setGlobalSettingsState({ status: "loaded", settings });
        }
      } catch (error) {
        if (!cancelled) {
          setGlobalSettingsState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown error"
          });
        }
      }
    }

    void loadSettings();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (state.status !== "loaded") {
      return;
    }
    const loadedExperiments = state.experiments;

    function handlePopState() {
      const url = new URL(window.location.href);
      const requestedRoute = currentExperimentRoute();
      const navigation = buildPendingNavigation(
        isGlobalSettingsRoute(url)
          ? { kind: "globalSettings" }
          : { kind: "route", route: requestedRoute }
      );
      if (navigation !== null) {
        writeCurrentRoute("replace");
        setNavigationError(null);
        setPendingNavigation(navigation);
        return;
      }
      if (isGlobalSettingsRoute(url)) {
        selectGlobalSettings({ historyMode: "replace" });
        return;
      }
      const requestedExperiment =
        requestedRoute.experimentId === null
          ? loadedExperiments[0] ?? null
          : loadedExperiments.find(
              (experiment) => experiment.id === requestedRoute.experimentId
            ) ?? loadedExperiments[0] ?? null;
      selectExperiment(requestedExperiment, {
        tab: requestedRoute.tab,
        updateUrl: false
      });
    }

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, [
    activeTab,
    appView,
    casesDirty,
    decisionsDirty,
    globalSettingsBusy,
    globalSettingsDirty,
    humanNotesDirty,
    reviewState,
    selectedExperiment,
    settingsBusy,
    settingsDirty,
    sourceDirty,
    validatorsDirty,
    validationDirty,
    validationState,
    workflowBusy,
    state
  ]);

  useEffect(() => {
    if (
      !settingsDirty &&
      !globalSettingsDirty &&
      !validationDirty &&
      !casesDirty &&
      !decisionsDirty &&
      !humanNotesDirty &&
      !sourceDirty &&
      !validatorsDirty
    ) {
      return;
    }

    function handleBeforeUnload(event: BeforeUnloadEvent) {
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [
    casesDirty,
    decisionsDirty,
    globalSettingsDirty,
    humanNotesDirty,
    settingsDirty,
    sourceDirty,
    validatorsDirty,
    validationDirty
  ]);

  useEffect(() => {
    if (selectedExperiment === null) {
      setDetailState({ status: "idle" });
      setCommittedValidationState(null);
      return;
    }

    let cancelled = false;
    setDetailState({ status: "loading" });
    setJobStatus(null);
    setCommittedValidationState(null);

    async function loadDetails(experiment: Experiment) {
      try {
        const [overview, runs, latestValidation, latestReview] = await Promise.all([
          getVersionOverview(experiment.id, experiment.active_version),
          getVersionRuns(experiment.id, experiment.active_version),
          getLatestValidationState(experiment.id, experiment.active_version),
          getLatestReviewState(experiment.id, experiment.active_version)
        ]);
        const latestProposal =
          latestReview === null
            ? null
            : await getReviewProposal(
                experiment.id,
                experiment.active_version,
                latestReview.review_id
              );
        if (!cancelled) {
          setDetailState({ status: "loaded", overview, runs });
          setCommittedValidationState(latestValidation);
          setCommittedReviewState(latestReview);
          setProposalResponse(latestProposal);
        }
      } catch (error) {
        if (!cancelled) {
          setDetailState({
            status: "error",
            message: error instanceof Error ? error.message : "Unknown error"
          });
        }
      }
    }

    void loadDetails(selectedExperiment);

    return () => {
      cancelled = true;
    };
  }, [selectedExperiment]);

  useEffect(() => {
    if (selectedExperiment === null) {
      setVersionSummaries([]);
      return;
    }

    let cancelled = false;

    async function loadVersions(experiment: Experiment) {
      try {
        const response = await getExperimentVersions(experiment.id);
        if (!cancelled) {
          setVersionSummaries(response.versions);
        }
      } catch (error) {
        if (!cancelled) {
          setWorkflowMessage(
            error instanceof Error ? error.message : "Could not load versions."
          );
        }
      }
    }

    void loadVersions(selectedExperiment);

    return () => {
      cancelled = true;
    };
  }, [selectedExperiment]);

  useEffect(() => {
    if (selectedExperiment === null) {
      setCompareValidationByVersion({});
      return;
    }

    let cancelled = false;
    const experimentId = selectedExperiment.id;
    const versions = [...new Set([baselineVersion, candidateVersion])];
    setCompareValidationByVersion({});

    async function loadCompareValidationState() {
      try {
        const entries = await Promise.all(
          versions.map(async (version) => {
            const state = await getLatestValidationState(experimentId, version);
            return [version, hasCompletedValidation(state)] as const;
          })
        );
        if (!cancelled) {
          setCompareValidationByVersion(Object.fromEntries(entries));
        }
      } catch (error) {
        if (!cancelled) {
          setCompareValidationByVersion({});
          setWorkflowMessage(
            error instanceof Error
              ? error.message
              : "Could not load validation state for comparison."
          );
        }
      }
    }

    void loadCompareValidationState();

    return () => {
      cancelled = true;
    };
  }, [baselineVersion, candidateVersion, selectedExperiment]);

  useEffect(() => {
    if (selectedExperiment === null) {
      return;
    }

    let cancelled = false;

    async function loadActiveJob() {
      try {
        if (cancelled) {
          return;
        }
        await syncActiveWorkflowJob("Resumed active workflow job.");
      } catch (error) {
        if (!cancelled) {
          setWorkflowMessage(
            error instanceof Error ? error.message : "Could not load active job."
          );
        }
      }
    }

    void loadActiveJob();

    return () => {
      cancelled = true;
    };
  }, [selectedExperiment]);

  const subtitle = useMemo(() => {
    if (appView === "caseSuites") {
      return "Manage reusable case suites";
    }
    if (appView === "globalSettings") {
      return "Application-level configuration";
    }
    if (state.status !== "loaded") {
      return "Loading local experiment manifests";
    }
    const count = state.experiments.length;
    return `${count} experiment${count === 1 ? "" : "s"} available`;
  }, [appView, state]);

  function handleSourceEdit() {
    if (detailState.status !== "loaded") {
      return;
    }
    setSourceDraft(sourceDraftFromOverview(detailState.overview));
    setSourceEditing(true);
    setSourceViewMode("edit");
    setWorkflowMessage(null);
  }

  function handleSourceDraftChange(draft: VersionSourceDraft) {
    setSourceDraft(draft);
    setWorkflowMessage(null);
  }

  function handleSourceReset() {
    if (detailState.status !== "loaded") {
      clearSourceEditor();
      return;
    }
    setSourceDraft(sourceDraftFromOverview(detailState.overview));
    setSourceViewMode("edit");
    setWorkflowMessage(null);
  }

  function requestSourceOverwrite(navigation: PendingNavigation | null = null) {
    if (sourceDraft === null || !sourceDirty || workflowBusy) {
      return;
    }
    setPendingSourceOverwrite({ navigation });
  }

  function handleCancelSourceOverwrite() {
    setPendingSourceOverwrite(null);
  }

  async function handleConfirmSourceOverwrite() {
    if (pendingSourceOverwrite === null) {
      return;
    }
    const navigation = pendingSourceOverwrite.navigation;
    setNavigationError(null);
    try {
      await handleSaveVersionSource("overwrite_current", {
        navigation,
        rethrow: true
      });
      setPendingSourceOverwrite(null);
      if (navigation !== null) {
        setPendingNavigation(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      if (navigation !== null) {
        setNavigationError(message);
      }
      setPendingSourceOverwrite(null);
    }
  }

  async function refreshCurrentVersionAfterSourceOverwrite(
    experiment: Experiment,
    version: string
  ) {
    const [overview, runs, latestValidation, latestReview] = await Promise.all([
      getVersionOverview(experiment.id, version),
      getVersionRuns(experiment.id, version),
      getLatestValidationState(experiment.id, version),
      getLatestReviewState(experiment.id, version)
    ]);
    const latestProposal =
      latestReview === null
        ? null
        : await getReviewProposal(experiment.id, version, latestReview.review_id);
    setDetailState({ status: "loaded", overview, runs });
    setCommittedValidationState(latestValidation);
    setCompareValidationByVersion({});
    setCommittedReviewState(latestReview);
    setProposalResponse(latestProposal);
    setCreatedVersion(null);
    setComparison(null);
  }

  async function handleSaveVersionSource(
    mode: VersionSourceSaveMode,
    options?: { navigation?: PendingNavigation | null; rethrow?: boolean }
  ) {
    if (
      selectedExperiment === null ||
      detailState.status !== "loaded" ||
      sourceDraft === null
    ) {
      return;
    }
    const experiment = selectedExperiment;
    const version = experiment.active_version;
    const navigation = options?.navigation ?? null;
    setWorkflowBusy(true);
    setWorkflowMessage(
      mode === "create_next"
        ? "Saving source as next version..."
        : "Overwriting current version..."
    );
    try {
      const response = await updateVersionSource(experiment.id, version, {
        mode,
        prompt: sourceDraft.prompt,
        model_py:
          detailState.overview.experiment.output.type === "pydantic"
            ? sourceDraft.model_py ?? ""
            : null
      });
      setVersionSummaries((current) => {
        if (current.some((summary) => summary.version === response.version)) {
          return current;
        }
        return [...current, { version: response.version, is_active: false }].sort(
          (left, right) => left.version.localeCompare(right.version)
        );
      });

      if (mode === "create_next") {
        const savedExperiment = await updateExperiment(experiment.id, {
          ...experiment,
          active_version: response.version
        });
        setCommittedReviewState(null);
        setProposalResponse(null);
        setCreatedVersion(null);
        setComparison(null);
        setCompareValidationByVersion({});
        await refreshExperimentsAfterSettingsSave(savedExperiment);
        clearSourceEditor();
        setWorkflowMessage(`Created ${response.version} and switched to it.`);
        activateTab("prompt");
      } else {
        await refreshCurrentVersionAfterSourceOverwrite(experiment, version);
        clearSourceEditor({ clearPendingOverwrite: false });
        setWorkflowMessage(`Overwrote ${version} and cleared generated artifacts.`);
        activateTab("prompt");
      }

      if (navigation !== null) {
        await performPendingNavigation(navigation);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setWorkflowMessage(message);
      if (options?.rethrow) {
        throw error;
      }
    } finally {
      setWorkflowBusy(false);
    }
  }

  function handleValidatorsDraftChange(draft: VersionValidatorsDraft | null) {
    const hadDirtyDraft = validatorsDirty;
    setValidatorsDraft(draft);
    setValidatorsDirty(draft !== null);
    if (draft === null && preserveNextValidatorsCleanMessageRef.current) {
      preserveNextValidatorsCleanMessageRef.current = false;
      return;
    }
    if (draft !== null) {
      preserveNextValidatorsCleanMessageRef.current = false;
      setWorkflowMessage(null);
    } else if (hadDirtyDraft) {
      setWorkflowMessage(null);
    }
  }

  function handleValidatorsReset() {
    clearValidatorEditor();
    setWorkflowMessage(null);
  }

  function requestValidatorsOverwrite(
    navigation: PendingNavigation | null = null
  ) {
    if (validatorsDraft === null || !validatorsDirty || workflowBusy) {
      return;
    }
    setPendingValidatorsOverwrite({ navigation });
  }

  function handleCancelValidatorsOverwrite() {
    setPendingValidatorsOverwrite(null);
  }

  async function handleConfirmValidatorsOverwrite() {
    if (pendingValidatorsOverwrite === null) {
      return;
    }
    const navigation = pendingValidatorsOverwrite.navigation;
    setNavigationError(null);
    try {
      await handleSaveVersionValidators("overwrite_current", {
        navigation,
        rethrow: true
      });
      setPendingValidatorsOverwrite(null);
      if (navigation !== null) {
        setPendingNavigation(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      if (navigation !== null) {
        setNavigationError(message);
      }
      setPendingValidatorsOverwrite(null);
    }
  }

  async function refreshCurrentVersionAfterValidatorsOverwrite(
    experiment: Experiment,
    version: string
  ) {
    const [overview, runs] = await Promise.all([
      getVersionOverview(experiment.id, version),
      getVersionRuns(experiment.id, version)
    ]);
    setDetailState({ status: "loaded", overview, runs });
    setCommittedValidationState(null);
    setCompareValidationByVersion({});
    setCommittedReviewState(null);
    setProposalResponse(null);
    setCreatedVersion(null);
    setComparison(null);
  }

  function caseInclusionMatchesOverview(nextCases: Case[]): boolean {
    if (detailState.status !== "loaded") {
      return false;
    }
    return caseInclusionMatchesCases(
      nextCases,
      detailState.overview.cases
    );
  }

  function handleCasesDraftChange(nextCases: Case[]) {
    const isDirty = !caseInclusionMatchesOverview(nextCases);
    setCasesDraft(isDirty ? nextCases : null);
    setCasesDirty(isDirty);
    setWorkflowMessage(null);
  }

  async function handleSaveCaseInclusion(options?: { rethrow?: boolean }) {
    if (
      selectedExperiment === null ||
      detailState.status !== "loaded" ||
      casesDraft === null
    ) {
      return;
    }
    const experiment = selectedExperiment;
    const version = detailState.overview.version;
    setWorkflowBusy(true);
    setWorkflowMessage("Saving case inclusion...");
    try {
      const response = await saveCaseInclusion(experiment.id, {
        excluded_case_ids: casesDraft
          .filter((artifactCase) => !artifactCase.enabled)
          .map((artifactCase) => artifactCase.id)
      });
      const runs = await getVersionRuns(experiment.id, version);
      const overview = {
        ...detailState.overview,
        experiment: response.experiment,
        cases: response.cases
      };
      setSelectedExperiment(response.experiment);
      setState((current) => {
        if (current.status !== "loaded") {
          return current;
        }
        return {
          status: "loaded",
          experiments: current.experiments.map((item) =>
            item.id === response.experiment.id ? response.experiment : item
          )
        };
      });
      setDetailState({ status: "loaded", overview, runs });
      setCommittedValidationState(null);
      setCompareValidationByVersion({});
      setCommittedReviewState(null);
      setProposalResponse(null);
      setCreatedVersion(null);
      setComparison(null);
      setCasesDraft(null);
      setCasesDirty(false);
      setWorkflowMessage("Case inclusion saved.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setWorkflowMessage(message);
      if (options?.rethrow) {
        throw error;
      }
    } finally {
      setWorkflowBusy(false);
    }
  }

  function handleCaseSuiteCasesChange(nextCases: Case[]) {
    setCaseSuiteCases(nextCases);
    setCaseSuiteCasesDirty(
      !caseSuiteCasesMatch(nextCases, caseSuiteCasesBaseline)
    );
    setCaseSuiteMessage(null);
  }

  function handleResetCaseSuiteCases() {
    setCaseSuiteCases(cloneCases(caseSuiteCasesBaseline));
    setCaseSuiteCasesDirty(false);
    setCaseSuiteMessage("Case suite case changes reset.");
  }

  async function handleCreateCaseSuite(request: CaseSuiteCreateRequest) {
    if (caseSuiteCasesDirty) {
      setCaseSuiteMessage("Save or reset case changes before creating suites.");
      return;
    }
    setCaseSuiteBusy(true);
    setCaseSuiteMessage("Creating case suite...");
    try {
      const created = await createCaseSuite(request);
      await refreshCaseSuites(created.id);
      setCaseSuiteMessage("Case Suite created.");
    } catch (error) {
      setCaseSuiteMessage(error instanceof Error ? error.message : "Unknown error");
      throw error;
    } finally {
      setCaseSuiteBusy(false);
    }
  }

  async function handleUpdateCaseSuite(
    suiteId: string,
    request: CaseSuiteUpdateRequest
  ) {
    if (caseSuiteCasesDirty) {
      setCaseSuiteMessage("Save or reset case changes before updating suites.");
      return;
    }
    setCaseSuiteBusy(true);
    setCaseSuiteMessage("Saving case suite...");
    try {
      const updated = await updateCaseSuite(suiteId, request);
      await refreshCaseSuites(updated.id);
      setCaseSuiteMessage("Case Suite saved.");
    } catch (error) {
      setCaseSuiteMessage(error instanceof Error ? error.message : "Unknown error");
      throw error;
    } finally {
      setCaseSuiteBusy(false);
    }
  }

  async function handleDeleteCaseSuite(suiteId: string) {
    if (caseSuiteCasesDirty) {
      setCaseSuiteMessage("Save or reset case changes before deleting suites.");
      return;
    }
    setCaseSuiteBusy(true);
    setCaseSuiteMessage("Deleting case suite...");
    try {
      await deleteCaseSuite(suiteId);
      await refreshCaseSuites(null);
      setCaseSuiteMessage("Case Suite deleted.");
    } catch (error) {
      setCaseSuiteMessage(error instanceof Error ? error.message : "Unknown error");
      throw error;
    } finally {
      setCaseSuiteBusy(false);
    }
  }

  async function refreshCurrentExperimentAfterCaseSuiteSave(
    affectedExperimentIds: string[]
  ) {
    if (
      selectedExperiment === null ||
      detailState.status !== "loaded" ||
      !affectedExperimentIds.includes(selectedExperiment.id)
    ) {
      return;
    }
    const version = detailState.overview.version;
    const [overview, runs] = await Promise.all([
      getVersionOverview(selectedExperiment.id, version),
      getVersionRuns(selectedExperiment.id, version)
    ]);
    setDetailState({ status: "loaded", overview, runs });
    setCommittedValidationState(null);
    setCompareValidationByVersion({});
    setCommittedReviewState(null);
    setProposalResponse(null);
    setCreatedVersion(null);
    setComparison(null);
    clearCaseEditor();
  }

  async function handleSaveCaseSuiteCases() {
    if (selectedCaseSuiteId === null) {
      return;
    }
    setCaseSuiteBusy(true);
    setCaseSuiteMessage("Saving case suite cases...");
    try {
      const response = await saveCaseSuiteCases(selectedCaseSuiteId, {
        cases: caseSuiteCases.map((artifactCase) => ({
          case_id: artifactCase.id,
          payload: artifactCase.payload
        }))
      });
      setCaseSuiteCases(cloneCases(response.cases));
      setCaseSuiteCasesBaseline(cloneCases(response.cases));
      setCaseSuiteCasesDirty(false);
      await refreshCaseSuites(selectedCaseSuiteId);
      await refreshCurrentExperimentAfterCaseSuiteSave(
        response.affected_experiment_ids
      );
      setCaseSuiteMessage(
        response.affected_experiment_ids.length > 0
          ? `Case Suite cases saved. Invalidated generated artifacts for ${response.affected_experiment_ids.join(
              ", "
            )}.`
          : "Case Suite cases saved."
      );
    } catch (error) {
      setCaseSuiteMessage(error instanceof Error ? error.message : "Unknown error");
      throw error;
    } finally {
      setCaseSuiteBusy(false);
    }
  }

  async function handleSaveVersionValidators(
    mode: VersionValidatorsSaveMode,
    options?: { navigation?: PendingNavigation | null; rethrow?: boolean }
  ) {
    if (
      selectedExperiment === null ||
      detailState.status !== "loaded" ||
      validatorsDraft === null
    ) {
      return;
    }
    const experiment = selectedExperiment;
    const version = experiment.active_version;
    const navigation = options?.navigation ?? null;
    setWorkflowBusy(true);
    setWorkflowMessage(
      mode === "create_next"
        ? "Saving validators as next version..."
        : "Overwriting current validators..."
    );
    try {
      const response = await updateVersionValidators(experiment.id, version, {
        mode,
        validators: validatorsDraft.validators
      });
      setVersionSummaries((current) => {
        if (current.some((summary) => summary.version === response.version)) {
          return current;
        }
        return [...current, { version: response.version, is_active: false }].sort(
          (left, right) => left.version.localeCompare(right.version)
        );
      });

      if (mode === "create_next") {
        const savedExperiment = await updateExperiment(experiment.id, {
          ...experiment,
          active_version: response.version
        });
        setCommittedValidationState(null);
        setCompareValidationByVersion({});
        setCommittedReviewState(null);
        setProposalResponse(null);
        setCreatedVersion(null);
        setComparison(null);
        await refreshExperimentsAfterSettingsSave(savedExperiment);
        clearValidatorEditor();
        preserveNextValidatorsCleanMessageRef.current = true;
        setWorkflowMessage(`Created ${response.version} and switched to it.`);
        activateTab("validators");
      } else {
        await refreshCurrentVersionAfterValidatorsOverwrite(experiment, version);
        clearValidatorEditor({ clearPendingOverwrite: false });
        preserveNextValidatorsCleanMessageRef.current = true;
        setWorkflowMessage(
          `Overwrote validators for ${version} and cleared generated validation artifacts.`
        );
        activateTab("validators");
      }

      if (navigation !== null) {
        await performPendingNavigation(navigation);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setWorkflowMessage(message);
      if (options?.rethrow) {
        throw error;
      }
    } finally {
      setWorkflowBusy(false);
    }
  }

  async function handleRunVersion() {
    if (selectedExperiment === null || detailState.status !== "loaded") {
      return;
    }
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (casesDirty) {
      setWorkflowMessage("Save case inclusion before running.");
      return;
    }

    const overview = detailState.overview;
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestId = runRequestIdRef.current + 1;
    runRequestIdRef.current = requestId;
    const isCurrentRequest = () =>
      runRequestIdRef.current === requestId && selectedKeyRef.current === selectionKey;

    try {
      setJobStatus({
        job_id: "",
        kind: "run_version",
        experiment_id: experimentId,
        version,
        status: "running",
        completed_units: 0,
        total_units:
          overview.cases.length * selectedExperiment.run_defaults.repeat_count,
        message: "Starting run",
        started_at: new Date().toISOString()
      });
      const dryRun = workflowMode === "dry-run";
      let job = await runVersion(experimentId, version, { dry_run: dryRun });
      if (!isCurrentRequest()) {
        return;
      }
      setJobStatus(job);
      setCommittedValidationState(null);
      setCompareValidationByVersion((current) => ({
        ...current,
        [version]: false
      }));
      setCommittedReviewState(null);
      setProposalResponse(null);
      setCreatedVersion(null);
      setComparison(null);

      job = await followJobEvents(job.job_id, job, isCurrentRequest);
      if (job.status === "cancelled") {
        if (isCurrentRequest()) {
          setWorkflowMessage("Workflow job cancelled.");
        }
        return;
      }
      if (job.status === "failed") {
        throw new Error(job.message || "Run failed.");
      }

      const runs = await getVersionRuns(experimentId, version);
      if (!isCurrentRequest()) {
        return;
      }
      setDetailState({ status: "loaded", overview, runs });
      setWorkflowMessage(
        dryRun
          ? "Dry-run generated the active run."
          : "Active run completed."
      );
      activateTab("runs");
    } catch (error) {
      if (!isCurrentRequest()) {
        return;
      }
      setJobStatus(null);
      setDetailState({
        status: "error",
        message: error instanceof Error ? error.message : "Unknown error"
      });
    }
  }

  function handleRejectPromptPreview() {
    setPromptPreview(null);
    setPromptPreviewAction(null);
  }

  function handleAcceptPromptPreview() {
    const action = promptPreviewAction;
    setPromptPreview(null);
    setPromptPreviewAction(null);
    if (action !== null) {
      void action();
    }
  }

  async function handlePreviewRunPrompts() {
    if (selectedExperiment === null || detailState.status !== "loaded") {
      return;
    }
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (casesDirty) {
      setWorkflowMessage("Save case inclusion before previewing run prompts.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    try {
      setWorkflowBusy(true);
      setWorkflowMessage("Preparing prompt preview...");
      const preview = await previewRunPrompts(experimentId, version);
      setPromptPreview(preview);
      setPromptPreviewAction(() => handleRunVersion);
      setWorkflowMessage(null);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setWorkflowBusy(false);
    }
  }

  async function handlePreviewValidationPrompts() {
    if (selectedExperiment === null || detailState.status !== "loaded") {
      return;
    }
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (detailState.runs.runs.length === 0) {
      setWorkflowMessage("Create a run before validating.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    try {
      setWorkflowBusy(true);
      setWorkflowMessage("Preparing validation prompt preview...");
      const preview = await previewValidationPrompts(experimentId, version);
      setPromptPreview(preview);
      setPromptPreviewAction(() => handleValidateVersion);
      setWorkflowMessage(null);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setWorkflowBusy(false);
    }
  }

  async function handlePreviewJudgePrompts() {
    if (selectedExperiment === null) return;
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (!hasCompletedValidation(validationState)) {
      setWorkflowMessage("Validate the active run before judging.");
      return;
    }
    if (validationDirty) {
      setWorkflowMessage("Save validation inclusion before judging.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    try {
      setWorkflowBusy(true);
      setWorkflowMessage("Preparing judge prompt preview...");
      const preview = await previewJudgePrompts(experimentId, version);
      setPromptPreview(preview);
      setPromptPreviewAction(() => handleJudgeVersion);
      setWorkflowMessage(null);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setWorkflowBusy(false);
    }
  }

  async function handlePreviewProposalPrompts() {
    if (selectedExperiment === null || reviewState === null) return;
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (decisionsDirty || humanNotesDirty) {
      setWorkflowMessage("Save review changes before generating a proposal.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    try {
      setWorkflowBusy(true);
      setWorkflowMessage("Preparing proposal prompt preview...");
      const preview = await previewProposalPrompts(
        experimentId,
        version,
        reviewState.review_id
      );
      setPromptPreview(preview);
      setPromptPreviewAction(() => handleGenerateProposal);
      setWorkflowMessage(null);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setWorkflowBusy(false);
    }
  }

  async function handleCancelWorkflowJob() {
    if (jobStatus?.status !== "running") {
      return;
    }
    try {
      const cancelledJob = await cancelJob(jobStatus.job_id);
      setJobStatus(cancelledJob);
      setWorkflowBusy(false);
      setWorkflowMessage("Workflow job cancelled.");
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
    }
  }

  function followJobEvents(
    jobId: string,
    initialJob: JobStatus,
    isCurrentRequest: () => boolean
  ): Promise<JobStatus> {
    if (initialJob.status !== "running") {
      return Promise.resolve(initialJob);
    }

    return new Promise((resolve, reject) => {
      const source = new EventSource(jobEventsStreamUrl(jobId));
      let latestJob = initialJob;

      source.addEventListener("job", (event) => {
        if (!isCurrentRequest()) {
          source.close();
          resolve(latestJob);
          return;
        }
        const jobEvent = JSON.parse((event as MessageEvent).data) as JobEvent;
        latestJob = {
          ...latestJob,
          status: jobEvent.status,
          completed_units: jobEvent.completed_units,
          total_units: jobEvent.total_units,
          message: jobEvent.message
        };
        setJobStatus(latestJob);
        if (latestJob.status !== "running") {
          source.close();
          resolve(latestJob);
        }
      });

      source.addEventListener("error", () => {
        source.close();
        void (async () => {
          for (let attempt = 0; attempt < 12; attempt += 1) {
            const job = await getJob(jobId);
            latestJob = job;
            if (isCurrentRequest()) {
              setJobStatus(latestJob);
            }
            if (latestJob.status === "running") {
              await new Promise((pollResolve) => {
                window.setTimeout(pollResolve, 500);
              });
              continue;
            }
            resolve(latestJob);
            return;
          }
          reject(new Error("Lost job event stream."));
        })().catch(() => reject(new Error("Lost job event stream.")));
      });
    });
  }

  async function handleValidateVersion() {
    if (selectedExperiment === null || detailState.status !== "loaded") {
      return;
    }
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (detailState.runs.runs.length === 0) {
      setWorkflowMessage("Create a run before validating.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const dryRun = workflowMode === "dry-run";
    const requestId = beginWorkflow(
      selectionKey,
      dryRun ? "Dry-run validating active run..." : "Validating active run..."
    );
    try {
      const latestValidation = await validateVersion(experimentId, version, dryRun);
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setCommittedValidationState(latestValidation);
      setCompareValidationByVersion((current) => ({
        ...current,
        [version]: hasCompletedValidation(latestValidation)
      }));
      setCommittedReviewState(null);
      setProposalResponse(null);
      setCreatedVersion(null);
      setComparison(null);
      setWorkflowMessage(
        dryRun
          ? "Dry-run validation loaded."
          : "Validation completed."
      );
      activateTab("validation");
    } catch (error) {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
    } finally {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowBusy(false);
      }
    }
  }

  function handleValidationStateChange(nextState: ValidationState) {
    setValidationState(nextState);
    setValidationDirty(true);
    setWorkflowMessage(null);
    setCommittedReviewState(null);
    setProposalResponse(null);
    setCreatedVersion(null);
    setComparison(null);
  }

  async function handleSaveValidationInclusion(options?: { rethrow?: boolean }) {
    if (selectedExperiment === null || validationState === null) {
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestId = beginWorkflow(selectionKey, "Saving validation inclusion...");
    try {
      const savedValidation = await updateValidationInclusion(
        experimentId,
        version,
        validationState.validation_batch.validation_batch_id,
        buildValidationInclusionUpdate(validationState)
      );
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setCommittedValidationState(savedValidation);
      setCompareValidationByVersion((current) => ({
        ...current,
        [version]: hasCompletedValidation(savedValidation)
      }));
      setCommittedReviewState(null);
      setProposalResponse(null);
      setCreatedVersion(null);
      setComparison(null);
      setWorkflowMessage("Validation inclusion saved.");
    } catch (error) {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
      if (options?.rethrow) {
        throw error;
      }
    } finally {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowBusy(false);
      }
    }
  }

  async function handleJudgeVersion() {
    if (selectedExperiment === null) return;
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (!hasCompletedValidation(validationState)) {
      setWorkflowMessage("Validate the active run before judging.");
      return;
    }
    if (validationDirty) {
      setWorkflowMessage("Save validation inclusion before judging.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const dryRun = workflowMode === "dry-run";
    const requestId = beginWorkflow(
      selectionKey,
      dryRun ? "Dry-run judging active run..." : "Judging active run..."
    );
    try {
      const response = await judgeVersion(experimentId, version, dryRun);
      const review = await getReviewState(experimentId, version, response.review_id);
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setCommittedReviewState(review);
      setProposalResponse(null);
      setCreatedVersion(null);
      setWorkflowMessage(
        dryRun
          ? "Dry-run review loaded as the active review."
          : "Active review loaded."
      );
      activateTab("review");
    } catch (error) {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
    } finally {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowBusy(false);
      }
    }
  }

  function handleDecisionChange(
    findingId: string,
    decision: FindingDecisionValue,
    reason: string | null
  ) {
    setReviewState((current) => {
      if (current === null) return current;
      return {
        ...current,
        decisions: {
          ...current.decisions,
          finding_decisions: {
            ...current.decisions.finding_decisions,
            [findingId]: {
              decision,
              reason: reason?.trim() ? reason : null
            }
          }
        }
      };
    });
    setDecisionsDirty(true);
    setWorkflowMessage(null);
    setProposalResponse(null);
    setCreatedVersion(null);
  }

  async function handleSaveReviewChanges(options?: { rethrow?: boolean }) {
    if (selectedExperiment === null || reviewState === null) return;
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const draftReview = snapshotReviewState(reviewState);
    if (draftReview === null) return;
    const requestId = beginWorkflow(selectionKey, "Saving review changes...");
    try {
      let savedReview = draftReview;
      if (decisionsDirty) {
        const decisions = await updateReviewDecisions(
          experimentId,
          version,
          draftReview.review_id,
          draftReview.decisions
        );
        savedReview = { ...savedReview, decisions };
      }
      if (humanNotesDirty) {
        const response = await updateHumanNotes(
          experimentId,
          version,
          draftReview.review_id,
          draftReview.human_notes
        );
        savedReview = { ...savedReview, human_notes: response.human_notes };
      }
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setCommittedReviewState(savedReview);
      setWorkflowMessage("Review changes saved.");
    } catch (error) {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
      if (options?.rethrow) {
        throw error;
      }
    } finally {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowBusy(false);
      }
    }
  }

  function handleHumanNotesChange(notes: string) {
    setReviewState((current) =>
      current === null ? current : { ...current, human_notes: notes }
    );
    setHumanNotesDirty(true);
    setWorkflowMessage(null);
    setProposalResponse(null);
    setCreatedVersion(null);
  }

  async function handleGenerateProposal() {
    if (selectedExperiment === null || reviewState === null) return;
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    if (decisionsDirty || humanNotesDirty) {
      setWorkflowMessage("Save review changes before generating a proposal.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const dryRun = workflowMode === "dry-run";
    const requestId = beginWorkflow(
      selectionKey,
      dryRun ? "Dry-run generating proposal..." : "Generating proposal..."
    );
    try {
      const response = await generateProposal(
        experimentId,
        version,
        reviewState.review_id,
        dryRun
      );
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setProposalResponse(response);
      setCreatedVersion(null);
      setWorkflowMessage(dryRun ? "Dry-run proposal generated." : "Proposal generated.");
      activateTab("proposal");
    } catch (error) {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
    } finally {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowBusy(false);
      }
    }
  }

  async function handleCreateVersion() {
    if (selectedExperiment === null || reviewState === null) return;
    const experiment = selectedExperiment;
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestId = beginWorkflow(selectionKey);
    try {
      const response = await createProposalVersion(
        experimentId,
        version,
        reviewState.review_id
      );
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setCreatedVersion(response);
      setVersionSummaries((current) => {
        if (current.some((summary) => summary.version === response.version)) {
          return current;
        }
        return [...current, { version: response.version, is_active: false }].sort(
          (left, right) => left.version.localeCompare(right.version)
        );
      });
      candidateVersionRef.current = response.version;
      setCandidateVersion(response.version);
      setComparison(null);
      const savedExperiment = await updateExperiment(experimentId, {
        ...experiment,
        active_version: response.version
      });
      setCommittedReviewState(null);
      setProposalResponse(null);
      await refreshExperimentsAfterSettingsSave(savedExperiment);
      setWorkflowMessage(`Created ${response.version} and switched to it.`);
      activateTab("prompt");
    } catch (error) {
      if (workflowRequestIdRef.current === requestId) {
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
    } finally {
      if (workflowRequestIdRef.current === requestId) {
        setWorkflowBusy(false);
      }
    }
  }

  async function handleCompareVersions() {
    if (selectedExperiment === null) return;
    if (workflowLocked) {
      setWorkflowMessage("Wait for the current workflow action to finish.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestedBaseline = baselineVersion;
    const requestedCandidate = candidateVersion;
    if (requestedBaseline === requestedCandidate) {
      setWorkflowMessage(
        knownVersions.length < 2
          ? "Create another version before comparing."
          : "Choose two different versions before comparing."
      );
      return;
    }
    if (hasUnsavedCompareValidationChanges) {
      setWorkflowMessage("Save validation inclusion before comparing.");
      return;
    }
    if (!hasComparedValidation) {
      setWorkflowMessage("Validate both versions before comparing.");
      return;
    }
    const dryRun = workflowMode === "dry-run";
    const requestId = beginWorkflow(
      selectionKey,
      dryRun ? "Dry-run comparing versions..." : "Comparing versions..."
    );
    try {
      const response = await compareVersions(
        experimentId,
        requestedBaseline,
        requestedCandidate,
        dryRun
      );
      if (
        !isWorkflowCurrent(requestId, selectionKey) ||
        requestedBaseline !== baselineVersionRef.current ||
        requestedCandidate !== candidateVersionRef.current
      ) {
        return;
      }
      setComparison(response);
      setWorkflowMessage(
        dryRun
          ? "Dry-run comparison loaded."
          : "Comparison loaded."
      );
      activateTab("compare");
    } catch (error) {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
      }
    } finally {
      if (isWorkflowCurrent(requestId, selectionKey)) {
        setWorkflowBusy(false);
      }
    }
  }

  function handleBaselineVersionChange(version: string) {
    baselineVersionRef.current = version;
    setBaselineVersion(version);
    setComparison(null);
    setWorkflowMessage(null);
  }

  function handleCandidateVersionChange(version: string) {
    candidateVersionRef.current = version;
    setCandidateVersion(version);
    setComparison(null);
    setWorkflowMessage(null);
  }

  async function handleCreateExperiment(request: ExperimentCreateRequest) {
    setExperimentActionBusy(true);
    setExperimentActionError(null);
    try {
      const created = await createExperiment(request);
      setExperimentDialog(null);
      await routeAfterExperimentMutation(created, "prompt");
      setWorkflowMessage(`Created ${created.title}.`);
    } catch (error) {
      setExperimentActionError(
        error instanceof Error ? error.message : "Unknown error"
      );
      throw error;
    } finally {
      setExperimentActionBusy(false);
    }
  }

  async function handleCloneExperiment(request: ExperimentCloneRequest) {
    if (experimentDialog?.kind !== "clone") return;
    const sourceExperiment = experimentDialog.experiment;
    setExperimentActionBusy(true);
    setExperimentActionError(null);
    try {
      const cloned = await cloneExperiment(sourceExperiment.id, request);
      setExperimentDialog(null);
      await routeAfterExperimentMutation(cloned, "settings");
      setSettingsMessage(`Cloned ${sourceExperiment.title}.`);
    } catch (error) {
      setExperimentActionError(
        error instanceof Error ? error.message : "Unknown error"
      );
      throw error;
    } finally {
      setExperimentActionBusy(false);
    }
  }

  async function handleDeleteExperiment() {
    if (experimentDialog?.kind !== "delete") return;
    const deletedExperiment = experimentDialog.experiment;
    setExperimentActionBusy(true);
    setExperimentActionError(null);
    try {
      await deleteExperiment(deletedExperiment.id);
      setExperimentDialog(null);
      await refreshAfterExperimentDelete(deletedExperiment.id);
      setWorkflowMessage(`Deleted ${deletedExperiment.title}.`);
    } catch (error) {
      setExperimentActionError(
        error instanceof Error ? error.message : "Unknown error"
      );
      throw error;
    } finally {
      setExperimentActionBusy(false);
    }
  }

  async function refreshExperimentsAfterSettingsSave(savedExperiment: Experiment) {
    const [experiments, overview, runs, latestValidation, versions, suites] =
      await Promise.all([
        apiGet<Experiment[]>("/api/experiments"),
        getVersionOverview(savedExperiment.id, savedExperiment.active_version),
        getVersionRuns(savedExperiment.id, savedExperiment.active_version),
        getLatestValidationState(savedExperiment.id, savedExperiment.active_version),
        getExperimentVersions(savedExperiment.id),
        getCaseSuites()
      ]);
    setState({ status: "loaded", experiments });
    setCaseSuites(suites);
    setSelectedExperiment(savedExperiment);
    selectedKeyRef.current = `${savedExperiment.id}:${savedExperiment.active_version}`;
    setDetailState({ status: "loaded", overview, runs });
    setCommittedValidationState(latestValidation);
    setCompareValidationByVersion({});
    setVersionSummaries(versions.versions);
    setCandidateVersion(savedExperiment.active_version);
    candidateVersionRef.current = savedExperiment.active_version;
    if (!experiments.some((experiment) => experiment.id === savedExperiment.id)) {
      setWorkflowMessage("Saved experiment is no longer listed.");
    }
  }

  async function handleSaveExperimentSettings(experiment: Experiment) {
    if (selectedExperiment === null) return;
    setSettingsBusy(true);
    setSettingsMessage(null);
    try {
      const savedExperiment = await updateExperiment(selectedExperiment.id, experiment);
      await refreshExperimentsAfterSettingsSave(savedExperiment);
      setSettingsMessage("Settings saved.");
      setSettingsDirty(false);
      setSettingsDraft(null);
      activateTab("settings");
    } catch (error) {
      setSettingsMessage(error instanceof Error ? error.message : "Unknown error");
      throw error;
    } finally {
      setSettingsBusy(false);
    }
  }

  function handleResetExperimentSettings() {
    setSettingsMessage(null);
  }

  async function handleSaveGlobalSettings(settings: GlobalSettingsModel) {
    setGlobalSettingsBusy(true);
    setGlobalSettingsMessage(null);
    try {
      const savedSettings = await updateGlobalSettings(settings);
      setGlobalSettingsState({ status: "loaded", settings: savedSettings });
      setGlobalSettingsMessage("Global settings saved.");
      setGlobalSettingsDirty(false);
      setGlobalSettingsDraft(null);
      writeGlobalSettingsRoute("replace");
    } catch (error) {
      setGlobalSettingsMessage(
        error instanceof Error ? error.message : "Unknown error"
      );
      throw error;
    } finally {
      setGlobalSettingsBusy(false);
    }
  }

  function handleResetGlobalSettings() {
    setGlobalSettingsMessage(null);
  }

  async function handleActiveVersionChange(version: string) {
    const navigation = buildPendingNavigation({ kind: "version", version });
    if (navigation !== null) {
      setNavigationError(null);
      setPendingNavigation(navigation);
      return;
    }
    await performActiveVersionChange(version);
  }

  async function performActiveVersionChange(version: string) {
    if (selectedExperiment === null || version === selectedExperiment.active_version) {
      return;
    }
    setWorkflowBusy(true);
    setWorkflowMessage(`Switching to ${version}...`);
    setPromptPreview(null);
    setPromptPreviewAction(null);
    setCommittedValidationState(null);
    setCompareValidationByVersion({});
    setCommittedReviewState(null);
    setProposalResponse(null);
    setCreatedVersion(null);
    setComparison(null);
    clearCaseEditor();
    try {
      const savedExperiment = await updateExperiment(selectedExperiment.id, {
        ...selectedExperiment,
        active_version: version
      });
      await refreshExperimentsAfterSettingsSave(savedExperiment);
      setWorkflowMessage(`Switched to ${version}.`);
      activateTab(activeTab);
    } catch (error) {
      setWorkflowMessage(error instanceof Error ? error.message : "Unknown error");
    } finally {
      setWorkflowBusy(false);
    }
  }

  const knownVersions = useMemo(() => {
    const versions = new Set(versionSummaries.map((summary) => summary.version));
    if (selectedExperiment !== null) versions.add(selectedExperiment.active_version);
    versions.add("v001");
    if (createdVersion !== null) versions.add(createdVersion.version);
    versions.add(baselineVersion);
    versions.add(candidateVersion);
    return [...versions].sort();
  }, [
    baselineVersion,
    candidateVersion,
    createdVersion,
    selectedExperiment,
    versionSummaries
  ]);

  const activeVersionOptions = useMemo(() => {
    const versions = new Set(versionSummaries.map((summary) => summary.version));
    if (selectedExperiment !== null) {
      versions.add(selectedExperiment.active_version);
    }
    if (createdVersion !== null) {
      versions.add(createdVersion.version);
    }
    return [...versions].sort();
  }, [createdVersion, selectedExperiment, versionSummaries]);

  const hasRuns = detailState.status === "loaded" && detailState.runs.runs.length > 0;
  const hasValidation = hasCompletedValidation(validationState);
  const hasComparedValidation =
    baselineVersion !== candidateVersion &&
    Boolean(compareValidationByVersion[baselineVersion]) &&
    Boolean(compareValidationByVersion[candidateVersion]);
  const activeVersion = selectedExperiment?.active_version ?? null;
  const hasUnsavedCompareValidationChanges =
    validationDirty &&
    activeVersion !== null &&
    (baselineVersion === activeVersion || candidateVersion === activeVersion);
  const workflowLocked = workflowBusy || jobStatus?.status === "running";
  const runActionDisabled = workflowLocked || casesDirty;
  const runActionDisabledReason = workflowLocked
    ? "Wait for the current run to finish."
    : casesDirty
      ? "Save case inclusion before running or previewing."
      : null;
  const judgeAction = getJudgeActionState({
    hasReview: reviewState !== null,
    hasRuns,
    hasUnsavedValidationChanges: validationDirty,
    hasValidation,
    isBusy: workflowLocked
  });
  const validateAction = getValidateActionState({
    hasRuns,
    hasValidation,
    isBusy: workflowLocked
  });
  const compareAction = getCompareActionState({
    hasComparison: comparison !== null,
    hasUnsavedValidationChanges: hasUnsavedCompareValidationChanges,
    hasValidation: hasComparedValidation,
    isBusy: workflowLocked,
    sameVersion: baselineVersion === candidateVersion,
    versionCount: knownVersions.length
  });
  const pendingNavigationKind = pendingNavigation?.unsavedKind ?? null;
  const pendingNavigationDialog = pendingNavigationCopy(pendingNavigationKind);
  const pendingNavigationSaveDisabled =
    navigationSaving || !canSavePendingNavigation(pendingNavigationKind);
  const hasUnsavedReviewChanges = decisionsDirty || humanNotesDirty;
  const workflowUnsavedChangesAction =
    activeTab === "validation" && validationDirty ? (
      <div className="workflow-unsaved-action">
        <span>Unsaved inclusion changes.</span>
        <TooltipButton
          className="secondary-action"
          disabled={workflowLocked || validationState === null}
          disabledReason={
            workflowLocked
              ? "Wait for the current workflow action to finish."
              : "Change validation inclusion before saving."
          }
          onClick={() => void handleSaveValidationInclusion()}
          type="button"
        >
          Save
        </TooltipButton>
      </div>
    ) : activeTab === "review" && hasUnsavedReviewChanges ? (
      <div className="workflow-unsaved-action">
        <span>Unsaved review changes.</span>
        <TooltipButton
          className="secondary-action"
          disabled={workflowLocked || reviewState === null}
          disabledReason={
            workflowLocked
              ? "Wait for the current workflow action to finish."
              : "Change review decisions or human notes before saving."
          }
          onClick={() => void handleSaveReviewChanges()}
          type="button"
        >
          Save
        </TooltipButton>
      </div>
    ) : activeTab === "cases" && casesDirty ? (
      <div className="workflow-unsaved-action">
        <span>Unsaved case inclusion changes.</span>
        <TooltipButton
          className="secondary-action"
          disabled={workflowLocked || casesDraft === null}
          disabledReason={
            workflowLocked
              ? "Wait for the current workflow action to finish."
              : "Change case inclusion before saving."
          }
          onClick={() => void handleSaveCaseInclusion()}
          type="button"
        >
          Save
        </TooltipButton>
      </div>
    ) : null;

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>Prompt Lab</h1>
          <p>{subtitle}</p>
        </div>
        <div className="header-actions">
          <button
            className={
              appView === "caseSuites"
                ? "header-settings-button is-active"
                : "header-settings-button"
            }
            onClick={requestCaseSuitesSelection}
            type="button"
          >
            Case Suites
          </button>
          <button
            className={
              appView === "globalSettings"
                ? "header-settings-button is-active"
                : "header-settings-button"
            }
            onClick={requestGlobalSettingsSelection}
            type="button"
          >
            Global settings
          </button>
        </div>
      </header>

      <section className="workspace" aria-live="polite">
        {state.status === "loading" ? (
          <div className="empty-state">Loading experiments...</div>
        ) : null}

        {state.status === "error" ? (
          <div className="error-state">
            <h2>Could not load experiments</h2>
            <p>{state.message}</p>
          </div>
        ) : null}

        {state.status === "loaded" ? (
          <div className="tool-layout">
            <ExperimentsList
              experiments={state.experiments}
              onClone={requestCloneExperiment}
              onCreate={requestNewExperiment}
              onDelete={requestDeleteExperiment}
              onSelect={requestExperimentSelection}
              selectedExperimentId={
                appView === "experiment" ? selectedExperiment?.id ?? null : null
              }
            />

            <div className="detail-panel">
              {appView === "globalSettings" ? (
                globalSettingsState.status === "loading" ? (
                  <div className="empty-state">Loading global settings...</div>
                ) : globalSettingsState.status === "error" ? (
                  <div className="error-state">
                    <h2>Could not load global settings</h2>
                    <p>{globalSettingsState.message}</p>
                  </div>
                ) : (
                  <GlobalSettings
                    isBusy={globalSettingsBusy}
                    message={globalSettingsMessage}
                    onDirtyChange={setGlobalSettingsDirty}
                    onDraftChange={setGlobalSettingsDraft}
                    onReset={handleResetGlobalSettings}
                    onSave={handleSaveGlobalSettings}
                    settings={globalSettingsState.settings}
                  />
                )
              ) : null}

              {appView === "caseSuites" ? (
                <CaseSuiteManager
                  cases={caseSuiteCases}
                  caseSuiteCasesDirty={caseSuiteCasesDirty}
                  isBusy={caseSuiteBusy}
                  message={caseSuiteMessage}
                  onCasesChange={handleCaseSuiteCasesChange}
                  onCreateSuite={handleCreateCaseSuite}
                  onDeleteSuite={handleDeleteCaseSuite}
                  onResetCases={handleResetCaseSuiteCases}
                  onSaveCases={handleSaveCaseSuiteCases}
                  onSelectSuite={handleSelectCaseSuite}
                  onUpdateSuite={handleUpdateCaseSuite}
                  selectedSuiteId={selectedCaseSuiteId}
                  suites={caseSuites}
                />
              ) : null}

              {appView === "experiment" && state.experiments.length === 0 ? (
                <div className="empty-state">No experiments found.</div>
              ) : null}

              {appView === "experiment" &&
              state.experiments.length > 0 &&
              detailState.status === "idle" ? (
                <div className="empty-state">Select an experiment.</div>
              ) : null}

              {appView === "experiment" && detailState.status === "loading" ? (
                <div className="empty-state">Loading experiment details...</div>
              ) : null}

              {appView === "experiment" && detailState.status === "error" ? (
                <div className="error-state">
                  <h2>Could not load experiment details</h2>
                  <p>{detailState.message}</p>
                </div>
              ) : null}

              {appView === "experiment" && detailState.status === "loaded" ? (
                <>
                  <WorkflowToolbar
                    activeVersion={detailState.overview.version}
                    availableVersions={activeVersionOptions}
                    experiment={detailState.overview.experiment}
                    isVersionSwitching={workflowLocked}
                    jobStatus={jobStatus}
                    onActiveVersionChange={handleActiveVersionChange}
                    onCancelJob={handleCancelWorkflowJob}
                    onWorkflowModeChange={setWorkflowMode}
                    showDryRunControls={SHOW_DRY_RUN_CONTROLS}
                    workflowMessage={workflowMessage}
                    workflowMode={workflowMode}
                    unsavedChangesAction={workflowUnsavedChangesAction}
                    secondaryAction={
                      activeTab === "runs" ? (
                        <TooltipButton
                          className="secondary-action"
                          disabled={runActionDisabled}
                          disabledReason={runActionDisabledReason}
                          onClick={handlePreviewRunPrompts}
                          type="button"
                        >
                          Preview prompts
                        </TooltipButton>
                      ) : activeTab === "validation" ? (
                        <TooltipButton
                          className="secondary-action"
                          disabled={validateAction.disabled}
                          disabledReason={validateAction.disabledReason}
                          onClick={handlePreviewValidationPrompts}
                          type="button"
                        >
                          Preview prompts
                        </TooltipButton>
                      ) : activeTab === "review" ? (
                        <TooltipButton
                          className="secondary-action"
                          disabled={judgeAction.disabled}
                          disabledReason={judgeAction.disabledReason}
                          onClick={handlePreviewJudgePrompts}
                          type="button"
                        >
                          Preview prompts
                        </TooltipButton>
                      ) : activeTab === "proposal" ? (
                        <TooltipButton
                          className="secondary-action"
                          disabled={
                            workflowLocked ||
                            reviewState === null ||
                            decisionsDirty ||
                            humanNotesDirty
                          }
                          disabledReason={
                            workflowLocked
                              ? "Wait for the current workflow action to finish."
                              : reviewState === null
                                ? "Judge the active run before generating a proposal."
                                : "Save review changes before generating a proposal."
                          }
                          onClick={handlePreviewProposalPrompts}
                          type="button"
                        >
                          Preview prompts
                        </TooltipButton>
                      ) : null
                    }
                    primaryAction={
                      activeTab === "review" ? (
                        <TooltipButton
                          className="primary-action"
                          disabled={judgeAction.disabled}
                          disabledReason={judgeAction.disabledReason}
                          onClick={handleJudgeVersion}
                          type="button"
                        >
                          {judgeAction.label}
                        </TooltipButton>
                      ) : activeTab === "proposal" ? (
                        <TooltipButton
                          className="primary-action"
                          disabled={
                            workflowLocked ||
                            reviewState === null ||
                            decisionsDirty ||
                            humanNotesDirty
                          }
                          disabledReason={
                            workflowLocked
                              ? "Wait for the current workflow action to finish."
                              : reviewState === null
                                ? "Judge the active run before generating a proposal."
                                : "Save review changes before generating a proposal."
                          }
                          onClick={handleGenerateProposal}
                          type="button"
                        >
                          {getProposalActionLabel({
                            hasProposal: proposalResponse !== null,
                            isBusy: workflowLocked
                          })}
                        </TooltipButton>
                      ) : activeTab === "compare" ? (
                        <TooltipButton
                          className="primary-action"
                          disabled={compareAction.disabled}
                          disabledReason={compareAction.disabledReason}
                          onClick={handleCompareVersions}
                          type="button"
                        >
                          {compareAction.label}
                        </TooltipButton>
                      ) : activeTab === "validation" ? (
                        <TooltipButton
                          className="primary-action"
                          disabled={validateAction.disabled}
                          disabledReason={validateAction.disabledReason}
                          onClick={handleValidateVersion}
                          type="button"
                        >
                          {validateAction.label}
                        </TooltipButton>
                      ) : activeTab === "runs" ? (
                        <TooltipButton
                          className="primary-action"
                          disabled={runActionDisabled}
                          disabledReason={runActionDisabledReason}
                          onClick={handleRunVersion}
                          type="button"
                        >
                          {getRunActionLabel({
                            hasRuns,
                            isRunning: jobStatus?.status === "running"
                          })}
                        </TooltipButton>
                      ) : null
                    }
                  />

                  <WorkbenchTabs
                    activeTab={activeTab}
                    onTabChange={requestTabChange}
                  />

                  <div className="workbench-body">
                    {activeTab === "prompt" ? (
                      <PromptView
                        overview={detailState.overview}
                        isRunning={workflowLocked}
                        isSourceEditing={sourceEditing}
                        onRunVersion={handleRunVersion}
                        onSourceDraftChange={handleSourceDraftChange}
                        onSourceEdit={handleSourceEdit}
                        onSourceOverwriteCurrent={() => requestSourceOverwrite()}
                        onSourceReset={handleSourceReset}
                        onSourceSaveAsNext={() =>
                          void handleSaveVersionSource("create_next")
                        }
                        onSourceViewModeChange={setSourceViewMode}
                        showRunAction={false}
                        sourceBusy={workflowLocked}
                        sourceDirty={sourceDirty}
                        sourceDraft={sourceDraft}
                        sourceViewMode={sourceViewMode}
                      />
                    ) : null}

                    {activeTab === "settings" ? (
                      <ExperimentSettings
                        caseSuites={caseSuites}
                        experiment={detailState.overview.experiment}
                        isBusy={settingsBusy}
                        message={settingsMessage}
                        onDirtyChange={setSettingsDirty}
                        onDraftChange={setSettingsDraft}
                        onReset={handleResetExperimentSettings}
                        onSave={handleSaveExperimentSettings}
                      />
                    ) : null}

                    {activeTab === "validators" ? (
                      <ValidatorsView
                        isBusy={workflowLocked}
                        message={workflowMessage}
                        onDraftChange={handleValidatorsDraftChange}
                        onOverwriteCurrent={() =>
                          requestValidatorsOverwrite()
                        }
                        onReset={handleValidatorsReset}
                        onSaveAsNext={() =>
                          void handleSaveVersionValidators("create_next")
                        }
                        validators={detailState.overview.validators ?? []}
                      />
                    ) : null}

                    {activeTab === "cases" ? (
                      <CaseBrowser
                        cases={casesDraft ?? detailState.overview.cases}
                        isBusy={workflowLocked}
                        onCasesChange={handleCasesDraftChange}
                        suiteTitle={
                          detailState.overview.case_suite?.title ?? null
                        }
                      />
                    ) : null}

                    {activeTab === "runs" ? (
                      <RunsView
                        cases={detailState.overview.cases}
                        runBatchId={detailState.runs.run_batch_id}
                        runs={detailState.runs.runs}
                      />
                    ) : null}

                    {activeTab === "validation" ? (
                      <ValidationView
                        hasRuns={hasRuns}
                        isBusy={workflowLocked}
                        onStateChange={handleValidationStateChange}
                        runs={detailState.runs.runs}
                        validationState={validationState}
                      />
                    ) : null}

                    {activeTab === "review" ? (
                      <ReviewView
                        isBusy={workflowLocked}
                        judgeDisabled={judgeAction.disabled}
                        judgeDisabledReason={judgeAction.disabledReason}
                        onDecisionChange={handleDecisionChange}
                        onHumanNotesChange={handleHumanNotesChange}
                        onJudge={handleJudgeVersion}
                        reviewState={reviewState}
                      />
                    ) : null}

                    {activeTab === "proposal" ? (
                      <ProposalView
                        createdVersion={createdVersion}
                        currentModel={detailState.overview.model_py ?? null}
                        currentModelFile={detailState.overview.model_file ?? null}
                        currentPrompt={detailState.overview.prompt}
                        hasUnsavedReviewChanges={hasUnsavedReviewChanges}
                        isBusy={workflowLocked}
                        onCreateVersion={handleCreateVersion}
                        onGenerateProposal={handleGenerateProposal}
                        proposalResponse={proposalResponse}
                        reviewState={reviewState}
                      />
                    ) : null}

                    {activeTab === "compare" ? (
                      <ComparisonView
                        baselineVersion={baselineVersion}
                        candidateVersion={candidateVersion}
                        comparison={comparison}
                        hasUnsavedValidationChanges={
                          hasUnsavedCompareValidationChanges
                        }
                        hasValidation={hasComparedValidation}
                        isBusy={workflowLocked}
                        knownVersions={knownVersions}
                        onBaselineVersionChange={handleBaselineVersionChange}
                        onCandidateVersionChange={handleCandidateVersionChange}
                        onCompare={handleCompareVersions}
                      />
                    ) : null}
                  </div>
                </>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      {promptPreview !== null ? (
        <PromptPreviewModal
          isAccepting={workflowLocked}
          onAccept={handleAcceptPromptPreview}
          onReject={handleRejectPromptPreview}
          preview={promptPreview}
        />
      ) : null}

      {experimentDialog?.kind === "new" ? (
        <NewExperimentModal
          error={experimentActionError}
          isBusy={experimentActionBusy}
          onCancel={closeExperimentDialog}
          onSubmit={handleCreateExperiment}
        />
      ) : null}

      {experimentDialog?.kind === "clone" ? (
        <CloneExperimentModal
          error={experimentActionError}
          isBusy={experimentActionBusy}
          onCancel={closeExperimentDialog}
          onSubmit={handleCloneExperiment}
          sourceTitle={experimentDialog.experiment.title}
        />
      ) : null}

      {experimentDialog?.kind === "delete" ? (
        <DeleteExperimentModal
          error={experimentActionError}
          experimentTitle={experimentDialog.experiment.title}
          isBusy={experimentActionBusy}
          onCancel={closeExperimentDialog}
          onConfirm={handleDeleteExperiment}
        />
      ) : null}

      {pendingNavigation !== null &&
      pendingSourceOverwrite === null &&
      pendingValidatorsOverwrite === null ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="settings-navigation-title"
            aria-modal="true"
            className="settings-navigation-modal"
            role="dialog"
          >
            <div>
              <h2 id="settings-navigation-title">{pendingNavigationDialog.title}</h2>
              <p>{pendingNavigationDialog.body}</p>
            </div>
            {navigationError !== null ? (
              <div className="settings-error">{navigationError}</div>
            ) : null}
            <div className="modal-actions">
              <button
                className="secondary-action"
                disabled={navigationSaving}
                onClick={handleStayOnSettings}
                type="button"
              >
                Stay
              </button>
              <button
                className="secondary-action danger-action"
                disabled={navigationSaving}
                onClick={() => void handleDiscardSettingsAndContinue()}
                type="button"
              >
                Discard changes
              </button>
              {pendingNavigationKind === "source" ? (
                <button
                  className="secondary-action danger-action"
                  disabled={pendingNavigationSaveDisabled}
                  onClick={() => requestSourceOverwrite(pendingNavigation)}
                  type="button"
                >
                  Overwrite and continue
                </button>
              ) : null}
              {pendingNavigationKind === "validators" ? (
                <button
                  className="secondary-action danger-action"
                  disabled={pendingNavigationSaveDisabled}
                  onClick={() => requestValidatorsOverwrite(pendingNavigation)}
                  type="button"
                >
                  Overwrite and continue
                </button>
              ) : null}
              <button
                className="primary-action"
                disabled={pendingNavigationSaveDisabled}
                onClick={() => void handleSaveSettingsAndContinue()}
                type="button"
              >
                {navigationSaving
                  ? "Saving..."
                  : pendingNavigationKind === "source" ||
                      pendingNavigationKind === "validators"
                    ? "Save as next and continue"
                    : "Save and continue"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {pendingSourceOverwrite !== null ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="source-overwrite-title"
            aria-modal="true"
            className="settings-navigation-modal"
            role="dialog"
          >
            <div>
              <h2 id="source-overwrite-title">Overwrite current version?</h2>
              <p>
                This will replace the prompt and model for the active version and
                delete its generated runs, validations, reviews, proposals, and
                comparisons.
              </p>
            </div>
            <div className="modal-actions">
              <button
                className="secondary-action"
                disabled={workflowBusy}
                onClick={handleCancelSourceOverwrite}
                type="button"
              >
                Cancel
              </button>
              <button
                className="secondary-action danger-action"
                disabled={workflowBusy}
                onClick={() => void handleConfirmSourceOverwrite()}
                type="button"
              >
                {workflowBusy ? "Overwriting..." : "Overwrite current version"}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {pendingValidatorsOverwrite !== null ? (
        <div className="modal-backdrop" role="presentation">
          <section
            aria-labelledby="validators-overwrite-title"
            aria-modal="true"
            className="settings-navigation-modal"
            role="dialog"
          >
            <div>
              <h2 id="validators-overwrite-title">
                Overwrite current validators?
              </h2>
              <p>
                This replaces validators for the current version and clears
                validation, review, proposal, and comparison artifacts. Existing
                runs are kept.
              </p>
            </div>
            <div className="modal-actions">
              <button
                className="secondary-action"
                disabled={workflowBusy}
                onClick={handleCancelValidatorsOverwrite}
                type="button"
              >
                Cancel
              </button>
              <button
                className="secondary-action danger-action"
                disabled={workflowBusy}
                onClick={() => void handleConfirmValidatorsOverwrite()}
                type="button"
              >
                {workflowBusy ? "Overwriting..." : "Overwrite current version"}
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

export default App;
