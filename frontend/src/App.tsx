import { useEffect, useMemo, useState } from "react";

import { apiGet } from "./api";
import type { Experiment } from "./types";

type LoadState =
  | { status: "loading" }
  | { status: "loaded"; experiments: Experiment[] }
  | { status: "error"; message: string };

function App() {
  const [state, setState] = useState<LoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    async function loadExperiments() {
      try {
        const experiments = await apiGet<Experiment[]>("/api/experiments");
        if (!cancelled) {
          setState({ status: "loaded", experiments });
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

  const subtitle = useMemo(() => {
    if (state.status !== "loaded") {
      return "Loading local experiment manifests";
    }
    const count = state.experiments.length;
    return `${count} experiment${count === 1 ? "" : "s"} available`;
  }, [state]);

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
          <div className="experiment-list">
            {state.experiments.map((experiment) => (
              <article className="experiment-row" key={experiment.id}>
                <div className="experiment-main">
                  <h2>{experiment.title}</h2>
                  <p>{experiment.description || "No description provided."}</p>
                </div>
                <dl className="experiment-meta">
                  <div>
                    <dt>ID</dt>
                    <dd>{experiment.id}</dd>
                  </div>
                  <div>
                    <dt>Active version</dt>
                    <dd>{experiment.active_version}</dd>
                  </div>
                </dl>
              </article>
            ))}
          </div>
        ) : null}
      </section>
    </main>
  );
}

export default App;
