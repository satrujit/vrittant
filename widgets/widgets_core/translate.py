"""Sarvam-backed translation helper for widget plugins."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Iterable

import httpx

# Cap concurrent Sarvam calls so one widget doesn't trip rate-limits.
_SEM = asyncio.Semaphore(int(os.getenv("SARVAM_CONCURRENCY", "6")))

logger = logging.getLogger(__name__)

SARVAM_BASE = os.getenv("SARVAM_BASE_URL", "https://api.sarvam.ai")
SARVAM_KEY = os.getenv("SARVAM_API_KEY", "")
MODEL = os.getenv("SARVAM_MODEL", "sarvam-30b")


async def translate_to_odia(text: str, *, context: str = "general") -> str:
    """Translate English/Hindi text to Odia using Sarvam's dedicated /translate
    endpoint (Mayura model). Purpose-built — no LLM commentary or reasoning
    artefacts.

    Falls back to the original text on failure.
    """
    text = (text or "").strip()
    if not text:
        return text
    if not SARVAM_KEY:
        logger.warning("SARVAM_API_KEY not set; returning original text")
        return text

    payload = {
        "input": text,
        "source_language_code": "en-IN",
        "target_language_code": "od-IN",
        "speaker_gender": "Male",
        "mode": "formal",
        "model": "mayura:v1",
    }
    headers = {
        "api-subscription-key": SARVAM_KEY,
        "Content-Type": "application/json",
    }

    try:
        async with _SEM:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(f"{SARVAM_BASE}/translate", json=payload, headers=headers)
                r.raise_for_status()
                translated = (r.json().get("translated_text") or "").strip()
                return translated or text
    except Exception as exc:  # noqa: BLE001 — graceful degradation
        logger.warning("Sarvam translate failed (%s); returning original", exc)
        return text


def _expand_wildcards(payload, parts: list[str]) -> list[list[str]]:
    """Expand any ``*`` segments into concrete list indices, returning all
    matching paths. ``events.*.text`` over a 3-element list yields three paths."""
    expanded: list[list[str]] = [[]]
    cursor: list = [payload]
    for p in parts:
        next_expanded: list[list[str]] = []
        next_cursor: list = []
        for path_so_far, node in zip(expanded, cursor):
            if p == "*":
                if isinstance(node, list):
                    for i, child in enumerate(node):
                        next_expanded.append(path_so_far + [str(i)])
                        next_cursor.append(child)
                # non-list under *: drop this branch
            else:
                next_expanded.append(path_so_far + [p])
                if isinstance(node, list):
                    try:
                        next_cursor.append(node[int(p)])
                    except (ValueError, IndexError, TypeError):
                        next_cursor.append(None)
                elif isinstance(node, dict):
                    next_cursor.append(node.get(p))
                else:
                    next_cursor.append(None)
        expanded, cursor = next_expanded, next_cursor
    return expanded


async def translate_fields(
    payload: dict, field_paths: Iterable[str], *, context: str = "general"
) -> dict:
    """For each dotted ``field.path`` in ``field_paths``, translate the value
    found there and write it into a sibling key suffixed with ``_or``.

    Path segments may be:
      - dict keys (``"foo.bar"``)
      - integer list indices (``"events.0.text"``)
      - ``*`` wildcard for "every item in this list" (``"events.*.text"``)

    For lists of strings the whole list is translated element-wise.
    """
    # Expand wildcards into concrete paths first
    concrete_paths: list[str] = []
    for path in field_paths:
        parts = path.split(".")
        if "*" in parts:
            for expanded in _expand_wildcards(payload, parts):
                concrete_paths.append(".".join(expanded))
        else:
            concrete_paths.append(path)

    # Pass 1: collect (source_text, write_back_fn) pairs
    jobs: list[tuple[str, callable]] = []  # type: ignore[name-defined]
    for path in concrete_paths:
        parts = path.split(".")
        parent = payload
        for p in parts[:-1]:
            if isinstance(parent, list):
                try:
                    parent = parent[int(p)]
                except (ValueError, IndexError, TypeError):
                    parent = None
                    break
            elif isinstance(parent, dict):
                parent = parent.get(p)
            else:
                parent = None
            if parent is None:
                break
        if parent is None:
            continue

        leaf = parts[-1]
        if isinstance(parent, list):
            try:
                idx = int(leaf)
                val = parent[idx]
            except (ValueError, IndexError):
                continue
            if isinstance(val, str):
                jobs.append((val, lambda t, p=parent, i=idx: p.__setitem__(i, t)))
        elif isinstance(parent, dict):
            val = parent.get(leaf)
            translated_key = f"{leaf}_or"
            if isinstance(val, str):
                jobs.append((val, lambda t, p=parent, k=translated_key: p.__setitem__(k, t)))
            elif isinstance(val, list) and all(isinstance(x, str) for x in val):
                # translate each element of a string-list, fan out as separate jobs
                translated_list: list[str] = [""] * len(val)
                parent[translated_key] = translated_list
                for i, s in enumerate(val):
                    jobs.append((s, lambda t, lst=translated_list, i=i: lst.__setitem__(i, t)))

    # Pass 2: translate all in parallel (semaphore caps concurrency)
    if jobs:
        translations = await asyncio.gather(
            *(translate_to_odia(src, context=context) for src, _ in jobs)
        )
        for (_, apply), translated in zip(jobs, translations):
            apply(translated)

    return payload
