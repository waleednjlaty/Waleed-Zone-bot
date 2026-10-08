"""Regression contracts from the authorized live 2026-10-08 canary handoffs."""
from unittest.mock import AsyncMock
import pytest
from integrations import steamrip_extractor as e
from app.services.download_service import manual_url


@pytest.mark.parametrize('host', ['ts.bzzhr.co', 'ts.buzzheavier.com', 'fafda.to'])
def test_exact_observed_cdn_host(host):
    assert e._looks_like_direct_download(f'https://{host}/d/file?v=fresh')
    assert not e._looks_like_direct_download(f'https://evil.{host}/d/file?v=fresh')


def test_no_synthetic_mirror_namespace():
    assert e._bzzhr_candidates('https://bzzhr.to/file') == ['https://bzzhr.to/file']


def test_dynamic_advertised_actions_and_mirror_order():
    page = 'https://bzzhr.co/file'
    html = '''<button class="download-btn" data-hx-get="/file/transfer?t=new&amp;sig=x">Get</button>
    <a hx-get="/file/download?t=new&amp;alt=true">Mirror</a><a hx-get="/file/preview?t=new">Preview</a>'''
    assert e._extract_signed_download_endpoints(html, page) == [
        page + '/transfer?t=new&sig=x', page + '/download?t=new&alt=true']


@pytest.mark.parametrize('html', ['<title>Just a moment...</title>', '<div class="cf-turnstile" data-sitekey="x"></div>'])
def test_challenge_even_with_200(html):
    assert e._looks_like_cloudflare_challenge(200, html)


def test_shared_turnstile_script_is_not_a_challenge():
    assert not e._looks_like_cloudflare_challenge(200,
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js"></script>')


@pytest.mark.parametrize('host', ['bzzhr.to', 'bzzhr.co', 'buzzheavier.com'])
def test_manual_input_accepts_stable_source_never_signed_url(host):
    assert manual_url(f'https://{host}/file', set()) == f'https://{host}/file'
    with pytest.raises(ValueError):
        manual_url(f'https://{host}/file/download?t=secret', set())


async def test_htmx_cookie_context_head_probe_and_advertised_alternate(monkeypatch):
    page = 'https://bzzhr.co/file'
    final = 'https://ts.bzzhr.co/d/file?v=fresh'
    calls = []
    async def transport(url, **kwargs):
        calls.append((url, kwargs))
        if url == page:
            return (b'<a hx-get="/file/download?t=fresh">Get</a><a hx-get="/file/download?t=fresh&amp;alt=true">Mirror</a>',
                'text/html', page, {'Set-Cookie': ['session=a; Path=/', 'second=b; Path=/']}, 200)
        if url == page + '/download?t=fresh':
            return b'Unavailable', 'text/html', url, {}, 503
        if url.endswith('alt=true'):
            assert kwargs['headers']['Cookie'] == 'session=a; second=b'
            assert kwargs['headers']['HX-Request'] == 'true'
            assert kwargs['headers']['Referer'] == page
            assert kwargs['follow'] is False
            return b'', '', url, {'HX-Redirect': final}, 204
        assert url == final
        assert kwargs['method'] == 'HEAD' and kwargs['headers_only']
        assert 'cookie_jar' not in kwargs
        return b'', 'application/octet-stream', final, {'Content-Disposition': 'attachment; filename=canary'}, 200
    monkeypatch.setattr(e, 'fetch_public_response', transport)
    assert await e._resolve_candidate_fast(page) == final
    assert len(calls) == 4


@pytest.mark.parametrize('status,code', [(404,'SOURCE_REMOVED'),(410,'SOURCE_REMOVED'),(403,'PROVIDER_FORBIDDEN'),(429,'PROVIDER_RATE_LIMITED')])
async def test_safe_stage_status_diagnostics(monkeypatch, status, code):
    page = 'https://bzzhr.co/file'
    monkeypatch.setattr(e, 'fetch_public_response', AsyncMock(return_value=(b'Failed', 'text/html', page, {}, status)))
    with pytest.raises(e.ProviderResolutionError) as caught:
        await e._resolve_candidate_fast(page)
    assert (caught.value.code, caught.value.stage, caught.value.host, caught.value.status) == (code, 'bzzhr_page', 'bzzhr.co', status)


async def test_head_html_is_not_file_success(monkeypatch):
    final = 'https://ts.bzzhr.co/d/file?v=secret'
    monkeypatch.setattr(e, 'fetch_public_response', AsyncMock(return_value=(b'', 'text/html', final, {}, 200)))
    with pytest.raises(e.ProviderResolutionError, match='FINAL_DESTINATION_NOT_FILE') as caught:
        await e._validate_file(final)
    assert caught.value.stage == 'file_probe'
    assert 'secret' not in str(caught.value)
