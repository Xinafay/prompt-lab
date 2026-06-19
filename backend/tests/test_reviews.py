from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from fastapi.testclient import TestClient

from prompt_lab.api import create_app
from prompt_lab.config import PromptLabConfig
from test_judge import valid_judgment_payload, write_json


def write_demo_review(root: Path, *, finding_ids: list[str] | None = None) -> Path:
    finding_ids = finding_ids or ["f001"]
    example = root / "experiments" / "demo"
    version_dir = example / "versions" / "v001"
    review_dir = version_dir / "reviews" / "review-001"
    write_json(
        example / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "demo",
            "title": "Demo",
            "description": "",
            "active_version": "v001",
            "output": {"type": "text"},
            "template": {"engine": "jinja2", "path": "prompt.md"},
            "models": {"generator_model": "local/a", "validator_model": "openai/judge", "judge_model": "openai/judge"},
            "run_defaults": {
                "repeat_count": 1,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (version_dir / "prompt.md").parent.mkdir(parents=True, exist_ok=True)
    (version_dir / "prompt.md").write_text("Say {{ value }}", encoding="utf-8")
    write_json(
        review_dir / "judgment.json",
        valid_judgment_payload(
            judge_model="openai/judge",
            findings=[
                {
                    "finding_id": finding_id,
                    "severity": "recommended",
                    "area": "prompt",
                    "category": "recurring_problem",
                    "description": f"The model skips required section {finding_id}.",
                    "evidence": [f"case after-hours repeat {index}"],
                    "suggested_change": "Make the required sections explicit.",
                }
                for index, finding_id in enumerate(finding_ids, start=1)
            ],
        ),
    )
    (review_dir / "judgment.md").write_text("# Judgment\n", encoding="utf-8")
    (review_dir / "rubric_snapshot.md").write_text(
        "Prefer complete answers.", encoding="utf-8"
    )
    write_json(
        review_dir / "decisions.json",
        {
            "schema_version": "prompt_lab.decisions/v1",
            "finding_decisions": {
                finding_id: {"decision": "accepted", "reason": "initial default"}
                for finding_id in finding_ids
            },
        },
    )
    return review_dir


def test_api_updates_one_finding_decision_to_rejected() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_demo_review(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).put(
            "/api/experiments/demo/versions/v001/reviews/review-001/decisions",
            json={
                "schema_version": "prompt_lab.decisions/v1",
                "finding_decisions": {
                    "f001": {"decision": "rejected", "reason": "False positive"}
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["finding_decisions"]["f001"]["decision"] == "rejected"
        saved = json.loads((review_dir / "decisions.json").read_text(encoding="utf-8"))
        assert saved == body


def test_api_rejects_decision_update_missing_judgment_finding_key() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_demo_review(root, finding_ids=["f001", "f002"])
        decisions_path = review_dir / "decisions.json"
        original = decisions_path.read_text(encoding="utf-8")
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).put(
            "/api/experiments/demo/versions/v001/reviews/review-001/decisions",
            json={
                "schema_version": "prompt_lab.decisions/v1",
                "finding_decisions": {
                    "f001": {"decision": "rejected", "reason": "False positive"}
                },
            },
        )

        assert response.status_code == 400
        assert "must exactly match judgment finding ids" in response.json()["detail"]
        assert decisions_path.read_text(encoding="utf-8") == original


def test_api_rejects_decision_update_unknown_judgment_finding_key() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_demo_review(root, finding_ids=["f001", "f002"])
        decisions_path = review_dir / "decisions.json"
        original = decisions_path.read_text(encoding="utf-8")
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).put(
            "/api/experiments/demo/versions/v001/reviews/review-001/decisions",
            json={
                "schema_version": "prompt_lab.decisions/v1",
                "finding_decisions": {
                    "f001": {"decision": "accepted", "reason": "Keep it"},
                    "f002": {"decision": "accepted", "reason": "Keep it"},
                    "f999": {"decision": "rejected", "reason": "Unknown finding"},
                },
            },
        )

        assert response.status_code == 400
        assert "must exactly match judgment finding ids" in response.json()["detail"]
        assert decisions_path.read_text(encoding="utf-8") == original


def test_api_saves_human_notes_markdown() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_demo_review(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).put(
            "/api/experiments/demo/versions/v001/reviews/review-001/human-notes",
            json={"notes": "Keep the finding rejected until case coverage improves.\n"},
        )

        assert response.status_code == 200
        assert response.json() == {
            "human_notes": "Keep the finding rejected until case coverage improves.\n"
        }
        assert (review_dir / "human_notes.md").read_text(encoding="utf-8") == (
            "Keep the finding rejected until case coverage improves.\n"
        )


def test_api_rejects_missing_human_notes_without_changing_existing_notes() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_demo_review(root)
        notes_path = review_dir / "human_notes.md"
        notes_path.write_text("Existing reviewer note.\n", encoding="utf-8")
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).put(
            "/api/experiments/demo/versions/v001/reviews/review-001/human-notes",
            json={},
        )

        assert response.status_code == 422
        assert notes_path.read_text(encoding="utf-8") == "Existing reviewer note.\n"


def test_api_reads_review_state() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        review_dir = write_demo_review(root)
        (review_dir / "human_notes.md").write_text(
            "Reviewer note.\n", encoding="utf-8"
        )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get(
            "/api/experiments/demo/versions/v001/reviews/review-001"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["review_id"] == "review-001"
        assert body["judgment"]["judgment_id"] == "j001"
        assert body["decisions"]["finding_decisions"]["f001"]["decision"] == "accepted"
        assert body["human_notes"] == "Reviewer note.\n"
        assert body["judgment_markdown"] == "# Judgment\n"
        assert body["rubric_snapshot"] == "Prefer complete answers."


def test_api_reads_latest_review_state() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        first_review_dir = write_demo_review(root)
        second_review_dir = first_review_dir.parent / "review-002"
        second_review_dir.mkdir()
        for name in [
            "judgment.json",
            "judgment.md",
            "rubric_snapshot.md",
            "decisions.json",
        ]:
            (second_review_dir / name).write_text(
                (first_review_dir / name).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app).get(
            "/api/experiments/demo/versions/v001/reviews/latest"
        )

        assert response.status_code == 200
        body = response.json()
        assert body["review_id"] == "review-002"
        assert body["judgment"]["judgment_id"] == "j001"


def test_api_rejects_unsafe_review_id_without_reading_parent_paths() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_demo_review(root)
        app = create_app(PromptLabConfig.from_env(project_root=root))

        response = TestClient(app, raise_server_exceptions=False).get(
            "/api/experiments/demo/versions/v001/reviews/%5Cescape"
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Unsafe review id"


def test_api_returns_404_for_missing_review_without_creating_it() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        existing_review_dir = write_demo_review(root)
        missing_review_dir = existing_review_dir.parent / "review-999"
        client = TestClient(create_app(PromptLabConfig.from_env(project_root=root)))

        get_response = client.get(
            "/api/experiments/demo/versions/v001/reviews/review-999"
        )
        decisions_response = client.put(
            "/api/experiments/demo/versions/v001/reviews/review-999/decisions",
            json={
                "schema_version": "prompt_lab.decisions/v1",
                "finding_decisions": {"f001": {"decision": "rejected"}},
            },
        )
        notes_response = client.put(
            "/api/experiments/demo/versions/v001/reviews/review-999/human-notes",
            json={"notes": "Do not create a missing review."},
        )

        assert get_response.status_code == 404
        assert decisions_response.status_code == 404
        assert notes_response.status_code == 404
        assert not missing_review_dir.exists()


def main() -> int:
    tests: list[Any] = [
        test_api_updates_one_finding_decision_to_rejected,
        test_api_rejects_decision_update_missing_judgment_finding_key,
        test_api_rejects_decision_update_unknown_judgment_finding_key,
        test_api_saves_human_notes_markdown,
        test_api_rejects_missing_human_notes_without_changing_existing_notes,
        test_api_reads_review_state,
        test_api_reads_latest_review_state,
        test_api_rejects_unsafe_review_id_without_reading_parent_paths,
        test_api_returns_404_for_missing_review_without_creating_it,
    ]
    for test in tests:
        test()
        print(f"OK: {test.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
