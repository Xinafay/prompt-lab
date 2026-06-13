# api.py

from __future__ import annotations

import jinja2

from .environment import env


def Template(source: str, *args, **kwargs) -> jinja2.Template:
    """
    Drop-in replacement for:

        from jinja2 import Template
        t = Template(...)

    Usage:

        from shared.jinjax import Template
        t = Template(...)

    Compiles `source` on the shared jinjax environment, so Carmilla's custom
    filters are available. Only `source: str` is accepted; to configure
    environment options build your own env with `create_env(...)` and use its
    native methods (e.g. `env.from_string(source)`).
    """
    if args or kwargs:
        raise TypeError(
            "shared.jinjax.Template(...) accepts only source: str. "
            "Build a custom environment with shared.jinjax.create_env(...) instead."
        )

    return env.from_string(source)


__all__ = ["Template"]
