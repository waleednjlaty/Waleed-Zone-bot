from types import SimpleNamespace

import pytest

from app.handlers import upload
from app.keyboards.admin import admin_panel_keyboard


def _settings(hosts: str):
    return SimpleNamespace(LEGACY_DOWNLOAD_ALLOWED_HOSTS=hosts)


def test_admin_panel_has_manual_link_option():
    keyboard = admin_panel_keyboard()
    labels = [button.text for row in keyboard.inline_keyboard for button in row]
    assert "🔗 إضافة برابط" in labels


def test_manual_download_url_accepts_allowed_https(monkeypatch):
    monkeypatch.setattr(
        upload,
        "get_settings",
        lambda: _settings("files.example.com, cdn.example.com"),
    )
    assert (
        upload._validate_manual_download_url(
            "https://files.example.com/releases/game.zip?token=abc"
        )
        == "https://files.example.com/releases/game.zip?token=abc"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://files.example.com/game.zip",
        "https://user:pass@files.example.com/game.zip",
        "https://files.example.com:444/game.zip",
        "https://files.example.com/game.zip#fragment",
        "https://evil.example/game.zip",
        "https://files.example.com/game zip",
        "file:///tmp/game.zip",
    ],
)
def test_manual_download_url_rejects_unsafe_or_unlisted_urls(monkeypatch, url):
    monkeypatch.setattr(
        upload,
        "get_settings",
        lambda: _settings("files.example.com,cdn.example.com"),
    )
    with pytest.raises(ValueError):
        upload._validate_manual_download_url(url)
