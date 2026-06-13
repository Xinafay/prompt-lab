from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "data-override" / "evals" / "workflow" / "story_parser"
DEST_ROOT = REPO_ROOT / "prompt_lab" / "examples"


DIVIDE_PROMPT = """You are given a part of a story with a numbered list of paragraphs.
Split the part into short structured scenes.

Simple definition of a scene:
- Stable space (same place or clearly continuous movement),
- Continuous time (no jump cut),
- Single immediate focus (goal/topic).

Segmentation heuristics (apply in this order):
1) Chapter change (or chapter/prologue) -> always new scene.
2) Time jump markers ("Later", "At dawn", "That night" etc.) -> new scene.
3) Clear location change (new room/place/vehicle) -> new scene, unless it is a travel montage.
4) Objective/focus shift (e.g., from breaking a door to arguing about trust) -> new scene.
5) Big cast turnover (who is present changes the social center) -> usually new scene.
6) Mode switch that persists (action to deep introspection) -> new scene.
7) One scene is getting too long (more that five paragraphs that are not parts of a conversation) -> divide it.

Rules:
- Keep `summary` as a short, single-sentence description of what happens in the scene.
- Cover all paragraphs exactly once.
- Scenes must be contiguous in paragraph order and must not overlap.
- Prefer shorter scenes by default.
- Paragraphs are numbered from the start of the story - keep the numbering intact.
- Scenes cannot cross the chapter borders (when chapter starts or ends it's always a new scene).

Return only JSON matching this schema:

```
<<MODEL>>
```

{% if previous_summaries %}
Summary of previous parts of the story:

---
{% for summary in previous_summaries %}
{{ summary }}
{% endfor %}
---
{% endif %}

Current part markdown with numbered paragraphs:

{{ chapter_text_with_paragraphs }}
"""


SUMMARY_PROMPT = """You are given part of the story:

{{ chapter_text_with_scenes }}

Write one paragraph summary of this part. This will be used in further processing of the next parts of the story.
"""


SPLIT_RUBRIC = """# Split Scenes Rubric

A good result:

- covers every paragraph exactly once;
- returns contiguous scenes in story order;
- ends the final scene at the final paragraph of the chapter;
- uses scene boundaries for stable place, continuous time, immediate focus, major cast change, or persistent mode shift;
- prefers shorter useful scenes over long mixed scenes;
- keeps summaries short and factual;
- keeps titles concise and specific;
- does not invent events that are not in the chapter.

Validation errors are important evidence. If validation fails, judge whether the prompt or Pydantic model should be adjusted.
"""


SUMMARY_RUBRIC = """# Summarize Chapter Rubric

A good result:

- is one paragraph;
- summarizes the actual chapter content without inventing events;
- preserves the main narrative movement and important state changes;
- mentions important characters, places, objects, facts, or phenomena only when relevant to the chapter's future context;
- stays neutral, factual, and concise;
- avoids literary analysis, commentary, and excessive detail.

Recurring omissions or hallucinated details are more important than one-off wording differences.
"""


def main() -> int:
    _write_split_scenes_example()
    _write_summarize_chapter_example()
    return 0


def _write_split_scenes_example() -> None:
    experiment_dir = DEST_ROOT / "split-scenes"
    version_dir = experiment_dir / "versions" / "v001"
    cases_dir = version_dir / "cases"
    _reset_dir(experiment_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        experiment_dir / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "split-scenes",
            "title": "Split scenes",
            "description": "Split a chapter into contiguous structured scenes.",
            "active_version": "v001",
            "output": {
                "type": "pydantic",
                "model_file": "model.py",
                "model_entrypoint": "model.SceneList",
            },
            "template": {
                "engine": "jinjax",
                "path": "prompt.md",
            },
            "models": {
                "generator_model": "local/example-small-model",
                "judge_model": "openai/example-large-model",
            },
            "run_defaults": {
                "repeat_count": 3,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (experiment_dir / "rubric.md").write_text(SPLIT_RUBRIC, encoding="utf-8")
    (version_dir / "prompt.md").write_text(DIVIDE_PROMPT, encoding="utf-8")
    shutil.copyfile(REPO_ROOT / "data" / "workflows" / "story_parser" / "models" / "scenes.py", version_dir / "model.py")

    for fixture_path in sorted((SOURCE_ROOT / "split-scenes").glob("*/fixture.json")):
        fixture = _read_json(fixture_path)
        case_id = fixture_path.parent.name
        chapter = _target_chapter(fixture)
        context = fixture["context_values"]
        chapter_data = context[f"chapters/{chapter}/data"]
        previous_summaries = [
            context[f"chapters/{previous_dir}/summary"]
            for previous_dir in chapter_data.get("previous_dirs", [])
            if f"chapters/{previous_dir}/summary" in context
        ]
        _write_json(
            cases_dir / f"{case_id}.json",
            _case_payload(
                case_id=case_id,
                title=fixture["meta"].get("display_case_name") or case_id,
                source=_source_metadata(fixture),
                values={
                    "previous_summaries": previous_summaries,
                    "chapter_text_with_paragraphs": context[f"chapters/{chapter}/text_with_paragraphs"],
                    **chapter_data,
                },
            ),
        )


def _write_summarize_chapter_example() -> None:
    experiment_dir = DEST_ROOT / "summarize-chapter"
    version_dir = experiment_dir / "versions" / "v001"
    cases_dir = version_dir / "cases"
    _reset_dir(experiment_dir)
    cases_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        experiment_dir / "experiment.json",
        {
            "schema_version": "prompt_lab.experiment/v1",
            "id": "summarize-chapter",
            "title": "Summarize chapter",
            "description": "Write one concise paragraph summary of a chapter with scene boundaries.",
            "active_version": "v001",
            "output": {
                "type": "text",
            },
            "template": {
                "engine": "jinjax",
                "path": "prompt.md",
            },
            "models": {
                "generator_model": "local/example-small-model",
                "judge_model": "openai/example-large-model",
            },
            "run_defaults": {
                "repeat_count": 3,
                "llm_cache": "disabled",
                "case_order": "case-major",
            },
        },
    )
    (experiment_dir / "rubric.md").write_text(SUMMARY_RUBRIC, encoding="utf-8")
    (version_dir / "prompt.md").write_text(SUMMARY_PROMPT, encoding="utf-8")

    for fixture_path in sorted((SOURCE_ROOT / "summarize-chapter").glob("*/fixture.json")):
        fixture = _read_json(fixture_path)
        case_id = fixture_path.parent.name
        chapter = _target_chapter(fixture)
        context = fixture["context_values"]
        _write_json(
            cases_dir / f"{case_id}.json",
            _case_payload(
                case_id=case_id,
                title=fixture["meta"].get("display_case_name") or case_id,
                source=_source_metadata(fixture),
                values={
                    "chapter_text_with_scenes": context[f"chapters/{chapter}/text_with_scenes"],
                },
            ),
        )


def _source_metadata(fixture: dict[str, Any]) -> dict[str, str]:
    meta = fixture["meta"]
    return {
        "type": "carmilla.workflow_step_eval",
        "workflow_name": str(meta.get("workflow_name") or ""),
        "test_name": str(meta.get("test_name") or ""),
        "case_name": str(meta.get("case_name") or ""),
        "target_step": str(meta.get("target_step") or ""),
        "captured_at": str(meta.get("captured_at") or ""),
    }


def _target_chapter(fixture: dict[str, Any]) -> str:
    target_step = fixture["meta"]["target_step"]
    match = re.search(r"\[([^\]]+)\]", target_step)
    if not match:
        raise ValueError(f"Cannot find target chapter in target_step: {target_step}")
    return match.group(1)


def _case_payload(
    *,
    case_id: str,
    title: str,
    source: dict[str, str],
    values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "prompt_lab.case/v2",
        "id": case_id,
        "title": title,
        "stores": {
            "case": {
                "kind": "flat_file_tree",
                "values": {name: _file_node(value) for name, value in values.items()},
            }
        },
        "bindings": {
            name: {"kind": "store_scope", "store": "case", "path": name}
            for name in values
        },
        "source": source,
    }


def _file_node(value: Any) -> dict[str, Any]:
    return {"__carmilla_flat_file_node__": "file", "value": value}


def _reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
