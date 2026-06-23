from __future__ import annotations

from copy import deepcopy
from typing import Any

from prompt_lab.models.artifacts import CaseArtifact


def materialize_case_context(case: CaseArtifact) -> dict[str, Any]:
    """Return the plain context object used by prompt templates and validators."""

    return deepcopy(case.payload)
