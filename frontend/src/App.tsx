import { useEffect, useMemo, useRef, useState } from "react";

import {
  apiGet,
  getJob,
  getJobEvents,
  getVersionOverview,
  getVersionRuns,
  runVersion
} from "./api";
import { ExperimentOverview } from "./components/ExperimentOverview";
import { ExperimentsList } from "./components/ExperimentsList";
import { RunsView } from "./components/RunsView";
import type { Experiment, JobStatus, RunsResponse, VersionOverview } from "./types";

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
  const selectedKeyRef = useRef<string | null>(null);
  const runRequestIdRef = useRef(0);

  function selectExperiment(experiment: Experiment | null) {
    selectedKeyRef.current =
      experiment === null ? null : `${experiment.id}:${experiment.active_version}`;
    runRequestIdRef.current += 1;
    setSelectedExperiment(experiment);
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

      while (job.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 400));
        const [latestJob, events] = await Promise.all([
          getJob(job.job_id),
          getJobEvents(job.job_id)
        ]);
        if (!isCurrentRequest()) {
          return;
        }
        const latestEvent = events.at(-1);
        job = latestEvent
          ? { ...latestJob, message: latestEvent.message }
          : latestJob;
        setJobStatus(job);
      }

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
