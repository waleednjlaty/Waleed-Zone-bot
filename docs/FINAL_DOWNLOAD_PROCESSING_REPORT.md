# Bot final download integration review

Baseline main: `11c10b1359df6c5699c91b34b92e043a5a167369`.
Website baseline: `df66eae708c2e391a964d6f64a157d45fce6b9ce`.
Branch: `agent/final-download-processing-integration` in both repositories.

## Changes

Normal `AppCB download` and historical `rip_dl` / `rip_refresh` callbacks use one `resolve_application_download` and one final-message sender. Telegram sources keep the stable website `/download/{id}` route. Approved manual/custom sources and existing SteamRIP dynamic downloads retain their source priority and fail-closed validation. No temporary destination is written into `shrankme_url` or `devupload_url`.

The existing `APP_DOWNLOAD_FOOTER` / `append_app_footer` helper is reused throughout final download blocks, app cards, download acknowledgments, channel promos and copied Files Channel captions. It is idempotent and preserves the exact requested footer. New channel promos use the stable website route as the download CTA, never the raw Telegram file destination or an ephemeral BZZHR signature.

Metadata is bounded as plain UTF-16 text before HTML escaping/formatting. Name, description, version, size, platform and developer cannot inject Telegram HTML. Long metadata is shortened while the footer, HTML tags and URL remain intact. Promo/copied-file captions fit 1024 parsed units; final app/download messages fit 4096. Provider URLs are capped at 2000 for final bot messages. SteamRIP owner previews also bound metadata before formatting.

## Processing and race fixes

- Shared download service commits middleware/catalog reads before external HTTP, captures revision/source fields and re-reads active/published/revision/source afterward. Changed or disabled apps cannot receive stale resolver results.
- Normal and historical callbacks share a bounded per-user/application processing guard. One duplicate callback cannot send a second result during the same in-flight operation.
- BZZHR resolution deduplicates only in-flight work, caps active resolutions at two, uses a total timeout and short backoff, and never keeps completed signed URLs in a cache.
- Telegram copying commits the current read transaction before network calls. Channel publication no longer holds `FOR UPDATE` across Telegram HTTP. Publication is bounded, deduplicated in-process and conditionally persisted against the captured revision; stale sent promos are deleted with a bounded compensating request.
- SteamRIP image migration happens before the application write transaction, with unique image names. Application records no longer remain inside a long network transaction.
- Critical error messages are short Arabic text. Download/provider errors and preview failures log sanitized categories/host/application ID, not signed endpoints or exception payloads.

## Provider security

The original SteamRIP metadata/parser flow was reviewed and preserved. BZZHR provider resolution is now exclusively ordinary public HTTP with the expected HTMX headers and scoped provider cookies. Browser challenge solving, curl impersonation, proxy fallback and unused browser dependencies were removed. Docker no longer installs Chromium for provider bypasses. Human verification fails closed and users can retry later.

`PublicResolver` validates every DNS answer and supplies only vetted addresses to aiohttp's connection path. DNS/connect/read/total deadlines, bounded bodies, manual finite redirects, HTTPS, host policy, no credentials/fragments/custom ports, and no environment proxies are enforced. Raw malformed redirects are rejected before URL normalization.

Finite BZZHR hosts are `bzzhr.to`, `bzzhr.co`, `buzzheavier.com` plus their explicitly enumerated `www` forms. The only additional file hostname is exact `fafda.to`, justified by the pre-existing fixture `test_hx_redirect_direct_download_is_accepted`. Signed destinations require the expected `/d/...` path and exactly one nonempty `v` query value, with public DNS. Current live CDN behavior is not claimed verified.

The default manual host policy matches the website: `devuploads.com,shrinkme.io,shrinkme.site`. Customized `LEGACY_DOWNLOAD_ALLOWED_HOSTS` must match on both deployments. Shared SQLAlchemy fields (`revision`, active/published/developer, source fields and counters) remain compatible; no catalog columns are deleted or synchronized to another DB.

CI exposed a missing runtime dependency when SQLAlchemy 2.1 is freshly installed: asyncio now needs the explicit `sqlalchemy[asyncio]` extra. The requirement was corrected so greenlet is installed on fresh production/CI builds.

## Validation and limitations

Complete local pytest: **182 passed** after the transaction, footer, provider and publication changes. Security-helper Ruff check and Python compilation also passed locally. The local pip-audit package could not be obtained from the available index; dependency audit subsequently passed in GitHub CI. Python compilation is included in repository CI. GitHub CI run https://github.com/waleednjlaty/Waleed-Zone-bot/actions/runs/37652022217 passed tests, compilation, security-helper lint and production dependency audit on code commit `288de0d4aec7e61db94d6af449c2cb4b2b908009`. Companion Website PR: https://github.com/waleednjlaty/Waleed-zone-wab/pull/54.

The website has matching provider fixtures, exact 20-second grant tests, source-race/replay tests, and a real native POST/303 mocked-provider browser journey. See the website's `docs/FINAL_DOWNLOAD_PROCESSING_REPORT.md` for its additive migration and release steps. Bot operation does not run that migration automatically.

Live provider DNS failed in this workspace (`EAI_AGAIN`); live SteamRIP/BZZHR resolution and actual Telegram channel transport are not verified here. Per-process callback/publication guards do not provide crash-safe exactly-once delivery across multiple bot instances. A distributed outbox would require a separately reviewed schema/protocol and is not claimed. A Telegram send may fail after counters commit.

No production database mutation, merge, deployment, AdSense activation or website direct-storage download activation occurred. Keep `DIRECT_DOWNLOADS_ENABLED=false`, the existing Files Channel configuration and all four website AdSense gates false.
