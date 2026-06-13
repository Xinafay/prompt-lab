from __future__ import annotations


class PromptLabError(Exception):
    """Base class for Prompt Lab domain errors."""


class NotFoundError(PromptLabError):
    """Raised when an experiment artifact does not exist."""


class InvalidArtifactError(PromptLabError):
    """Raised when a stored artifact has invalid shape or content."""
