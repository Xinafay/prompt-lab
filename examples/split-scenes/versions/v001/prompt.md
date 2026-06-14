You are given a part of a story with a numbered list of paragraphs.
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

{% if chapter.data.previous_dirs %}
Summary of previous parts of the story:

---
{% for dir in chapter.data.previous_dirs %}
{{ state.chapters[dir].summary }}
{% endfor %}
---
{% endif %}

Current part markdown with numbered paragraphs:

{{ chapter.text_with_paragraphs }}
