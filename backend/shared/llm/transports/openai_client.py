from __future__ import annotations

from typing import Any

from openai import DefaultHttpxClient, OpenAI

from shared.llm.chat_request import PreparedChatRequest


_OPENAI_CLIENT_CACHE: dict[tuple[str, str | None, str | None, bool], OpenAI] = {}


def _get_openai_client(prepared: PreparedChatRequest) -> OpenAI:
    spec = prepared.spec
    key = (spec.server_name, spec.api_key, spec.base_url, spec.no_verify_tls)
    client = _OPENAI_CLIENT_CACHE.get(key)
    if client is not None:
        return client
    if spec.no_verify_tls:
        client = OpenAI(
            api_key=spec.api_key,
            base_url=spec.base_url,
            http_client=DefaultHttpxClient(verify=False),
        )
    else:
        client = OpenAI(api_key=spec.api_key, base_url=spec.base_url)
    _OPENAI_CLIENT_CACHE[key] = client
    return client
