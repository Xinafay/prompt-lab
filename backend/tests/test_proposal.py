from __future__ import annotations

import json
from pathlib import Path
from threading import Event, Thread
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from prompt_lab import llm_client
from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig
from prompt_lab.proposal import (
    PydanticProposalDraft,
    TextProposalDraft,
    build_proposal_prompt,
)
from prompt_lab.settings import PromptLabSettings, save_settings
from test_judge import valid_case_payload, valid_judgment_payload, write_json


class FakeGeneratedStructured:
    def __init__(self, output: Any) -> None:
        self.output = output
        self.usage: dict[str, Any] = {}


def write_review_fixture(root: Path, *, output_type: str = "pydantic") -> Path:
    save_settings(
        root / "config" / "settings.json",
        PromptLabSettings(
            default_generator_model="local/a",
            default_validator_model="openai/judge",
            default_judge_model="openai/judge",
            default_repeat_count=1,
        ),
    )
    example = root / "examples" / "demo"
    version_dir = example / "versions" / "v001"
    review_dir = version_dir / "reviews" / "review-001"
    output: dict[str, Any]
    if output_type == "pydantic":
        output = {
            "type": "pydantic",
            "model_file": "model.py",
            "model_entrypoint": "model.DemoOutput",
        }
    else:
        output = {"type": "text"}
    write_json(
        example / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "Demo experiment",
            "active_version": "v001",
            "output": output,
            "template": {"engine": "jinjax", "path": "prompt.md"},
            "models": {"generator_model": "local/a", "validator_model": "openai/judge", "judge_model": "openai/judge"},
            "run_defaults": {
                "repeat_count": 1,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (example / "rubric.md").write_text("Keep answers complete.", encoding="utf-8")
    cases_dir = example / "cases"
    cases_dir.mkdir(parents=True)
    version_dir.mkdir(parents=True)
    prompt_text = (
        "Say {{ value }}\n\n<<MODEL>>"
        if output_type == "pydantic"
        else "Say {{ value }}"
    )
    (version_dir / "prompt.md").write_text(prompt_text, encoding="utf-8")
    if output_type == "pydantic":
        (version_dir / "model.py").write_text(
            "from pydantic import BaseModel\n\n"
            "class DemoOutput(BaseModel):\n"
            "    answer: str\n",
            encoding="utf-8",
        )
    write_json(
        cases_dir / "case-a.json",
        valid_case_payload(),
    )
    write_json(
        review_dir / "judgment.json",
        valid_judgment_payload(
            judge_model="openai/judge",
            findings=[
                {
                    "finding_id": "f-accepted",
                    "severity": "recommended",
                    "area": "prompt",
                    "category": "recurring_problem",
                    "description": "The output misses the required summary.",
                    "evidence": ["case-a repeat 1"],
                    "suggested_change": "Require a concise summary.",
                },
                {
                    "finding_id": "f-rejected",
                    "severity": "optional",
                    "area": "prompt",
                    "category": "style",
                    "description": "The tone could be friendlier.",
                    "evidence": ["case-a repeat 1"],
                    "suggested_change": "Make the tone warmer.",
                },
                {
                    "finding_id": "f-deferred",
                    "severity": "do_not_change_yet",
                    "area": "prompt",
                    "category": "scope",
                    "description": "Add unrelated metadata.",
                    "evidence": ["case-a repeat 1"],
                    "suggested_change": "Add metadata.",
                },
            ],
        ),
    )
    write_json(
        review_dir / "decisions.json",
        {
            "schema_version": "prompt_lab.decisions/v1",
            "finding_decisions": {
                "f-accepted": {"decision": "accepted", "reason": "Required"},
                "f-rejected": {"decision": "rejected", "reason": "Out of scope"},
                "f-deferred": {"decision": "deferred", "reason": "Later"},
            },
        },
    )
    write_json(
        review_dir / "validation_context.json",
        {
            "validation_batch_id": "validation-001",
            "run_batch_id": "batch-001",
            "validation_evidence": [
                {
                    "validator_id": "quality",
                    "validator_title": "Quality checks",
                    "check_id": "complete",
                    "check_title": "Complete answer",
                    "case_id": "case-a",
                    "repeat_index": 1,
                    "grade": 1,
                    "comment": "The output misses the required summary.",
                }
            ],
            "validator_snapshots": [],
        },
    )
    (review_dir / "human_notes.md").write_text(
        "Keep the answer terse; do not add friendliness work.", encoding="utf-8"
    )
    return review_dir


def runtime_review_dir(root: Path) -> Path:
    return (
        root
        / "experiments"
        / "demo"
        / "versions"
        / "v001"
        / "reviews"
        / "review-001"
    )


def write_valid_proposal_source(review_dir: Path) -> None:
    write_json(
        review_dir / "proposal" / "source.json",
        {
            "experiment_id": "demo",
            "source_version": "v001",
            "review_id": "review-001",
            "judgment_id": "j001",
            "decision_summary": {
                "accepted": ["f-accepted"],
                "rejected": ["f-rejected"],
                "deferred": ["f-deferred"],
            },
            "human_notes_present": True,
            "generated_by_model": "openai/judge",
        },
    )


def test_text_proposal_draft_rejects_model_marker() -> None:
    try:
        TextProposalDraft(
            prompt_md="Improved prompt\n\n<<MODEL>>",
            rationale_md="Text prompts should not include structured schema markers.",
        )
    except ValueError as error:
        assert "text proposal prompt_md cannot contain <<MODEL>>" in str(error)
    else:
        raise AssertionError("Expected text proposal to reject <<MODEL>>")


def test_pydantic_proposal_draft_requires_prompt_marker_and_model_py() -> None:
    for prompt_md in ["Improved prompt", "A\n\n<<MODEL>>\n\nB\n\n<<MODEL>>"]:
        try:
            PydanticProposalDraft(
                prompt_md=prompt_md,
                model_py="from pydantic import BaseModel\n",
                rationale_md="Pydantic prompts need one schema marker.",
            )
        except ValueError as error:
            assert "pydantic proposal prompt_md must contain exactly one <<MODEL>>" in str(
                error
            )
        else:
            raise AssertionError("Expected pydantic proposal to reject marker count")

    try:
        PydanticProposalDraft.model_validate(
            {
                "prompt_md": "Improved prompt\n\n<<MODEL>>",
                "model_py": None,
                "rationale_md": "Pydantic proposals must include model.py.",
            }
        )
    except ValueError as error:
        assert "pydantic proposal model_py must contain complete model.py" in str(error)
    else:
        raise AssertionError("Expected pydantic proposal to require model_py")

    proposal = PydanticProposalDraft(
        prompt_md="Improved prompt\n\n<<MODEL>>",
        model_py="from pydantic import BaseModel\n",
        rationale_md="Pydantic prompt keeps structured output.",
    )
    assert proposal.prompt_md.endswith("<<MODEL>>")
    assert proposal.model_py.startswith("from pydantic")


def test_build_proposal_prompt_sorts_decisions_and_includes_rules() -> None:
    prompt = build_proposal_prompt(
        experiment_id="demo",
        version="v001",
        current_model="local/generator",
        output_type="pydantic",
        prompt_template="Say {{ value }} and include summary.\n\n<<MODEL>>",
        model_source="class DemoOutput: ...\n    answer: str\n    marker = '<<MODEL>>'",
        validation_context={
            "validation_batch_id": "validation-001",
            "run_batch_id": "batch-001",
            "validation_evidence": [
                {
                    "validator_id": "quality",
                    "check_id": "complete",
                    "case_id": "case-a",
                    "repeat_index": 1,
                    "grade": 1,
                    "comment": "Missing summary near <<MODEL>>.",
                }
            ],
        },
        judgment=valid_judgment_payload(
            findings=[
                {
                    "finding_id": "f-accepted",
                    "severity": "recommended",
                    "area": "prompt",
                    "category": "recurring_problem",
                    "description": "Missing summary.",
                    "evidence": ["case-a repeat 1"],
                    "suggested_change": "Require summary.",
                },
                {
                    "finding_id": "f-rejected",
                    "severity": "optional",
                    "area": "prompt",
                    "category": "style",
                    "description": "Make warmer.",
                    "evidence": ["case-a repeat 1"],
                    "suggested_change": "Use warmer tone.",
                },
                {
                    "finding_id": "f-deferred",
                    "severity": "optional",
                    "area": "prompt",
                    "category": "format",
                    "description": "Add metadata.",
                    "evidence": ["case-a repeat 1"],
                    "suggested_change": "Add metadata.",
                },
            ],
        ),
        decisions={
            "f-accepted": {"decision": "accepted", "reason": "Required"},
            "f-rejected": {"decision": "rejected", "reason": "Out of scope"},
            "f-deferred": {"decision": "deferred", "reason": "Later"},
        },
        human_notes=(
            "Keep the answer terse; human notes override all judge findings. "
            "Do not copy <<MODEL>> from notes."
        ),
    )

    assert "human notes override all judge findings" in prompt
    assert prompt.count("<<MODEL>>") == 1
    assert "accepted findings are requested changes" in prompt
    assert "rejected findings are constraints" in prompt
    assert "deferred findings are ignored" in prompt
    assert "preserve task scope" in prompt
    assert "change `model.py` contents only when contract changes are clearly needed" in prompt
    assert "always return complete `model_py`" in prompt
    assert "Say {{ value }} and include summary." in prompt
    assert "[OUTPUT_MODEL_SCHEMA: see CURRENT_MODEL_PY]" in prompt
    assert prompt.count("[MODEL_MARKER_LITERAL]") == 2
    assert "Current model: local/generator" in prompt
    assert "Keep the answer terse" in prompt
    assert "VALIDATION_METADATA_JSON" in prompt
    assert "validation-001" in prompt
    assert '"grade": 1' not in prompt
    assert "Missing summary near" not in prompt
    assert '"verdict"' not in prompt
    assert "<<<PROPOSAL_SCHEMA_JSON" not in prompt
    assert prompt.index("<<<VALIDATION_METADATA_JSON") < prompt.index("<<MODEL>>")
    assert prompt.index("<<<REJECTED_FINDINGS_AS_CONSTRAINTS_JSON") < prompt.index("<<MODEL>>")
    assert "RUBRIC_SNAPSHOT_MD" not in prompt
    assert "f-accepted" in prompt
    assert "Missing summary." in prompt
    assert "f-rejected" in prompt
    assert "REJECTED_FINDINGS_AS_CONSTRAINTS_JSON" in prompt
    assert "Out of scope" in prompt
    assert "f-deferred" not in prompt
    assert "class DemoOutput" in prompt
    assert "answer: str" in prompt
    assert "Use the output-specific response schema" in prompt


def test_proposal_prompt_template_file_is_used() -> None:
    template_path = (
        Path(__file__).parents[1]
        / "prompt_lab"
        / "system_prompts"
        / "proposal.md.jinja"
    )
    assert template_path.is_file()
    assert (
        "You are generating a Prompt Lab proposal for one reviewed experiment version."
        in template_path.read_text(encoding="utf-8")
    )


def test_api_generates_proposal_artifacts_with_traceable_source() -> None:
    calls: list[dict[str, Any]] = []

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        calls.append(
            {
                "model": model,
                "prompt": prompt,
                "response_model": response_model,
                "validation_context": validation_context,
            }
        )
        return FakeGeneratedStructured(
            response_model(
                prompt_md="Say {{ value }} with summary\n\n<<MODEL>>",
                model_py="from pydantic import BaseModel\n\nclass DemoOutput(BaseModel):\n    answer: str\n    summary: str\n",
                rationale_md="Accepted f-accepted and preserved rejected scope.",
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = write_review_fixture(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
            )

            assert response.status_code == 200
            assert response.json()["proposal_dir"].endswith(
                "versions/v001/reviews/review-001/proposal"
            )
            proposal_dir = runtime_review_dir(root) / "proposal"
            assert (proposal_dir / "prompt.md").read_text(encoding="utf-8") == (
                "Say {{ value }} with summary\n\n<<MODEL>>"
            )
            assert (proposal_dir / "model.py").is_file()
            assert (proposal_dir / "rationale.md").read_text(encoding="utf-8") == (
                "Accepted f-accepted and preserved rejected scope."
            )
            source = json.loads(
                (proposal_dir / "source.json").read_text(encoding="utf-8")
            )
            assert source["experiment_id"] == "demo"
            assert source["source_version"] == "v001"
            assert source["review_id"] == "review-001"
            assert source["judgment_id"] == "j001"
            assert source["validation_batch_id"] == "validation-001"
            assert source["generated_by_model"] == "openai/judge"
            assert source["human_notes_present"] is True
            assert source["decision_summary"] == {
                "accepted": ["f-accepted"],
                "rejected": ["f-rejected"],
                "deferred": ["f-deferred"],
            }
            assert calls[0]["model"] == "openai/judge"
            assert calls[0]["response_model"].__name__ == "PydanticProposalDraft"
            assert calls[0]["validation_context"] is None
            assert calls[0]["prompt"].count("<<MODEL>>") == 1
            assert "[OUTPUT_MODEL_SCHEMA: see CURRENT_MODEL_PY]" in calls[0]["prompt"]
            assert "Say {{ value }}" in calls[0]["prompt"]
            assert "Current model: local/a" in calls[0]["prompt"]
            assert "Keep the answer terse" in calls[0]["prompt"]
            assert "VALIDATION_METADATA_JSON" in calls[0]["prompt"]
            assert "validation-001" in calls[0]["prompt"]
            assert "RUBRIC_SNAPSHOT_MD" not in calls[0]["prompt"]
            assert "f-accepted" in calls[0]["prompt"]
            assert "The output misses the required summary." in calls[0]["prompt"]
            assert "f-rejected" in calls[0]["prompt"]
            assert "REJECTED_FINDINGS_AS_CONSTRAINTS_JSON" in calls[0]["prompt"]
            assert "Out of scope" in calls[0]["prompt"]
            assert "f-deferred" not in calls[0]["prompt"]
            assert "class DemoOutput(BaseModel)" in calls[0]["prompt"]
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_reads_existing_proposal_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_review_fixture(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        review_dir = runtime_review_dir(root)
        proposal_dir = runtime_review_dir(root) / "proposal"
        proposal_dir.mkdir()
        (proposal_dir / "prompt.md").write_text("Improved prompt", encoding="utf-8")
        (proposal_dir / "model.py").write_text(
            "from pydantic import BaseModel\n\nclass DemoOutput(BaseModel):\n    answer: str\n",
            encoding="utf-8",
        )
        (proposal_dir / "rationale.md").write_text("Why", encoding="utf-8")
        write_valid_proposal_source(review_dir)

        response = TestClient(app).get(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["proposal_dir"].endswith(
            "versions/v001/reviews/review-001/proposal"
        )
        assert body["proposal"]["prompt_md"] == "Improved prompt"
        assert body["proposal"]["model_py"].startswith("from pydantic")
        assert body["proposal"]["rationale_md"] == "Why"
        assert body["source"]["review_id"] == "review-001"


def test_api_previews_proposal_prompt_without_creating_proposal_artifacts() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_review_fixture(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        proposal_dir = runtime_review_dir(root) / "proposal"

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal/preview-prompts"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["workflow_kind"] == "proposal"
        assert body["warnings"] == []
        assert len(body["prompts"]) == 1
        prompt = body["prompts"][0]
        assert prompt["kind"] == "proposal"
        assert prompt["title"] == "Generate proposal"
        assert prompt["model"] == "openai/judge"
        assert prompt["case_id"] is None
        assert prompt["repeat_index"] is None
        assert prompt["validator_id"] is None
        assert "ACCEPTED_FINDINGS_JSON" in prompt["prompt"]
        assert "REJECTED_FINDINGS_AS_CONSTRAINTS_JSON" in prompt["prompt"]
        assert "Keep the answer terse" in prompt["prompt"]
        assert prompt["character_count"] == len(prompt["prompt"])
        assert prompt["word_count"] == len(prompt["prompt"].split())
        assert not proposal_dir.exists()


def test_api_strips_wrapping_code_fences_from_proposal_files() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        return FakeGeneratedStructured(
            response_model(
                prompt_md="```text\nSay {{ value }} with summary\n\n<<MODEL>>\n```",
                model_py=(
                    "```python\n"
                    "from pydantic import BaseModel\n\n"
                    "class DemoOutput(BaseModel):\n"
                    "    answer: str\n"
                    "```"
                ),
                rationale_md="```markdown\nAccepted f-accepted.\n```",
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_review_fixture(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
            )

            assert response.status_code == 200
            proposal_dir = runtime_review_dir(root) / "proposal"
            assert (proposal_dir / "prompt.md").read_text(encoding="utf-8") == (
                "Say {{ value }} with summary\n\n<<MODEL>>"
            )
            assert (proposal_dir / "model.py").read_text(encoding="utf-8") == (
                "from pydantic import BaseModel\n\n"
                "class DemoOutput(BaseModel):\n"
                "    answer: str"
            )
            assert (proposal_dir / "rationale.md").read_text(encoding="utf-8") == (
                "Accepted f-accepted."
            )
            assert response.json()["proposal"]["prompt_md"] == (
                "Say {{ value }} with summary\n\n<<MODEL>>"
            )
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_generates_dry_run_proposal_without_live_llm() -> None:
    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        raise AssertionError("dry-run proposal must not call live structured LLM")

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = write_review_fixture(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app, raise_server_exceptions=False).post(
                "/api/experiments/demo/versions/v001/reviews/review-001/proposal",
                json={"dry_run": True},
            )

            assert response.status_code == 200
            body = response.json()
            assert body["proposal"]["prompt_md"]
            assert body["proposal"]["model_py"] is not None
            assert body["proposal"]["rationale_md"]
            proposal_dir = runtime_review_dir(root) / "proposal"
            assert (proposal_dir / "prompt.md").is_file()
            assert (proposal_dir / "model.py").is_file()
            assert (proposal_dir / "rationale.md").is_file()
            source = json.loads(
                (proposal_dir / "source.json").read_text(encoding="utf-8")
            )
            assert source["experiment_id"] == "demo"
            assert source["source_version"] == "v001"
            assert source["review_id"] == "review-001"
            assert source["generated_by_model"] == "openai/judge"
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_reports_active_proposal_job_and_rejects_second_proposal() -> None:
    started = Event()
    release = Event()

    def slow_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        del model, prompt, validation_context
        started.set()
        if not release.wait(timeout=5):
            raise TimeoutError("test timed out waiting to release fake proposal")
        return FakeGeneratedStructured(
            response_model(
                prompt_md="Improved prompt\n\n<<MODEL>>",
                model_py=(
                    "from pydantic import BaseModel\n\n"
                    "class DemoOutput(BaseModel):\n"
                    "    answer: str\n"
                ),
                rationale_md="Why this proposal helps.",
            )
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = slow_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_review_fixture(root)
            app = create_app(PromptLabConfig.from_env(project_root=root))
            client = TestClient(app, raise_server_exceptions=False)
            responses: list[Any] = []

            def start_proposal() -> None:
                responses.append(
                    client.post(
                        "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
                    )
                )

            thread = Thread(target=start_proposal)
            thread.start()
            try:
                assert started.wait(timeout=5)

                active_response = client.get("/api/jobs/active")
                assert active_response.status_code == 200
                active_job = active_response.json()["job"]
                assert active_job["kind"] == "proposal"
                assert active_job["status"] == "running"

                duplicate_response = client.post(
                    "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
                )
                assert duplicate_response.status_code == 409
                assert active_job["job_id"] in duplicate_response.json()["detail"]
            finally:
                release.set()
                thread.join(timeout=5)

            assert responses
            assert responses[0].status_code == 200
    finally:
        release.set()
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def test_api_create_version_copies_clean_source_and_replaces_pydantic_files() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_review_fixture(root)
        version_dir = review_dir.parents[1]
        (version_dir / "runs" / "batch-001" / "case-a").mkdir(parents=True)
        (version_dir / "runs" / "batch-001" / "case-a" / "repeat-001.json").write_text(
            "{}", encoding="utf-8"
        )
        (version_dir / "comparisons" / "comparison-001").mkdir(parents=True)
        proposal_dir = review_dir / "proposal"
        proposal_dir.mkdir()
        (proposal_dir / "prompt.md").write_text(
            "Improved prompt\n\n<<MODEL>>", encoding="utf-8"
        )
        (proposal_dir / "model.py").write_text(
            "from pydantic import BaseModel\n\n"
            "class DemoOutput(BaseModel):\n"
            "    answer: str\n"
            "    summary: str\n",
            encoding="utf-8",
        )
        (proposal_dir / "rationale.md").write_text("Why", encoding="utf-8")
        write_valid_proposal_source(review_dir)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal/create-version"
        )

        assert response.status_code == 200
        assert response.json()["version"] == "v002"
        runtime_version_dir = runtime_review_dir(root).parents[1]
        new_version_dir = runtime_version_dir.parent / "v002"
        assert (new_version_dir / "prompt.md").read_text(encoding="utf-8") == (
            "Improved prompt\n\n<<MODEL>>"
        )
        assert "summary: str" in (new_version_dir / "model.py").read_text(
            encoding="utf-8"
        )
        assert not (new_version_dir / "cases").exists()
        assert (runtime_version_dir.parent.parent / "cases" / "case-a.json").is_file()
        assert not (new_version_dir / "runs").exists()
        assert not (new_version_dir / "reviews").exists()
        assert not (new_version_dir / "comparisons").exists()
        assert (runtime_version_dir / "prompt.md").read_text(encoding="utf-8") == (
            "Say {{ value }}\n\n<<MODEL>>"
        )
        assert "summary: str" not in (runtime_version_dir / "model.py").read_text(
            encoding="utf-8"
        )


def test_api_updating_review_decisions_invalidates_existing_proposal() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_review_fixture(root)
        proposal_dir = review_dir / "proposal"
        proposal_dir.mkdir()
        (proposal_dir / "prompt.md").write_text("Stale prompt", encoding="utf-8")
        (proposal_dir / "rationale.md").write_text("Stale rationale", encoding="utf-8")
        write_valid_proposal_source(review_dir)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app, raise_server_exceptions=False)
        runtime_proposal_dir = runtime_review_dir(root) / "proposal"

        update_response = client.put(
            "/api/experiments/demo/versions/v001/reviews/review-001/decisions",
            json={
                "schema_version": "prompt_lab.decisions/v1",
                "finding_decisions": {
                    "f-accepted": {"decision": "rejected", "reason": "Changed"},
                    "f-rejected": {"decision": "rejected", "reason": "Out of scope"},
                    "f-deferred": {"decision": "deferred", "reason": "Later"},
                },
            },
        )
        get_response = client.get(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
        )
        create_response = client.post(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal/create-version"
        )

        assert update_response.status_code == 200
        assert not runtime_proposal_dir.exists()
        assert get_response.status_code == 404
        assert create_response.status_code == 404
        assert create_response.json()["detail"] == "Proposal not found"


def test_api_updating_review_human_notes_invalidates_existing_proposal() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_review_fixture(root)
        proposal_dir = review_dir / "proposal"
        proposal_dir.mkdir()
        (proposal_dir / "prompt.md").write_text("Stale prompt", encoding="utf-8")
        (proposal_dir / "rationale.md").write_text("Stale rationale", encoding="utf-8")
        write_valid_proposal_source(review_dir)
        app = create_app(PromptLabConfig.from_env(project_root=root))
        client = TestClient(app, raise_server_exceptions=False)
        runtime_proposal_dir = runtime_review_dir(root) / "proposal"

        update_response = client.put(
            "/api/experiments/demo/versions/v001/reviews/review-001/human-notes",
            json={"notes": "Use the new human instruction."},
        )
        get_response = client.get(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
        )
        create_response = client.post(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal/create-version"
        )

        assert update_response.status_code == 200
        assert not runtime_proposal_dir.exists()
        assert get_response.status_code == 404
        assert create_response.status_code == 404
        assert create_response.json()["detail"] == "Proposal not found"


def test_api_create_version_rejects_mismatched_source_without_creating_version() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_review_fixture(root)
        version_dir = review_dir.parents[1]
        proposal_dir = review_dir / "proposal"
        proposal_dir.mkdir()
        (proposal_dir / "prompt.md").write_text("Improved prompt", encoding="utf-8")
        (proposal_dir / "rationale.md").write_text("Why", encoding="utf-8")
        write_json(
            proposal_dir / "source.json",
            {
                "experiment_id": "demo",
                "source_version": "v999",
                "review_id": "review-001",
                "judgment_id": "j001",
            },
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal/create-version"
        )

        assert response.status_code == 400
        assert "Proposal source mismatch" in response.json()["detail"]
        assert not (runtime_review_dir(root).parents[1].parent / "v002").exists()


def test_api_create_version_cleans_partial_version_when_replacement_fails() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_review_fixture(root)
        version_dir = review_dir.parents[1]
        experiment_path = review_dir.parents[3] / "experiment.json"
        manifest = json.loads(experiment_path.read_text(encoding="utf-8"))
        manifest["template"]["path"] = "../escaped.md"
        write_json(experiment_path, manifest)
        proposal_dir = review_dir / "proposal"
        proposal_dir.mkdir()
        (proposal_dir / "prompt.md").write_text("Improved prompt", encoding="utf-8")
        (proposal_dir / "rationale.md").write_text("Why", encoding="utf-8")
        write_valid_proposal_source(review_dir)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).post(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal/create-version"
        )

        assert response.status_code == 400
        assert not (runtime_review_dir(root).parents[1].parent / "v002").exists()


def test_api_create_version_returns_404_when_proposal_missing() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_review_fixture(root, output_type="text")
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).post(
            "/api/experiments/demo/versions/v001/reviews/review-001/proposal/create-version"
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Proposal not found"


def test_api_rejects_text_proposal_that_returns_model_py() -> None:
    captured: dict[str, Any] = {}

    def fake_generate_structured(
        model: str,
        prompt: str,
        response_model: Any,
        validation_context: dict[str, Any] | None,
    ) -> FakeGeneratedStructured:
        captured["response_model"] = response_model
        return FakeGeneratedStructured(
            {
                "prompt_md": "Improved text prompt",
                "model_py": "class ShouldNotExist: ...",
                "rationale_md": "Text proposals cannot change model.py.",
            }
        )

    original_generate_structured = llm_client.generate_structured
    llm_client.generate_structured = fake_generate_structured  # type: ignore[assignment]
    try:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            review_dir = write_review_fixture(root, output_type="text")
            app = create_app(PromptLabConfig.from_env(project_root=root))

            response = TestClient(app).post(
                "/api/experiments/demo/versions/v001/reviews/review-001/proposal"
            )

            assert response.status_code == 400
            assert captured["response_model"].__name__ == "TextProposalDraft"
            assert (
                "model_py"
                not in captured["response_model"].model_json_schema()["properties"]
            )
            assert response.json()["detail"] == (
                "Text output proposals cannot include model_py"
            )
            assert not (runtime_review_dir(root) / "proposal").exists()
    finally:
        llm_client.generate_structured = original_generate_structured  # type: ignore[assignment]


def main() -> int:
    tests: list[Any] = [
        test_text_proposal_draft_rejects_model_marker,
        test_pydantic_proposal_draft_requires_prompt_marker_and_model_py,
        test_build_proposal_prompt_sorts_decisions_and_includes_rules,
        test_proposal_prompt_template_file_is_used,
        test_api_generates_proposal_artifacts_with_traceable_source,
        test_api_reads_existing_proposal_artifacts,
        test_api_previews_proposal_prompt_without_creating_proposal_artifacts,
        test_api_strips_wrapping_code_fences_from_proposal_files,
        test_api_generates_dry_run_proposal_without_live_llm,
        test_api_reports_active_proposal_job_and_rejects_second_proposal,
        test_api_create_version_copies_clean_source_and_replaces_pydantic_files,
        test_api_updating_review_decisions_invalidates_existing_proposal,
        test_api_updating_review_human_notes_invalidates_existing_proposal,
        test_api_create_version_rejects_mismatched_source_without_creating_version,
        test_api_create_version_cleans_partial_version_when_replacement_fails,
        test_api_create_version_returns_404_when_proposal_missing,
        test_api_rejects_text_proposal_that_returns_model_py,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
