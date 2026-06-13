# shared.jinjax
#
# A thin layer over Jinja2 with Carmilla's own extensions.
# The public API is re-exported here, so this still works:
#
#     from shared.jinjax import Template
#     t = Template(...)

from __future__ import annotations

from .api import Template
from .environment import create_env, env

__all__ = [
    "Template",
    "create_env",
    "env",
]
