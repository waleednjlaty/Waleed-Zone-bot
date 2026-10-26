from types import SimpleNamespace

import pytest

from app.handlers import remote_import


def configure_hosts(monkeypatch, hosts="downloads.example.com"):
    monkeypatch.setattr(
        remote_import,
        "get_settings",
        lambda: SimpleNamespace(
            REMOTE_UPLOAD_ALLOWED_HOSTS=hosts,
            LEGACY_DOWNLOAD_ALLOWED_HOSTS="legacy.example.com",
        ),
    )


def test_remote_import_accepts_allowlisted_signed_direct_file_url(monkeypatch):
    configure_hosts(monkeypatch)
    url = "https://downloads.example.com/CapCut_19.8.0.apk?signature=temporary"
    parsed_url, filename = remote_import._parse_url(url)
    assert parsed_url == url
    assert filename == "CapCut_19.8.0.apk"


@pytest.mark.parametrize(
    "url",
    [
        "http://downloads.example.com/app.apk",
        "https://downloads.example.com:8443/app.apk",
        "https://user:password@downloads.example.com/app.apk",
        "https://downloads.example.com/app.apk#fragment",
        "https://downloads.example.com/login.html",
        "https://not-downloads.example.com/app.apk",
    ],
)
def test_remote_import_rejects_unsafe_or_non_file_urls(monkeypatch, url):
    configure_hosts(monkeypatch)
    with pytest.raises(ValueError):
        remote_import._parse_url(url)


def test_remote_import_uses_legacy_allowlist_only_when_remote_list_is_blank(monkeypatch):
    configure_hosts(monkeypatch, hosts="")
    assert remote_import._parse_url("https://legacy.example.com/file.zip")[1] == "file.zip"
    with pytest.raises(ValueError, match="HOST_NOT_ALLOWED"):
        remote_import._parse_url("https://downloads.example.com/file.zip")
