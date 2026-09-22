"""The single approved LLM gateway. Every agent calls through this module — never the Azure
OpenAI SDK directly — so there is exactly one place holding credentials, one place logging every
call for the audit trail, and one place where 'versioned prompts' is a real, checkable fact
rather than a policy someone might forget to follow.
"""
import hashlib
import time
from pathlib import Path
from typing import Dict, Optional, Type, TypeVar

from openai import AzureOpenAI
from pydantic import BaseModel

from app.config import settings
from app.db import db_session

T = TypeVar("T", bound=BaseModel)

_prompt_cache: Dict[str, str] = {}
_client: Optional[AzureOpenAI] = None


class LLMCallError(RuntimeError):
    """Raised when Azure OpenAI does not return a response matching the requested schema."""


def _get_client() -> AzureOpenAI:
    global _client
    if _client is None:
        settings.require_azure_openai()
        _client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )
    return _client


def _load_prompt(prompt_file: str) -> str:
    if prompt_file not in _prompt_cache:
        path: Path = settings.prompts_dir / prompt_file
        _prompt_cache[prompt_file] = path.read_text(encoding="utf-8")
    return _prompt_cache[prompt_file]


def _prompt_version_hash(template: str) -> str:
    return hashlib.sha256(template.encode("utf-8")).hexdigest()[:12]


def _log_call(
    *,
    agent: str,
    prompt_file: str,
    prompt_version_hash: str,
    tokens_in: Optional[int],
    tokens_out: Optional[int],
    latency_ms: int,
) -> None:
    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO llm_call_log
                (agent, prompt_file, prompt_version_hash, model_deployment, tokens_in, tokens_out, latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent,
                prompt_file,
                prompt_version_hash,
                settings.azure_openai_deployment,
                tokens_in,
                tokens_out,
                latency_ms,
            ),
        )


def call_structured(
    *,
    agent: str,
    prompt_file: str,
    variables: dict,
    response_model: Type[T],
    temperature: Optional[float] = None,
) -> T:
    """Loads `prompt_file`, fills in `variables`, and forces the model's reply into
    `response_model` (a Pydantic class). Every call is logged with the prompt's content hash,
    so a prompt-file edit is a tracked, visible version change, not a silent behaviour change.
    """
    template = _load_prompt(prompt_file)
    prompt_text = template.format(**variables)
    version_hash = _prompt_version_hash(template)

    client = _get_client()
    kwargs = {}
    if temperature is not None:
        # Some Azure OpenAI deployments (reasoning-tier models) reject any explicit temperature
        # other than their own default and return a 400. Omitting the parameter entirely when
        # the caller doesn't need a specific value keeps this client working across both kinds
        # of deployment, rather than hardcoding an assumption about which one is configured.
        kwargs["temperature"] = temperature

    start = time.monotonic()
    completion = client.chat.completions.parse(
        model=settings.azure_openai_deployment,
        messages=[{"role": "user", "content": prompt_text}],
        response_format=response_model,
        **kwargs,
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise LLMCallError(
            f"Azure OpenAI did not return a response matching {response_model.__name__} "
            f"for prompt '{prompt_file}' (agent={agent})."
        )

    usage = completion.usage
    _log_call(
        agent=agent,
        prompt_file=prompt_file,
        prompt_version_hash=version_hash,
        tokens_in=usage.prompt_tokens if usage else None,
        tokens_out=usage.completion_tokens if usage else None,
        latency_ms=latency_ms,
    )
    return parsed
