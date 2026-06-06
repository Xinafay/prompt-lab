from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI

from prompt_lab import llm_client
from prompt_lab.config import PromptLabConfig
from prompt_lab.jobs import JobManager
from prompt_lab.runner import iter_case_major, run_text_case
from prompt_lab.storage import PromptLabStore


def create_app(config: PromptLabConfig | None = None) -> FastAPI:
    resolved_config = config or PromptLabConfig.from_env()
    store = PromptLabStore(
        experiments_root=resolved_config.experiments_root,
        examples_root=resolved_config.examples_root,
    )
    job_manager = JobManager()
    app = FastAPI(title="Prompt Lab")

    @app.get("/api/experiments")
    def list_experiments() -> list[dict[str, object]]:
        return [item.model_dump(mode="json") for item in store.list_experiments()]

    @app.post("/api/experiments/{experiment_id}/versions/{version}/runs")
    def run_experiment_version(experiment_id: str, version: str) -> dict[str, object]:
        experiment = store.load_experiment(experiment_id)
        cases = store.load_cases(experiment_id, version)
        repeat_count = experiment.run_defaults.repeat_count
        job = job_manager.start_job(
            kind="run_version",
            experiment_id=experiment_id,
            version=version,
            total_units=len(cases) * repeat_count,
        )
        template_text = store.read_text(experiment_id, version, experiment.template.path)

        completed_units = 0
        for case, repeat_index in iter_case_major(cases, repeat_count=repeat_count):
            if experiment.output.type != "text":
                raise NotImplementedError(
                    "Pydantic run endpoint is implemented in a later task."
                )
            run = run_text_case(
                version=version,
                run_batch_id=job.job_id,
                case=case,
                repeat_index=repeat_index,
                generator_model=experiment.models.generator_model,
                template_text=template_text,
                generate_text=llm_client.generate_text,
            )
            store.write_run_artifact(
                experiment_id,
                version,
                f"runs/{job.job_id}/{case.id}/repeat-{repeat_index:03d}.json",
                run.model_dump(mode="json"),
            )
            completed_units += 1
            job = job_manager.update(
                job.job_id,
                completed_units=completed_units,
                message=f"Completed {case.id} repeat {repeat_index}",
            )

        job = job_manager.complete(job.job_id, message="Run completed")
        return asdict(job)

    return app
