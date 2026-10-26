"""Owner-confirmed application family suggestions for sequential releases."""
from __future__ import annotations

import os
from typing import Any

import httpx

from app.utils.versions import normalize_application_name, normalize_platform


def _score(name: str, platform: str, candidate: Any) -> float:
    wanted_name = normalize_application_name(name)
    candidate_name = normalize_application_name(getattr(candidate, "name", ""))
    wanted_platform = normalize_platform(platform)
    candidate_platform = normalize_platform(getattr(candidate, "platform", None))
    if wanted_platform != "unspecified" and wanted_platform != candidate_platform:
        return 0.0
    if not wanted_name or not candidate_name:
        return 0.0
    if wanted_name == candidate_name:
        return 1.0
    if wanted_name in candidate_name or candidate_name in wanted_name:
        return min(0.92, 0.70 + min(len(wanted_name), len(candidate_name)) / max(len(wanted_name), len(candidate_name)) * 0.22)
    left = set(wanted_name)
    right = set(candidate_name)
    overlap = len(left & right) / max(1, len(left | right))
    return overlap * 0.8


async def suggest_application_families(name: str, version: str, platform: str, candidates: list[Any]) -> dict[str, Any]:
    """Suggest only existing rows; never writes anything. Admin confirmation is mandatory."""
    seen: set[tuple[str, str]] = set()
    unique: list[Any] = []
    for candidate in candidates:
        key = (normalize_application_name(getattr(candidate, "name", "")),
               normalize_platform(getattr(candidate, "platform", None)))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    ranked = sorted(
        ((candidate, _score(name, platform, candidate)) for candidate in unique),
        key=lambda item: (item[1], int(getattr(item[0], "id", 0))),
        reverse=True,
    )
    shortlist = [(candidate, score) for candidate, score in ranked if score >= 0.28][:12]
    provider = "similarity"
    ai_results: list[tuple[int, float, str]] | None = None
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key and shortlist:
        payload = {
            "model": os.getenv("RELEASE_MATCH_MODEL", "gpt-4o-mini"),
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": (
                    "You match software catalog records. Only select a candidate if it is clearly the same app, "
                    "not a competitor or related product. Platform must match. Never invent IDs. If uncertain, "
                    "If uncertain, return an empty matches array. Return a JSON object with a matches array; each item has id, confidence, and reason."
                )},
                {"role": "user", "content": __import__("json").dumps({
                    "wanted": {"name": name, "version": version, "platform": platform},
                    "candidates": [
                        {"id": int(getattr(app, "id", 0)), "name": getattr(app, "name", ""),
                         "version": getattr(app, "version", None), "platform": getattr(app, "platform", None),
                         "category": getattr(app, "category", None), "developer": getattr(app, "developer", None)}
                        for app, _ in shortlist
                    ],
                }, ensure_ascii=False)},
            ],
        }
        try:
            async with httpx.AsyncClient(timeout=7.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                import json
                parsed = json.loads(content)
                raw_matches = parsed.get("matches", [])
                allowed = {int(getattr(app, "id", 0)): (app, score) for app, score in shortlist}
                ai_results = []
                for raw in raw_matches[:5]:
                    if not isinstance(raw, dict):
                        continue
                    try:
                        app_id = int(raw["id"])
                        confidence = max(0.0, min(1.0, float(raw["confidence"])))
                    except (KeyError, TypeError, ValueError):
                        continue
                    if app_id not in allowed or confidence < 0.35 or allowed[app_id][1] < 0.28:
                        continue
                    ai_results.append((app_id, confidence, str(raw.get("reason") or "اقتراح ذكاء اصطناعي")[:160]))
                provider = "openai"
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            ai_results = None
    rows: list[dict[str, Any]] = []
    by_id = {int(getattr(app, "id", 0)): (app, score) for app, score in shortlist}
    if ai_results is not None:
        for app_id, confidence, reason in sorted(ai_results, key=lambda item: item[1], reverse=True):
            app, _ = by_id[app_id]
            rows.append({"id": app_id, "name": app.name, "version": app.version, "platform": app.platform,
                         "confidence": confidence, "reason": reason,
                         "duplicate_version": str(getattr(app, "version", "") or "").strip().casefold() == version.strip().casefold()})
    else:
        for app, confidence in shortlist[:5]:
            rows.append({"id": int(getattr(app, "id", 0)), "name": app.name, "version": app.version,
                         "platform": app.platform, "confidence": confidence,
                         "reason": "تطابق اسم/نظام محتمل؛ تأكد قبل الاعتماد.",
                         "duplicate_version": str(getattr(app, "version", "") or "").strip().casefold() == version.strip().casefold()})
    return {"provider": provider, "items": rows[:5]}
