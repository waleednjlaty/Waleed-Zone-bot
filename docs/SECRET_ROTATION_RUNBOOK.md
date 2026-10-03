# Secret rotation — operator procedure, no automated production changes

Phase 8 does not change production values. Treat any credential shown in chat, screenshots, logs or support tools as exposed. Do not paste replacement values into tickets, PRs, shell history or chat. Use the service's secret settings UI or a protected credential tool. These instructions describe manual operations only; the agent has not executed them.

## Before starting

Record deployed commits and the current environment privately. Confirm a rollback release, an owner session, and both services' health. Keep `DIRECT_DOWNLOADS_ENABLED=false`. Apply/verify `migrations/003_runtime_security.sql` separately before a later Phase 8 release; application startup/request handlers now verify/use schema and never create it. The additive migration preserves existing user/session/favorite/visit rows. No schema change is part of secret rotation itself.

A configuration change requires a restart/redeployment of the affected running process. Railway's exact restart/deployment policy must be checked by the operator; do not assume editing a variable mutates an existing process. Public `NEXT_PUBLIC_*` values may require a build; sensitive values must never use that prefix.

## 1. LEGACY_DOWNLOAD_SIGNING_KEY — website only

Generate at least 32 random bytes, encoded as hex/base64url (current validator accepts a 32–512 character string). Update the website server secret and restart all website instances together. The bot never needs this key.

Existing stateless countdown grants become invalid on instances using the replacement key. Current grants live **200 seconds total**: 20-second countdown plus 180-second redeem window. Users can immediately prepare again and wait 20 seconds. Auth sessions and favorites are unaffected. No dual-secret implementation is needed for this short TTL and public-file flow; a rolling deployment can temporarily disagree across instances, so use a coordinated restart or accept a short retry period.

Verify: prepare succeeds and contains no destination, an early POST fails with 425, and after 20 seconds POST returns 303 to the configured exact Telegram message. Old-key grants must return an error on the new release. Do not follow the redirect during HTTP verification if you need to avoid Telegram traffic.

Rollback: restoring the old key may revive still-unexpired old grants. Prefer fixing configuration and preparing a new grant; restoring a known exposed key is an emergency rollback only. After 200 seconds all original grants have expired.

## 2. WEBSITE_STATS_TOKEN — website and bot

This token is read-only statistics authority; it cannot authorize admin mutations. Deploy the new token to the website, then immediately update/restart the bot's statistics client. Expect a brief 401 on bot statistics between updates. This feature can tolerate that interruption; do not add a second permanent stats credential.

Verify bot statistics and website owner statistics. Confirm the new bearer can read `/api/stats`, the old bearer gets 401, and either bearer cannot mutate `/api/admin/*`. Auth sessions and download grants do not depend on this token.

`VISIT_KEY_SALT` should be independent if continuity of daily visitor deduplication matters. Without it, current analytics falls back to `WEBSITE_STATS_TOKEN` (then `DATABASE_URL`): rotating a fallback can split the day's visitor deduplication key and increase counts. This is an analytics limitation, not a session invalidation.

Rollback: update website and bot to the same temporarily restored value; do not leave mismatched services. Revoke the old exposed value again as soon as the fault is fixed.

## 3. PostgreSQL credentials / DATABASE_URL — both services

Prefer a staged database credential change that allows old and new credentials to coexist temporarily. The operator creates a new login role/credential with the **same verified required DML privileges** on website and bot tables/sequences. Do not make either application a schema owner or grant CREATE just to avoid missing migrations. Audit all bot tables, sequences, source revision triggers and favorites before reducing privileges. Use TLS appropriate to the provider, verify certificates, and preserve host/database/SSL settings.

Update/restart the website first with the replacement URL. Confirm public catalog, owner reads, auth/session lookup and a prepared grant. Then update/restart the bot and verify startup schema checks and read-only shared catalog visibility. The pools hold their connection string for process lifetime; both restarts are required. Only once both are healthy should the operator revoke the old login and terminate its remaining connections using the provider's controlled procedure.

Changing credentials on the **same database** does not invalidate hashed sessions or favorites. Countdown HMAC grants remain valid if the signing key and application/source revisions remain unchanged. A connection outage yields safe errors; it must not enable direct storage. Changing to a different database is not credential rotation and is outside this runbook.

Rollback: before revocation, point both services back to the prior credential and restart. After revocation, re-enable a credential only through the provider's controlled account procedure, or issue a fresh replacement. Never restore privileges blindly or paste the URL in logs.

## 4. Other sensitive tokens

| Credential | Services and order | Consequence / verification |
|---|---|---|
| `BOT_TOKEN` | Revoke/regenerate via BotFather; update/restart **bot only** immediately | Bot polling fails until replacement; never add the token to website. Confirm polling and admin authorization without publishing a real file as part of this phase. Telegram file IDs/channel messages are not rotated by a bot token change. |
| `IMGBB_API_KEY` | Replace in bot; restart, then revoke old key according to provider capability | Existing hosted images remain independent. Verify with an operator-controlled inert image only if separately authorized. |
| `VISIT_KEY_SALT` | Website; restart | Daily visitor keys change; no logout. |
| `DOWNLOAD_IP_HASH_KEY` / previous overlap settings | Website; follow existing direct-download key-overlap contract | Can alter network quota identity. Direct remains disabled. Never change ingress verification based on an assumed header. |
| S3 access/secret keys (`DOWNLOAD_S3_*`, optional storage equivalents) | Website only if ever enabled; provider credential lifecycle | No direct-storage enablement or bucket creation. Existing signed URL lifetime is provider-dependent; key revocation may invalidate issued URLs. |
| Credential-bearing `BZZHR_PROXY_URL` / `IMGBB_PROXY_URL` | Bot, then provider revocation | Phase 8 refuses unverified BZZHR proxy use because it bypasses DNS pinning. Review actual egress controls before reintroducing a proxy. No new proxy is provisioned. |

Do not change `OWNER_USER_ID` or `ADMIN_IDS` while rotating secrets. They are authorization configuration, not rotatable signing keys.

## Manual release verification and rollback boundary

Before revoking a replacement's predecessor, verify public home/apps/games/search/details, login/logout/account, anonymous/non-owner admin denial, owner read, and legacy countdown with an existing canary. Do not create/upload/publish files or write application rows as part of this audit. A later authorized operator smoke test is a separate production operation. Keep key values out of HTML, RSC, browser bundles, response errors and logs. Review logs by codes only.

References: [Next.js environment variables](https://nextjs.org/docs/app/guides/environment-variables), [Telegram bot authentication](https://core.telegram.org/bots/api#authorizing-your-bot), [PostgreSQL roles](https://www.postgresql.org/docs/current/database-roles.html).
