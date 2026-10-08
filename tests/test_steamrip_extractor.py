from bs4 import BeautifulSoup

from integrations.steamrip_extractor import (
    _bzzhr_candidates,
    _direct_link_from_headers,
    _extract_game_image,
    _extract_signed_download_endpoint,
    _looks_like_cloudflare_challenge,
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


def test_cloudflare_solver_is_only_requested_for_real_challenge():
    challenge_html = "<title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/x'></script>"
    normal_html = '<a hx-get="/file-xyz/download?t=abc">Download</a>'

    assert _looks_like_cloudflare_challenge(403, challenge_html) is True
    assert _looks_like_cloudflare_challenge(200, normal_html) is False
    assert _looks_like_cloudflare_challenge(403, "Forbidden") is False


def test_game_image_uses_lazy_url_instead_of_data_placeholder():
    html = """
    <article>
      <div class="entry-content">
        <img
          src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
          data-lazy-src="https://steamrip.com/wp-content/uploads/game-cover.webp"
        >
      </div>
    </article>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert _extract_game_image(soup, "https://steamrip.com/example/") == (
        "https://steamrip.com/wp-content/uploads/game-cover.webp"
    )


def test_game_image_uses_largest_srcset_candidate():
    html = """
    <div class="entry-content">
      <img
        src="data:image/png;base64,placeholder"
        data-srcset="/small.jpg 300w, /medium.jpg 768w, /large.jpg 1280w"
      >
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert _extract_game_image(soup, "https://steamrip.com/example/") == (
        "https://steamrip.com/large.jpg"
    )


def test_game_image_falls_back_to_open_graph_image():
    html = """
    <html>
      <head>
        <meta property="og:image" content="https://cdn.example.com/game.jpg">
      </head>
      <body>
        <img src="data:image/png;base64,placeholder">
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert _extract_game_image(soup, "https://steamrip.com/example/") == (
        "https://cdn.example.com/game.jpg"
    )


def test_game_image_prefers_cover_over_screenshot_gallery():
    html = """
    <html>
      <head>
        <meta property="og:image" content="https://cdn.example.com/backrooms-cover.jpg">
      </head>
      <body>
        <article>
          <div class="entry-content">
            <h2>SCREENSHOTS</h2>
            <div class="wp-block-gallery screenshots">
              <img src="https://cdn.example.com/screenshot-1.jpg">
              <img src="https://cdn.example.com/screenshot-2.jpg">
            </div>
          </div>
        </article>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert _extract_game_image(soup, "https://steamrip.com/backrooms/") == (
        "https://cdn.example.com/backrooms-cover.jpg"
    )


def test_game_image_prefers_wordpress_featured_image_before_content_images():
    html = """
    <article>
      <div class="post-thumbnail">
        <img
          class="wp-post-image"
          src="data:image/png;base64,placeholder"
          data-lazy-src="https://cdn.example.com/hero.webp"
        >
      </div>
      <div class="entry-content">
        <img src="https://cdn.example.com/content-image.jpg">
      </div>
    </article>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert _extract_game_image(soup, "https://steamrip.com/example/") == (
        "https://cdn.example.com/hero.webp"
    )


def test_game_image_does_not_use_images_after_screenshots_heading():
    html = """
    <article>
      <div class="entry-content">
        <h2>SCREENSHOTS</h2>
        <img src="https://cdn.example.com/screenshot-only.jpg">
      </div>
    </article>
    """
    soup = BeautifulSoup(html, "html.parser")

    assert _extract_game_image(soup, "https://steamrip.com/example/") is None


def test_live_observed_ts_cdn_accepted_exactly():
    assert _direct_link_from_headers({'HX-Redirect': 'https://ts.buzzheavier.com/d/724hyjkckpyu?v=fixture'}, 'https://buzzheavier.com/724hyjkckpyu/download?t=x') == 'https://ts.buzzheavier.com/d/724hyjkckpyu?v=fixture'
    assert _direct_link_from_headers({'HX-Redirect': 'https://evil.buzzheavier.com/d/id?v=x'}, 'https://buzzheavier.com/id/download?t=x') is None


def test_declared_endpoint_uses_dynamic_path_and_query():
    assert _extract_signed_download_endpoint('<a hx-get="/file-xyz/preview?t=x"><button hx-get="/file-xyz/fetch?signature=x&amp;alt=true">', 'https://bzzhr.to/file-xyz') == 'https://bzzhr.to/file-xyz/fetch?signature=x&alt=true'


async def test_resolver_checks_final_headers_without_file_bytes(monkeypatch):
    from integrations import steamrip_extractor as extractor
    calls = []
    async def fetch(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            return b'<a hx-get="/file/fetch?sig=x">', 'text/html', url, {}, 200
        if len(calls) == 2:
            return b'', '', url, {'HX-Redirect': 'https://ts.buzzheavier.com/d/file?v=x'}, 204
        assert kwargs['method'] == 'HEAD'
        return b'', 'application/octet-stream', url, {}, 200
    monkeypatch.setattr(extractor, 'fetch_public_response', fetch)
    assert await extractor._resolve_candidate_fast('https://bzzhr.co/file') == 'https://ts.buzzheavier.com/d/file?v=x'
    assert len(calls) == 3
