from integrations.steamrip_extractor import (
    _bzzhr_candidates,
    _direct_link_from_headers,
    _extract_signed_download_endpoint,
    _normalize_url,
)


def test_normalize_protocol_relative_bzzhr_url():
    assert _normalize_url("//bzzhr.to/file123") == "https://bzzhr.to/file123"


def test_bzzhr_candidates_preserve_dynamic_file_path_and_query():
    candidates = _bzzhr_candidates("https://bzzhr.to/file-xyz?t=abc")

    assert candidates == [
        "https://bzzhr.to/file-xyz?t=abc",
        "https://bzzhr.co/file-xyz?t=abc",
        "https://buzzheavier.com/file-xyz?t=abc",
    ]


def test_signed_download_endpoint_is_taken_from_real_hx_get():
    html = """
    <a hx-get="/ignored/preview?t=abc">Preview</a>
    <a hx-get="/file-xyz/download?t=abc&amp;sig=123">Download File</a>
    """

    endpoint = _extract_signed_download_endpoint(
        html,
        "https://bzzhr.to/file-xyz",
    )

    assert endpoint == "https://bzzhr.to/file-xyz/download?t=abc&sig=123"


def test_external_hx_get_is_rejected():
    html = '<a hx-get="https://evil.example/file/download?t=abc">Download</a>'

    assert (
        _extract_signed_download_endpoint(
            html,
            "https://bzzhr.to/file-xyz",
        )
        is None
    )


def test_hx_redirect_direct_download_is_accepted():
    direct = _direct_link_from_headers(
        {"hx-redirect": "https://fafda.to/d/file-xyz?v=signed-token"},
        "https://bzzhr.co/file-xyz/download?t=abc&sig=123",
    )

    assert direct == "https://fafda.to/d/file-xyz?v=signed-token"


def test_page_url_is_not_mistaken_for_direct_download():
    direct = _direct_link_from_headers(
        {"hx-redirect": "https://bzzhr.to/file-xyz"},
        "https://bzzhr.to/file-xyz/download?t=abc&sig=123",
    )

    assert direct is None
