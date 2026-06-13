# filters package

from __future__ import annotations

import jinja2

from .tojson import tojson


def register_filters(env: jinja2.Environment) -> None:
    """
    Register all custom filters on the given environment.

    To add another filter: create a new module under `filters/`,
    import it here, and add an entry to `env.filters`.
    """
    env.filters["tojson"] = tojson


__all__ = ["register_filters", "tojson"]
