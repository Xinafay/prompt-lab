# environment.py

from __future__ import annotations

import jinja2
from jinja2.sandbox import SandboxedEnvironment

from .filters import register_filters


def create_env(*args, **kwargs) -> jinja2.Environment:
    """
    Build a jinja2.Environment with all of Carmilla's extensions.

    Accepts the same arguments as jinja2.Environment(...) (e.g. loader=...,
    autoescape=...) and additionally configures Carmilla's policies and
    registers its filters on the result:

        env = create_env()                                 # string templates
        env = create_env(loader=FileSystemLoader("tpl"))   # name-based templates

    The return value is a plain jinja2.Environment — use its native methods
    directly: env.from_string(...), env.get_template(...), etc.
    """
    kwargs.setdefault("undefined", jinja2.StrictUndefined)
    env = SandboxedEnvironment(*args, **kwargs)

    # Explicit, to make it clear we are not mutating the nested policies dict.
    env.policies["json.dumps_kwargs"] = {
        **env.policies.get("json.dumps_kwargs", {}),
    }

    register_filters(env)

    return env


# Default, loaderless environment for the whole application (string templates).
env = create_env()


__all__ = ["create_env", "env"]
