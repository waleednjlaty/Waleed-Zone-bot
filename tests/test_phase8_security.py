from __future__ import annotations

import logging
import socket
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_telegram_delivery import incoming, settings

from app.services.upload_service import UploadService
from app.utils.logging_config import SecretRedactingFormatter, redact
from integrations import public_http
from integrations.steamrip_extractor import (
    _bzzhr_candidates,
    _direct_link_from_headers,
    _is_bzzhr_url,
    _is_steamrip_url,
    fetch_game_data,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://steamrip.com/a",
        "file:///etc/passwd",
        "ftp://example.com/a",
        "https://localhost/a",
        "https://127.0.0.1/a",
        "https://127.2.3.4/a",
        "https://[::1]/a",
        "https://[::ffff:127.0.0.1]/a",
        "https://10.1.2.3/a",
        "https://172.16.0.1/a",
        "https://192.168.1.1/a",
        "https://169.254.169.254/latest/meta-data",
        "https://[fe80::1]/a",
        "https://[fc00::1]/a",
        "https://metadata.google.internal/a",
        "https://user:pass@steamrip.com/a",
        "https://steamrip.com:444/a",
        "https://steamrip.com/a\r\nHeader: value",
        "https://steamrip.com/a#bad",
        "https://steamrip.com\\@127.0.0.1/a",
    ],
)
def test_ssrf_url_rejected(url):
    with pytest.raises(ValueError):
        public_http.public_url(url)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.1.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "::1",
        "fe80::1",
        "fc00::1",
        "::ffff:127.0.0.1",
        "224.0.0.1",
    ],
)
def test_dns_private_and_mixed_address_denied(monkeypatch, address):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **kw: [
            (socket.AF_INET, 1, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, 1, 6, "", (address, 443)),
        ],
    )
    with pytest.raises(ValueError, match="PRIVATE_DNS_ADDRESS"):
        public_http.public_addresses("steamrip.com")


async def test_resolver_returns_vetted_numeric_addresses_without_second_dns(monkeypatch):
    calls = []

    def dns(*a, **kw):
        calls.append(a[0])
        return [(socket.AF_INET, 1, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    resolved = await public_http.PublicResolver().resolve("steamrip.com", 443)
    assert calls == ["steamrip.com"]
    assert resolved[0]["host"] == "93.184.216.34"
    assert resolved[0]["flags"] == socket.AI_NUMERICHOST


class Response:
    def __init__(self, status=200, headers=None, payload=b"<h1>QA</h1>"):
        self.status = status
        self.headers = headers or {}
        self.payload = payload
        self.content_length = None
        self.url = "https://steamrip.com/qa"
        self.content = self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    async def iter_chunked(self, size):
        yield self.payload


def install_http(monkeypatch, response):
    calls = []

    class Session:
        def __init__(self, **kw):
            assert kw["trust_env"] is False
            assert isinstance(kw["connector"]._resolver, public_http.PublicResolver)
            self.connector = kw["connector"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            await self.connector.close()

        def get(self, url, **kw):
            calls.append(url)
            assert kw["allow_redirects"] is False
            return response

    monkeypatch.setattr(public_http.aiohttp, "ClientSession", Session)
    return calls


@pytest.mark.parametrize(
    "location",
    [
        "https://127.0.0.1/secret",
        "https://evil.example/qa",
        "file:///etc/passwd",
        "https://user:pass@steamrip.com/a",
    ],
)
async def test_redirect_blocked_before_second_contact(monkeypatch, location):
    calls = install_http(monkeypatch, Response(302, {"Location": location}))
    with pytest.raises(ValueError):
        await fetch_game_data("https://steamrip.com/qa")
    assert calls == ["https://steamrip.com/qa"]


async def test_steamrip_source_metadata_regression_without_network(monkeypatch):
    install_http(
        monkeypatch,
        Response(
            payload=(
                b'<h1>QA Free Download</h1>'
                b'<a class="shortc-button" href="https://bzzhr.to/file123">BZZHR</a>'
                b'Size: 2 GB'
            )
        ),
    )
    result = await fetch_game_data("https://steamrip.com/qa")
    assert result["title"] == "QA"
    assert result["size"] == "2 GB"
    assert "https://bzzhr.to/file123" in result["servers"].values()


async def test_http_response_bounds_before_html_parsing(monkeypatch):
    install_http(monkeypatch, Response(payload=b"x" * 1001))
    with pytest.raises(ValueError, match="RESPONSE_TOO_LARGE"):
        await public_http.fetch_public_bytes("https://steamrip.com/qa", max_bytes=1000)


@pytest.mark.parametrize(
    "url",
    [
        "https://bzzhr.to.evil/a",
        "https://bzzhr.to@127.0.0.1/a",
        "http://bzzhr.to/a",
        "https://bzzhr.to:444/a",
        "https://[oops/a",
    ],
)
def test_provider_input_denied(url):
    assert not _is_bzzhr_url(url)
    assert _bzzhr_candidates(url) == []
    assert not _is_steamrip_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/d/a?v=token",
        "file:///d/a?v=token",
        "http://fafda.to/d/a?v=token",
        "https://fafda.to:444/d/a?v=token",
        "https://user:pass@fafda.to/d/a?v=token",
    ],
)
def test_direct_provider_redirect_denies_private_or_unsafe_url(url):
    assert _direct_link_from_headers({"hx-redirect": url}, "https://bzzhr.to/a") is None


@pytest.mark.parametrize("size", [None, 0, -1, True, 1001])
async def test_file_size_checked_before_any_telegram_call(monkeypatch, size):
    monkeypatch.setattr("app.services.upload_service.get_settings", lambda: settings())
    message = incoming()
    message.document.file_size = size
    with pytest.raises(ValueError):
        await UploadService().copy(message)
    message.bot.get_chat.assert_not_awaited()
    message.bot.copy_message.assert_not_awaited()


@pytest.mark.parametrize("status,can_post", [("member", True), ("administrator", False)])
async def test_bot_channel_permissions_before_copy(monkeypatch, status, can_post):
    monkeypatch.setattr("app.services.upload_service.get_settings", lambda: settings())
    message = incoming()
    message.bot.get_chat_member.return_value = SimpleNamespace(
        status=status, can_post_messages=can_post
    )
    with pytest.raises(ValueError, match="FILES_CHANNEL_PERMISSION_DENIED"):
        await UploadService().copy(message)
    message.bot.copy_message.assert_not_awaited()


async def test_copy_failure_does_not_return_metadata_or_download_file(monkeypatch):
    monkeypatch.setattr("app.services.upload_service.get_settings", lambda: settings())
    message = incoming()
    message.bot.copy_message.side_effect = RuntimeError("copy denied")
    with pytest.raises(RuntimeError):
        await UploadService().copy(message)
    message.bot.download.assert_not_called()
    message.bot.get_file.assert_not_called()


async def test_protected_source_denied_before_copy(monkeypatch):
    monkeypatch.setattr("app.services.upload_service.get_settings", lambda: settings())
    message = incoming()
    message.has_protected_content = True
    with pytest.raises(ValueError, match="PROTECTED_SOURCE"):
        await UploadService().copy(message)
    message.bot.copy_message.assert_not_awaited()


@pytest.mark.parametrize(
    "function,callback",
    [
        ("on_rip_name", False),
        ("on_rip_description", False),
        ("on_rip_version", False),
        ("on_rip_category_text", False),
        ("on_rip_platform_text", False),
        ("on_rip_platform_choice", True),
        ("on_rip_category_choice", True),
        ("on_rip_image_none", True),
        ("on_rip_publish_choice", True),
    ],
)
async def test_forged_fsm_and_callbacks_cannot_change_state(function, callback):
    from app.handlers import steamrip

    state = SimpleNamespace(update_data=AsyncMock(), set_state=AsyncMock(), get_data=AsyncMock())
    event = SimpleNamespace(
        from_user=SimpleNamespace(id=999),
        answer=AsyncMock(),
        text="malicious",
        data="rip:pf:Windows",
    )
    await getattr(steamrip, function)(event, state)
    state.update_data.assert_not_awaited()
    state.set_state.assert_not_awaited()
    event.answer.assert_awaited_once()


def test_redaction_unknown_headers_signed_urls_and_traceback(monkeypatch):
    monkeypatch.setenv("BZZHR_PROXY_URL", "http://user:PRIVATE_PROXY@proxy.example")
    message = (
        "Authorization: Bearer PRIVATE_AUTH\nCookie: a=PRIVATE_COOKIE; b=PRIVATE_SECOND\n"
        "password=PRIVATE_PASSWORD https://bucket.example/x?X-Amz-Signature=PRIVATE_SIGNATURE "
        "https://api.telegram.org/file/botPRIVATE_BOT/x.apk "
        "http://user:PRIVATE_PROXY@proxy.example postgres://user:PRIVATE_DB@database/x"
    )
    output = SecretRedactingFormatter().format(
        logging.LogRecord("qa", logging.ERROR, "", 0, message, (), None)
    )
    for value in [
        "PRIVATE_AUTH",
        "PRIVATE_COOKIE",
        "PRIVATE_SECOND",
        "PRIVATE_PASSWORD",
        "PRIVATE_SIGNATURE",
        "PRIVATE_BOT",
        "PRIVATE_PROXY",
        "PRIVATE_DB",
    ]:
        assert value not in output
    assert redact("key=nonsecret")
    assert "PRIVATE_SECOND" not in redact('"Cookie": "a=PRIVATE_COOKIE; b=PRIVATE_SECOND"')


def test_config_repr_and_validation_errors_hide_credentials():
    from config.settings import Settings

    values = dict(
        BOT_TOKEN="PRIVATE_BOT",
        DATABASE_URL="postgres://user:PRIVATE_DB@localhost/db",
        IMGBB_API_KEY="PRIVATE_IMGBB",
        WEBSITE_STATS_TOKEN="PRIVATE_STATS",
    )
    settings_obj = Settings(_env_file=None, **values)
    for secret in values.values():
        assert secret not in repr(settings_obj)
    with pytest.raises(ValueError) as caught:
        Settings(_env_file=None, **values, FILES_CHANNEL_ID="PRIVATE_BAD_ID")
    assert "PRIVATE_BAD_ID" not in str(caught.value)


def test_schema_startup_contains_only_verification_for_postgresql():
    import re

    source = Path("database/database.py").read_text()
    assert "SELECT revision FROM applications LIMIT 0" in source
    assert "SELECT application_id FROM site_delivery_sources LIMIT 0" in source
    assert "run_sync(Base.metadata.create_all)" in source  # SQLite test/local-only branch
    # Historical guides had token-shaped examples. Keep samples opaque, never usable-looking.
    token = re.compile(r"(?<![0-9])[0-9]{8,12}:[A-Za-z0-9_-]{35}(?![A-Za-z0-9_-])")
    image_key = re.compile(r"IMGBB_API_KEY[ \t]*=[ \t]*[\x22\x27]?[a-fA-F0-9]{32}\b")
    for guide in [*Path('.').glob('*.md'), *Path('docs').rglob('*.md')]:
        assert not token.search(guide.read_text()), f"Token-shaped content in {guide.name}"
        assert not image_key.search(guide.read_text()), f"Key-shaped content in {guide.name}"


async def test_steamrip_size_fallback_rejects_redirect_before_contact(monkeypatch):
    from integrations import steamrip_metadata

    async def data(url):
        return {"page_url": url, "size": "—", "servers": {}}

    monkeypatch.setattr(steamrip_metadata, "_fetch_game_data", data)
    calls = install_http(monkeypatch, Response(302, {"Location": "http://169.254.169.254/latest"}))
    result = await steamrip_metadata.fetch_game_data("https://steamrip.com/qa")
    assert result["size"] == "—"
    assert calls == ["https://steamrip.com/qa"]


async def test_steamrip_size_fallback_retains_size_extraction(monkeypatch):
    from integrations import steamrip_metadata

    async def data(url):
        return {"page_url": url, "size": "—", "servers": {}}

    monkeypatch.setattr(steamrip_metadata, "_fetch_game_data", data)
    install_http(monkeypatch, Response(payload=b"<strong>File Size:</strong> 112.4 GB"))
    result = await steamrip_metadata.fetch_game_data("https://steamrip.com/qa")
    assert result["size"] == "112.4 GB"


async def test_fetch_total_deadline_covers_redirect_chain(monkeypatch):
    import asyncio

    class SlowRedirect(Response):
        async def __aenter__(self):
            await asyncio.sleep(0.03)
            return self

    calls = install_http(monkeypatch, SlowRedirect(302, {"Location": "/next"}))
    with pytest.raises(TimeoutError):
        await public_http.fetch_public_bytes("https://steamrip.com/qa", timeout=0.01)
    assert calls == ["https://steamrip.com/qa"]
