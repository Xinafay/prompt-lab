# tojson.py

from __future__ import annotations

import json
from typing import Any

from jinja2 import pass_eval_context
from jinja2.nodes import EvalContext
from jinja2.utils import htmlsafe_json_dumps

_MISSING = object()


@pass_eval_context
def tojson(
    eval_ctx: EvalContext,
    value: Any,
    indent: int | None = None,
    ensure_ascii: bool | object = _MISSING,
) -> str:
    """
    Extended version of the `tojson` filter.

    {{ obj | tojson }}              -> standard Jinja behavior
    {{ obj | tojson(2) }}           -> standard behavior + indent=2
    {{ obj | tojson(None, False) }} -> ensure_ascii=False, no indent
    {{ obj | tojson(2, False) }}    -> ensure_ascii=False, indent=2

    Security note: like Jinja's built-in filter this escapes <, >, &, ' so the
    result is safe in HTML. It does NOT escape the U+2028/U+2029 line/paragraph
    separators, which standard Jinja sidesteps via its default ensure_ascii=True.
    With ensure_ascii=False those characters are emitted raw, which can break or
    inject JavaScript inside a <script> block — only pass ensure_ascii=False when
    the output is not embedded in a script context.
    """
    env = eval_ctx.environment
    policies = env.policies

    dumps = policies.get("json.dumps_function") or json.dumps

    # Copy kwargs so we don't mutate env.policies in-place.
    kwargs = dict(policies.get("json.dumps_kwargs", {}))

    if indent is not None:
        kwargs["indent"] = indent

    if ensure_ascii is not _MISSING:
        kwargs["ensure_ascii"] = ensure_ascii

    return htmlsafe_json_dumps(value, dumps=dumps, **kwargs)
