"""Owner-reviewed suggestions for matching new uploads to existing app releases."""
from __future__ import annotations

import asyncio
import json
import os
from difflib import SequenceMatcher
from typing import Iterable

import aiohttp

from app.utils.versions import (
    application_family_key,
    latest_per_family,
    normalize_application_name,
    normalize_platform,
)


def _score(name: str, platform: str | None, app: object) -> float:
    wanted_platform = normalize_platform(platform)
    app_platform = normalize_platform(getattr(app, "platform", None))
    if wanted_platform != "unspecified" and app_platform != "unspecified" and wanted_platform != app_platform:
        return 0.0
    wanted = normalize_application_name(name)
    existing = normalize_application_name(getattr(app, "name", None))
    if not wanted or not existing:
        return 0.0
    if wanted == existing:
        return 1.0
    if wanted in existing or existing in wanted:
        shorter, longer = sorted((len(wanted), len(existing)))
        return min(0.91, 0.68 + shorter / max(1, longer) * 0.23)
    return SequenceMatcher(a=wanted, b=existing).ratio()


async def _ai_rank(name: str, version: str, platform: str, candidates: list[dict]) -> list[dict] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or not candidates:
        return None
    payload = {
        "model": os.getenv("RELEASE_MATCH_MODEL", "gpt-4o-mini"),
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a cautious app-catalog identity reviewer. Select only candidate IDs that are clearly the same app/product, "
                    "not merely related apps, competitors, or separate editions. The operating system/platform must match. "
                    "If uncertain, return no match. Never invent candidate IDs or facts. "
                    'Return JSON: {"matches":[{"id":123,"confidence":0.91,"reason":"short explanation in Arabic"}]}.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "new_upload": {"name": name, "version": version, "platform": platform},
                        "candidates": [
                            {
                                "id": item["id"],
                                "name": item["name"],
                                "version": item["version"],
                                "platform": item["platform"],
                                "category": item["category"],
                                "developer": item["developer"],
                                "description": (item["description"] or "")[:200],
                            }
                            for item in candidates
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    timeout = aiohttp.ClientTimeout(total=7)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            ) as response:
                if response.status != 200:
                    return None
                result = await response.json()
        content = result["choices"][0]["message"]["content"]
        if not isinstance(content, str) or len(content) > 4000:
            return None
        parsed = json.loads(content)
        raw_matches = parsed.get("matches")
        if not isinstance(raw_matches, list):
            return None
        allowed = {item["id"]: item for item in candidates}
        seen: set[int] = set()
        ranked = []
        for item in raw_matches[:5]:
            if not isinstance(item, dict):
                continue
            candidate_id = item.get("id")
            confidence = item.get("confidence")
            candidate = allowed.get(candidate_id) if isinstance(candidate_id, int) else None
            if (
                candidate is None
                or candidate_id in seen
                or not isinstance(confidence, (int, float))
                or not 0.35 <= float(confidence) <= 1
            ):
                continue
            seen.add(candidate_id)
            ranked.append(
                {
                    **candidate,
                    "confidence": float(confidence),
                    "reason": str(item.get("reason") or "اقتراح ذكاء اصطناعي؛ يلزم تأكيدك")[:180],
                    "provider": "openai",
                }
            )
        return ranked
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, IndexError, TypeError, ValueError):
        return None
    except Exception:
        # Never expose provider diagnostics or credentials to Telegram.
        return None


async def suggest_release_candidates(
    applications: Iterable[object],
    *,
    name: str,
    version: str,
    platform: str,
    limit: int = 3,
) -> tuple[str, list[dict]]:
    """Return suggestions only. This helper never mutates catalog records."""
    rows = latest_per_family(
        app for app in applications if getattr(app, "active", True) is True
    )
    scored = [
        (_score(name, platform, app), app)
        for app in rows
        if application_family_key(app)
        == application_family_key({"name": getattr(app, "name", None), "platform": getattr(app, "platform", None)})
    ]
    # The key comparison above is deliberately identity-normalized; all rows remain isolated by OS.
    scored = [(score, app) for score, app in scored if score >= 0.30]
    scored.sort(key=lambda pair: (pair[0], str(getattr(pair[1], "version", "") or "")), reverse=True)
    candidates = [
        {
            "id": int(getattr(app, "id")),
            "name": str(getattr(app, "name", "") or ""),
            "version": str(getattr(app, "version", "") or ""),
            "platform": str(getattr(app, "platform", "") or ""),
            "category": str(getattr(app, "category", "") or ""),
            "developer": str(getattr(app, "developer", "") or ""),
            "description": str(getattr(app, "description", "") or ""),
            "confidence": round(score, 3),
            "reason": "الاسم مطابق بعد توحيد الكتابة." if score >= 0.99 else "تشابه اسم؛ راجع التطبيق قبل اعتماده.",
            "provider": "similarity",
        }
        for score, app in scored[:18]
    ]
    if not candidates:
        return "similarity", []
    ai = await _ai_rank(name, version, platform, candidates)
    if ai:
        return "openai", ai[:limit]
    return "similarity", candidates[:limit]
