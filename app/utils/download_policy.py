"""Policy for download providers that are no longer supported by Waleed Zone."""

_BLOCKED_DOWNLOAD_PROVIDER_DOMAINS = frozenset({
    "shrinkme.io",
    "shrinkme.click",
    "shrinkme.net",
    "shrinkme.org",
    "shrinkme.site",
    "devuploads.com",
    "devupload.com",
})


def is_blocked_download_provider_host(host: str | None) -> bool:
    """Return True for ShrinkMe / DevUploads domains, including their subdomains."""
    normalized = (host or "").strip().lower().rstrip(".")
    if not normalized:
        return False
    return any(
        normalized == domain or normalized.endswith("." + domain)
        for domain in _BLOCKED_DOWNLOAD_PROVIDER_DOMAINS
    )


def is_blocked_download_provider_url(value: str) -> bool:
    """Check a URL without following it or making any network request."""
    from urllib.parse import urlsplit

    try:
        host = urlsplit(value).hostname
    except ValueError:
        return False
    return is_blocked_download_provider_host(host)
