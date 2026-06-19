# tojson.py

from __future__ import annotations

import json
from typing import Any

from jinja2 import pass_eval_context
from jinja2.nodes import EvalContext
from jinja2.utils import htmlsafe_json_dumps


@pass_eval_context
def tojson(
    eval_ctx: EvalContext,
    value: Any,
    indent: int | None = None,
    ensure_ascii: bool = False,
    html_safe: bool = False,
    sort_keys: bool = False,
) -> str:
    """
    Extended version of the `tojson` filter.

    JinJax renders to Markdown by default, so the output is NOT escaped for
    HTML and non-ASCII characters are emitted raw. Pass ``html_safe=True`` when
    the result is embedded in an HTML/script context.

    Parameters (all keyword-friendly):
      indent       -- pretty-print indentation (default: None, compact).
      ensure_ascii -- escape non-ASCII as \\uXXXX (default: False).
      html_safe    -- escape <, >, &, ' and wrap in Markup (default: False).
      sort_keys    -- sort object keys alphabetically (default: False).

    {{ obj | tojson }}                       -> raw JSON, ensure_ascii=False
    {{ obj | tojson(2) }}                     -> + indent=2
    {{ obj | tojson(None, True) }}            -> ensure_ascii=True
    {{ obj | tojson(html_safe=True) }}        -> HTML-safe (escapes <, >, &, ')
    {{ obj | tojson(sort_keys=True) }}        -> keys sorted alphabetically

    Security note: ``html_safe=True`` escapes <, >, &, ' so the result is safe
    in HTML. It does NOT escape the U+2028/U+2029 line/paragraph separators,
    which standard Jinja sidesteps via ensure_ascii=True. With ensure_ascii=False
    those characters are emitted raw, which can break or inject JavaScript inside
    a <script> block — only embed such output in a script context with
    ensure_ascii=True.
    """
    env = eval_ctx.environment
    policies = env.policies

    dumps = policies.get("json.dumps_function") or json.dumps

    # Copy kwargs so we don't mutate env.policies in-place.
    kwargs = dict(policies.get("json.dumps_kwargs", {}))

    if indent is not None:
        kwargs["indent"] = indent

    kwargs["ensure_ascii"] = ensure_ascii
    kwargs["sort_keys"] = sort_keys

    if html_safe:
        return htmlsafe_json_dumps(value, dumps=dumps, **kwargs)

    return dumps(value, **kwargs)
