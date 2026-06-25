Create a concise launch-readiness report for this product brief.

Brief:
{{ brief | tojson(indent=2) }}

Return JSON matching the configured schema:
- keep the summary under 30 words,
- include exactly three short tags,
- include one to three concrete launch risks,
- set launch_ready to false whenever unresolved risks remain.
