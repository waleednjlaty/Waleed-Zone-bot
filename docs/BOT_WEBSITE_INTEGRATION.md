# Bot / Website integration contract

Both repositories own the same PostgreSQL `applications` catalog. Neither client is authoritative over the other. There is no synchronization job or second catalog. Website reads use per-request caching only, including search, so a committed bot change is visible on the next request. An already-open page needs refresh.

## Additive schema

`migrations/002_delivery_sources.sql` is identical in both PRs. Apply it once, explicitly, after review. This change does not apply production migrations. PostgreSQL bot startup checks existing schema without running DDL; SQLite remains a local test/development option only.

`applications.revision` is advanced by a PostgreSQL BEFORE UPDATE trigger. `updated_at` is also maintained by the database. Every source insert/update/delete advances the parent application revision. Traffic-only views/download counters preserve the catalog revision and do not invalidate owner forms or countdowns. Legacy `shrankme_url` and `devupload_url` remain intact. SteamRIP continues to use `devupload_url` as its source page, not an upload-service URL.

`site_delivery_sources` has primary key `(application_id, provider)`, an application FK, provider (`telegram`, `railway-s3`, `s3`), Telegram chat/message/username/file references, filename, byte size, MIME and creation/update timestamps. Telegram rows require a valid public username and positive message ID. Website references may have unknown chat ID/file metadata. Bot references come from a verified `get_chat` + `copy_message` result. No token, API file URL or arbitrary destination URL is stored in this table.

Future S3 delivery retains the stable `/download/{application_id}` contract. Real direct storage remains in the existing secure version/file/config system with its integrity, scan, ingress, budget and kill-switch gates. Provider values reserved in this table are not activated implementations.

## States and concurrency

Saved means committed metadata. Draft means `published=false`. Active is separate from publication. Both public clients require `active=true AND published=true`. Archive sets both false; reactivation returns to draft. No default hard delete.

Website owner writes use `requireOwner()` and `authorizeOwnerRequest()`, same-origin checks, session-bound CSRF, bounded JSON and strict field whitelists. Catalog metadata bodies are capped at 8192 bytes; other existing admin/download bodies retain 2048 bytes. Existing record writes require a 64-character SHA-256 `expected_revision` of the revision value. The application is locked before comparing the revision or changing a source. Conflicts return HTTP 409 `STALE_REVISION`; the UI refetches and requires a deliberate new action, never blind retries. Missing source tables/columns fail closed with 503.

The bot uses `ADMIN_IDS` for all upload, attachment, edit, publication and archive mutations. SQLAlchemy version checks prevent stale ORM edits; multi-step edits/attachments capture the starting revision. Attachments lock the application before source upsert. A conflicted copied file is left unlinked in the files channel; no automatic delete or destructive compensation is attempted.

## Bot workflow

Owner uploads a Telegram document → verify files channel username/ID and public, unprotected channel → `copy_message` inside Telegram → collect metadata → atomically insert application and delivery source → save draft → optionally publish a promo to the main channel. APK bytes are never downloaded or buffered on the bot host. A skipped image is allowed; ImgBB remains optional for small cover photos only.

Bot Admin → Applications lists all shared rows, including website drafts. `📎 ربط ملف Telegram` attaches/replaces a document for an existing app without changing publication. Public browse/search/favorites exclude drafts and disabled apps.

Configure `FILES_CHANNEL_ID` plus `FILES_CHANNEL_USERNAME` on the bot. If BOTH are absent, use the complete main `CHANNEL_ID`/`CHANNEL_USERNAME` pair and verify it against Telegram. A partial files-channel pair fails closed and never mixes channels. Main-channel fallback puts raw files into the main channel; use a separate PUBLIC files channel when that is undesirable. Telegram public files are publicly accessible: the site countdown is a site navigation gate, not private-file access control.

## Website workflow

Owner Admin → Applications → create/edit metadata → optionally bind `https://t.me/configured_channel/positive_message_id` or a username/message pair → publish. The website only manages metadata. It neither uploads APK bytes nor calls Telegram with bot credentials. Pasted references are validated syntactically and against configured channel; the website cannot attest document existence or MIME without bot access. Use the bot to copy/verify the file; deleted messages or renamed channels require updating the source/configuration.

New catalog write APIs never accept legacy external URL fields. Existing external records remain supported. Bot runtime no longer builds DevUploads/ShrinkMe clients or requires their API keys; those modules are deprecated offline references only.

## URLs and delivery

Every new channel promo's primary CTA is `🌐 تحميل من Waleed Zone` → `${WEBSITE_BASE_URL}/download/{id}`. Optional details link uses `/app/{id}`, which redirects to the canonical detail route. SteamRIP channel promos use the same website CTA; its existing live bot extractor stays available.

`/download/{id}` chooses a ready existing secure direct-storage presentation first, otherwise a valid Telegram source, otherwise an approved existing external legacy record. An explicitly disabled download config denies fallback. Unpublished/disabled applications deny public download requests.

Telegram fallback: POST `/api/downloads/legacy/prepare` JSON `{application_id}` → HMAC signed, browser-cookie-bound token with application/revision/nonce/ready/expiry and ISO `ready_at`, `expires_at`, `server_time` → countdown → native POST form `/api/downloads/legacy/redeem` `{application_id, token}` → exact HTTP 303 Location `https://t.me/<configured-channel>/<message-id>`. Initial HTML, RSC props and prepare JSON contain no destination. No fetch/Blob/file proxy; the browser goes directly to Telegram after 303.

Set `LEGACY_DOWNLOAD_SIGNING_KEY` to an independent >=32-character random server-only secret. Tokens become ready at exactly 20 seconds, expire 180 seconds after readiness (200 seconds total), use constant-time HMAC verification and bind the HttpOnly/SameSite client cookie. Changing app/source revision, publication or active state invalidates delivery. Stateless grants may be reused by the same browser within their short TTL; they are NOT one-time direct-download grants. Process-wide bounded request shedding is local only, not a distributed rate limiter. The existing secure direct system retains its separate one-time token and shared quota rules.

On the website configure `FILES_CHANNEL_USERNAME` to match the bot (no BOT_TOKEN). `CHANNEL_USERNAME` fallback is allowed only if no FILES configuration exists. Redeem reconstructs the URL; arbitrary database URLs can never become Telegram destinations. Legacy external records use exact `LEGACY_DOWNLOAD_ALLOWED_HOSTS` (default devuploads.com, shrinkme.io, shrinkme.site), HTTPS without credentials, custom ports or fragments. SteamRIP source pages hand off to the existing live bot flow instead of falsely advertising a direct file.

## Rollout boundary

No merge, manual deployment, production migration, storage activation, infrastructure provisioning or billing change. `DIRECT_DOWNLOADS_ENABLED=false` stays unchanged. These PRs need the reviewed additive migration and consistent channel/signing configuration before Telegram delivery can run in production. Verification uses fixtures and isolated local databases, never production or real Telegram channel writes.

## References

- Telegram copyMessage: https://core.telegram.org/bots/api#copymessage
- Telegram public message links: https://core.telegram.org/api/links#message-links
- SQLAlchemy optimistic version counters: https://docs.sqlalchemy.org/en/20/orm/versioning.html
