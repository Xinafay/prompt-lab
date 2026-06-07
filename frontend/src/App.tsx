import { useEffect, useMemo, useRef, useState } from "react";

import {
  apiGet,
  compareVersions,
  createProposalVersion,
  generateProposal,
  getReviewState,
  getVersionOverview,
  getVersionRuns,
  judgeVersion,
  jobEventsStreamUrl,
  runVersion,
  updateHumanNotes,
  updateReviewDecisions
} from "./api";
import { ComparisonView } from "./components/ComparisonView";
import { ExperimentOverview } from "./components/ExperimentOverview";
import { ExperimentsList } from "./components/ExperimentsList";
import { ProposalView } from "./components/ProposalView";
import { ReviewView } from "./components/ReviewView";
import { RunsView } from "./components/RunsView";
import type {
  ComparisonArtifact,
  CreatedVersionResponse,
  Experiment,
  FindingDecisionValue,
  JobEvent,
  JobStatus,
  ProposalResponse,
  ReviewState,
  RunsResponse,
  VersionOverview
} from "./types";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; experiments: Experiment[] }
  | { status: "error"; message: string };

type DetailState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "loaded"; overview: VersionOverview; runs: RunsResponse }
  | { status: "error"; message: string };

function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [selectedExperiment, setSelectedExperiment] =
    useState<Experiment | null>(null);
  const [detailState, setDetailState] = useState<DetailState>({ status: "idle" });
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [reviewState, setReviewState] = useState<ReviewState | null>(null);
  const [proposalResponse, setProposalResponse] =
    useState<ProposalResponse | null>(null);
  const [createdVersion, setCreatedVersion] =
    useState<CreatedVersionResponse | null>(null);
  const [comparison, setComparison] = useState<ComparisonArtifact | null>(null);
  const [baselineVersion, setBaselineVersion] = useState("v001");
  const [candidateVersion, setCandidateVersion] = useState("v001");
  const [workflowBusy, setWorkflowBusy] = useState(false);
  const [workflowMessage, setWorkflowMessage] = useState<string | null>(null);
  const [decisionsDirty, setDecisionsDirty] = useState(false);
  const [humanNotesDirty, setHumanNotesDirty] = useState(false);
  const selectedKeyRef = useRef<string | null>(null);
  const runRequestIdRef = useRef(0);
  const workflowRequestIdRef = useRef(0);
  const baselineVersionRef = useRef("v001");
  const candidateVersionRef = useRef("v001");

  function selectExperiment(experiment: Experiment | null) {
    selectedKeyRef.current =
      experiment === null ? null : `${experiment.id}:${experiment.active_version}`;
    runRequestIdRef.current += 1;
    workflowRequestIdRef.current += 1;
    setSelectedExperiment(experiment);
    setReviewState(null);
    setProposalResponse(null);
    setCreatedVersion(null);
    setComparison(null);
    setWorkflowMessage(null);
    setWorkflowBusy(false);
    setDecisionsDirty(false);
    setHumanNotesDirty(false);
    if (experiment !== null) {
      setCandidateVersion(experiment.active_version);
      setBaselineVersion("v001");
      candidateVersionRef.current = experiment.active_version;
      baselineVersionRef.current = "v001";
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
    return requestId;
  }

  function isWorkflowCurrent(requestId: number, selectionKey: string): boolean {
    return (
      workflowRequestIdRef.current === requestId && isSelectionCurrent(selectionKey)
    );
  }

  useEffect(() => {
    let cancelled = false;

    async function loadExperiments() {
      try {
        const experiments = await apiGet<Experiment[]>("/api/experiments");
        if (!cancelled) {
          setState({ status: "loaded", experiments });
          if (selectedKeyRef.current === null) {
            selectExperiment(experiments[0] ?? null);
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

  useEffect(() => {
    if (selectedExperiment === null) {
      setDetailState({ status: "idle" });
      return;
    }

    let cancelled = false;
    setDetailState({ status: "loading" });
    setJobStatus(null);

    async function loadDetails(experiment: Experiment) {
      try {
        const [overview, runs] = await Promise.all([
          getVersionOverview(experiment.id, experiment.active_version),
          getVersionRuns(experiment.id, experiment.active_version)
        ]);
        if (!cancelled) {
          setDetailState({ status: "loaded", overview, runs });
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

  const subtitle = useMemo(() => {
    if (state.status !== "loaded") {
      return "Loading local experiment manifests";
    }
    const count = state.experiments.length;
    return `${count} experiment${count === 1 ? "" : "s"} available`;
  }, [state]);

  async function handleRunVersion() {
    if (selectedExperiment === null || detailState.status !== "loaded") {
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
      let job = await runVersion(experimentId, version);
      if (!isCurrentRequest()) {
        return;
      }
      setJobStatus(job);

      job = await followJobEvents(job.job_id, job, isCurrentRequest);

      const runs = await getVersionRuns(experimentId, version);
      if (!isCurrentRequest()) {
        return;
      }
      setDetailState({ status: "loaded", overview, runs });
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
        reject(new Error("Lost job event stream."));
      });
    });
  }

  async function handleJudgeVersion() {
    if (selectedExperiment === null) return;
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestId = beginWorkflow(selectionKey, "Judging latest runs...");
    try {
      const response = await judgeVersion(experimentId, version);
      const review = await getReviewState(experimentId, version, response.review_id);
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setReviewState(review);
      setProposalResponse(null);
      setCreatedVersion(null);
      setDecisionsDirty(false);
      setHumanNotesDirty(false);
      setWorkflowMessage(`Loaded ${response.review_id}`);
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
    setProposalResponse(null);
    setCreatedVersion(null);
  }

  async function handleSaveDecisions() {
    if (selectedExperiment === null || reviewState === null) return;
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestId = beginWorkflow(selectionKey);
    try {
      const decisions = await updateReviewDecisions(
        experimentId,
        version,
        reviewState.review_id,
        reviewState.decisions
      );
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setReviewState((current) =>
        current === null || current.review_id !== reviewState.review_id
          ? current
          : { ...current, decisions }
      );
      setDecisionsDirty(false);
      setWorkflowMessage("Decisions saved.");
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

  function handleHumanNotesChange(notes: string) {
    setReviewState((current) =>
      current === null ? current : { ...current, human_notes: notes }
    );
    setHumanNotesDirty(true);
    setProposalResponse(null);
    setCreatedVersion(null);
  }

  async function handleSaveHumanNotes() {
    if (selectedExperiment === null || reviewState === null) return;
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestId = beginWorkflow(selectionKey);
    try {
      const response = await updateHumanNotes(
        experimentId,
        version,
        reviewState.review_id,
        reviewState.human_notes
      );
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setReviewState((current) =>
        current === null || current.review_id !== reviewState.review_id
          ? current
          : { ...current, human_notes: response.human_notes }
      );
      setHumanNotesDirty(false);
      setWorkflowMessage("Human notes saved.");
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

  async function handleGenerateProposal() {
    if (selectedExperiment === null || reviewState === null) return;
    if (decisionsDirty || humanNotesDirty) {
      setWorkflowMessage("Save decisions and human notes before generating a proposal.");
      return;
    }
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestId = beginWorkflow(selectionKey, "Generating proposal...");
    try {
      const response = await generateProposal(
        experimentId,
        version,
        reviewState.review_id
      );
      if (!isWorkflowCurrent(requestId, selectionKey)) return;
      setProposalResponse(response);
      setCreatedVersion(null);
      setWorkflowMessage("Proposal generated.");
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
      candidateVersionRef.current = response.version;
      setCandidateVersion(response.version);
      setComparison(null);
      setWorkflowMessage(`Created ${response.version}.`);
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

  async function handleCompareVersions() {
    if (selectedExperiment === null) return;
    const experimentId = selectedExperiment.id;
    const version = selectedExperiment.active_version;
    const selectionKey = `${experimentId}:${version}`;
    const requestedBaseline = baselineVersion;
    const requestedCandidate = candidateVersion;
    const requestId = beginWorkflow(selectionKey, "Comparing versions...");
    try {
      const response = await compareVersions(
        experimentId,
        requestedBaseline,
        requestedCandidate
      );
      if (
        !isWorkflowCurrent(requestId, selectionKey) ||
        requestedBaseline !== baselineVersionRef.current ||
        requestedCandidate !== candidateVersionRef.current
      ) {
        return;
      }
      setComparison(response.comparison);
      setWorkflowMessage(`Loaded ${response.comparison_id}.`);
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

  const knownVersions = useMemo(() => {
    const versions = new Set<string>();
    if (selectedExperiment !== null) versions.add(selectedExperiment.active_version);
    versions.add("v001");
    if (createdVersion !== null) versions.add(createdVersion.version);
    versions.add(baselineVersion);
    versions.add(candidateVersion);
    return [...versions].sort();
  }, [baselineVersion, candidateVersion, createdVersion, selectedExperiment]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>Prompt Lab</h1>
          <p>{subtitle}</p>
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

        {state.status === "loaded" && state.experiments.length === 0 ? (
          <div className="empty-state">No experiments found.</div>
        ) : null}

        {state.status === "loaded" && state.experiments.length > 0 ? (
          <div className="tool-layout">
            <ExperimentsList
              experiments={state.experiments}
              onSelect={selectExperiment}
              selectedExperimentId={selectedExperiment?.id ?? null}
            />

            <div className="detail-panel">
              {detailState.status === "idle" ? (
                <div className="empty-state">Select an experiment.</div>
              ) : null}

              {detailState.status === "loading" ? (
                <div className="empty-state">Loading experiment details...</div>
              ) : null}

              {detailState.status === "error" ? (
                <div className="error-state">
                  <h2>Could not load experiment details</h2>
                  <p>{detailState.message}</p>
                </div>
              ) : null}

              {detailState.status === "loaded" ? (
                <>
                  {jobStatus !== null ? (
                    <div className={`job-banner job-${jobStatus.status}`}>
                      <strong>{jobStatus.status}</strong>
                      <span>
                        {jobStatus.message} · {jobStatus.completed_units}/
                        {jobStatus.total_units}
                      </span>
                    </div>
                  ) : null}
                  <ExperimentOverview
                    isRunning={jobStatus?.status === "running"}
                    onRunVersion={handleRunVersion}
                    overview={detailState.overview}
                  />
                  <RunsView
                    cases={detailState.overview.cases}
                    runBatchId={detailState.runs.run_batch_id}
                    runs={detailState.runs.runs}
                  />
                  {workflowMessage !== null ? (
                    <div className="workflow-message">{workflowMessage}</div>
                  ) : null}
                  <ReviewView
                    isBusy={workflowBusy}
                    onDecisionChange={handleDecisionChange}
                    onHumanNotesChange={handleHumanNotesChange}
                    onJudge={handleJudgeVersion}
                    onSaveDecisions={handleSaveDecisions}
                    onSaveHumanNotes={handleSaveHumanNotes}
                    reviewState={reviewState}
                  />
                  <ProposalView
                    createdVersion={createdVersion}
                    hasUnsavedReviewChanges={decisionsDirty || humanNotesDirty}
                    isBusy={workflowBusy}
                    onCreateVersion={handleCreateVersion}
                    onGenerateProposal={handleGenerateProposal}
                    proposalResponse={proposalResponse}
                    reviewState={reviewState}
                  />
                  <ComparisonView
                    baselineVersion={baselineVersion}
                    candidateVersion={candidateVersion}
                    comparison={comparison}
                    isBusy={workflowBusy}
                    knownVersions={knownVersions}
                    onBaselineVersionChange={handleBaselineVersionChange}
                    onCandidateVersionChange={handleCandidateVersionChange}
                    onCompare={handleCompareVersions}
                  />
                </>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}

export default App;
