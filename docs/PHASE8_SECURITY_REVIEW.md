# Phase 8 bot security review

Based on main `5544b6f67b4867b35d68ed6e1178d4fd72b3c881`; companion website main `bb96f53243520a7cac68f7ccc74ee823aa88211d`. Both use `agent/phase8-security-performance`. No production DB write/migration, live Telegram publication, deployment, paid infrastructure, owner identity change or direct-storage enablement was performed.

## Authority / threat model

Untrusted inputs are Telegram messages, callback data, retained FSM state, uploaded file metadata and remote SteamRIP/BZZHR/image responses. Catalog mutation authority is `ADMIN_IDS`; explicit `owner_gate` checks now run at the beginning of every privileged admin/upload/SteamRIP handler, supplementing existing owner middleware. A forged FSM or direct callback invocation cannot grant authority. Public SteamRIP download lookup remains public. Group moderation retains its existing owner-or-Telegram-group-admin authority and denial for ordinary members. No owner IDs were changed.

Normal APK storage remains Telegram `copy_message` to a public channel; the bot does not obtain Telegram file download URLs or download/proxy APK bytes to local disk. Only after successful copy does metadata reach the shared repository. A DB failure after successful external copy can leave an orphan public channel message (existing non-transactional external-service boundary); there is no destructive cleanup or retry-based duplicate publication introduced.

## Changes and tests

* File size must be known, positive integer and <= configured maximum before channel API/copy. Unknown/zero/boolean/oversized input fails. Filename/MIME fields reject control/bidi characters.
* Channel public username and optional configured numeric ID must match resolved channel data. Private/wrong/protected channels and protected incoming files fail. get_chat/get_me/get_chat_member have 15s deadlines; copy_message has 30s deadline. Bot must be channel administrator/creator with posting authority before copying.
* Copy failure yields no source metadata. Mock tests cover username-only, ID+username, wrong ID/name, private/protected channel, insufficient bot rights, protected source, unknown/oversized file and copy failure; no Telegram network was contacted.
* PostgreSQL connect/command 10s, statements 5s, lock 2s, idle transaction 120s. Startup only verifies required shared catalog/revision/source schema; it fails closed when absent. SQLite create_all remains local/test-only. Existing transaction/revision triggers and SQLAlchemy version checks continue to reject stale bot/website writes; counter increments preserve revision.
* SteamRIP main source fetch **and size fallback** use HTTPS finite-host, bounded 2MiB bodies and an overall 25s deadline. All redirects are validated before contact. Public-only DNS candidates are pinned into aiohttp's resolver; a mixed private/public result is rejected. No environment proxy or second DNS resolution at connection time. Tests cover loopback/RFC1918/link-local/metadata/mapped IPv6, schemes, credentials, nonstandard ports, DNS mixing, redirect and body/time bounds.
* ImgBB fallback image fetch uses the same connection guard, 32MiB cap/45s total deadline and raster MIME allowlist; SVG/HTML responses denied. Fixed ImgBB upload rejects redirects so API key is not forwarded. Existing operator IMGBB proxy configuration is retained for that fixed provider upload endpoint.
* BZZHR fast extraction restricts mirror/signed endpoint hosts and pins public curl addresses. Browser fallback pins finite mirror/www/Cloudflare challenge hosts and routes all resources through host/HTTPS checks with service workers/QUIC/unknown DNS disabled. Nonempty BZZHR_PROXY_URL is now refused pending separately verified egress controls. This is a documented compatibility restriction for SSRF protection, not a promise that every live provider challenge will work.
* Final BZZHR public CDN hostname can rotate; returned HTTPS delivery URLs reject private literals, controls, credentials, nonstandard ports and fragments. They are handed to the user's browser, not fetched by the server. Provider-hostname trust and client-side DNS remain an accepted third-party boundary.
* Root logging formatter redacts configured sensitive values and raw Authorization/Cookie/passwords, DB/proxy credentials, Telegram API/file URLs, signed query strings; quoted multi-cookie headers covered. Settings repr/validation hides private inputs. SteamRIP size fallback failures log a type code, not URL/body/exception internals.

The website retains server 20-second enforcement and exact validated Telegram native 303. Delayed Telegram message/file deletion or channel renaming cannot be continuously verified without adding bot credentials to the website; manual rebind/unpublish is required. Public files are redistributable, not confidential or DRM-protected. Stateless grants remain same-client replayable for 180 seconds after the 20-second delay, with current source/revision checks and shared PostgreSQL quotas; this avoids a heavy single-use request table.

## Configuration inventory / rotation

Sensitive: BOT_TOKEN, DATABASE_URL, IMGBB_API_KEY, WEBSITE_STATS_TOKEN, credential-bearing BZZHR_PROXY_URL/IMGBB_PROXY_URL. Authority: ADMIN_IDS. Channel config: FILES_CHANNEL_ID/USERNAME, fallback CHANNEL_ID/USERNAME; group config GROUP_ID/USERNAME. Public service endpoints: WEBSITE_BASE_URL/WEBSITE_STATS_URL. Limits/tooling: MAX_UPLOAD_BYTES, HTTP_MAX_RETRIES, DOWNLOAD_DIR, SCRAPLING_EXECUTABLE_PATH, script PYTHONIOENCODING/PYTHONUTF8. No deployed values were inspected or printed; no website BOT_TOKEN is introduced. Application/source IDs are private metadata except necessary public catalog IDs and owner source displays.

Production-shaped Telegram token examples in `BEGINNERS_GUIDE.md` and `LOCAL_DEVELOPMENT.md`, and ImgBB key examples in guides, were replaced with opaque provider placeholders; a regression assertion scans guides for both credential formats. Their validity was not tested. Removal does not erase Git history; if any example was ever a real credential, revoke/rotate it manually as exposed. No history rewrite or token revocation was performed.

[SECRET_ROTATION_RUNBOOK.md](SECRET_ROTATION_RUNBOOK.md) specifies website signing key, shared stats bearer, staged shared PostgreSQL credentials, BotFather/ImgBB/proxy tokens, coordinated restarts, verification/rollback and session/grant consequences. Exposed historical secrets need manual rotation. No dual-signing complexity is added for the 200-second total grant TTL. No new required variable; review any nonempty BZZHR proxy before a later authorized release.

## Evidence / accepted limits

Python 3.11 local validation: `python -m compileall -q app config database integrations main.py`; **pytest 132 passed / 0 failed / 0 skipped**. pip-audit of the installed requirement set reported **zero known vulnerabilities** at review time; broad dependency ranges remain a reproducibility limitation. Runtime requirements/framework majors unchanged.

Selected security/helper files pass Ruff. Full repository Ruff was also run: **166 existing findings vs 187 on original main**, mainly style/import debt. It is not reported as a passing full-repo lint, and no rule was disabled. Commands:

```sh
python -m compileall -q app config database integrations main.py
pytest -q
ruff check app config database integrations main.py
ruff check app/utils/owner_guard.py app/utils/logging_config.py app/services/upload_service.py \
 database/database.py integrations/public_http.py integrations/steamrip_metadata.py tests/test_phase8_security.py
pip-audit -r requirements.txt
```

The companion website native test launches the actual Python repository against disposable PostgreSQL and actual HTTPS Next routes: website creates draft → bot sees/binds/edits/publishes → fresh website detail/search visibility → stale revisions denied in both directions → counters do not stale forms → countdown → exact 303. Local browser suites at 360/768/1440 intercept all Telegram/provider traffic. These are synthetic tests, not a real production canary.

Shared database quotas are multi-instance authority; local early shedding only supplements them. They are not DDoS protection: shared unverified-ingress buckets can cause user contention and DB hot keys add load. Bot provider work inside transactions and optional browser fallback remain connection/memory bottlenecks. No Redis, paid service or catalog cache added.

Before any later release, the operator must verify existing shared migration/revision triggers and apply/verify the website additive `003_runtime_security.sql` separately (lazy auth/visit DDL removed); optional `004_phase8_indexes.sql` is supported by disposable EXPLAIN. Neither was run in production. Validate Railway HTTPS, trusted ingress overwrite, secret alignment, timeout suitability and public files channel identity. Migration/deployment/publishing require separately authorized operator work. Direct remains false.

See companion website [security review](https://github.com/waleednjlaty/Waleed-zone-wab/blob/agent/phase8-security-performance/docs/PHASE8_SECURITY_REVIEW.md) and [performance review](https://github.com/waleednjlaty/Waleed-zone-wab/blob/agent/phase8-security-performance/docs/PERFORMANCE_REVIEW.md) for environment inventory, quotas, browser/client leakage evidence, manual production checks and local before/after metrics.
