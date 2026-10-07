from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import html
import re
import pytest
from app.utils.text import APP_DOWNLOAD_FOOTER, append_app_footer, app_card, final_download_message
from app.handlers.upload import channel_promo
from app.services import download_service as service
from integrations import steamrip_extractor as extractor
from database import repositories as repo


def visible_units(text):
    return len(html.unescape(re.sub(r"<[^>]+>", "", text)).encode("utf-16-le")) // 2


def app_fixture():
    return SimpleNamespace(id=123, name='<script>' + '🎮' * 300, version='<' * 100,
        size='>' * 100, platform='Windows', category='ألعاب كمبيوتر', developer='&' * 300,
        downloads=5, description='📱<&>' * 4000, image_url=None, icon_file_id=None)


@pytest.mark.parametrize('url', ['https://waleed-zone.up.railway.app/download/123',
    'https://fafda.to/d/file?v=fixture-token', 'https://shrinkme.io/file'])
def test_final_download_footer_safe_once(url):
    text = final_download_message(app_fixture(), url)
    assert text.count(APP_DOWNLOAD_FOOTER) == 1
    assert text.count('@Waleedzone_bot') == 1
    assert append_app_footer(text) == text
    assert '<script>' not in text
    assert visible_units(text) <= 4096
    assert url.replace('&', '&amp;') in text


def test_card_and_channel_caption_limits_with_emoji_and_html():
    app = app_fixture()
    card = app_card(app)
    promo, _ = channel_promo(app)
    assert card.count(APP_DOWNLOAD_FOOTER) == promo.count(APP_DOWNLOAD_FOOTER) == 1
    assert visible_units(card) <= 4096
    assert visible_units(promo) <= 1024
    assert '/download/123' in promo
    assert '<script>' not in card + promo
    assert '<&>' not in card + promo


@pytest.mark.parametrize('url', ['https://evil.test/d/a?v=x', 'https://127.0.0.1/d/a?v=x',
    'https://fafda.to/d/a', 'https://fafda.to/d/a?v=x\r\nBad: a', 'http://fafda.to/d/a?v=x'])
def test_direct_header_host_policy_fail_closed(url):
    assert extractor._direct_link_from_headers({'HX-Redirect': url}, 'https://bzzhr.to/a/download?t=abc') is None


async def test_http_only_resolver_deduplicates_and_caps(monkeypatch):
    extractor._BZZHR_INFLIGHT.clear()
    monkeypatch.setattr(extractor, '_BZZHR_BACKOFF_UNTIL', 0)
    gate = asyncio.Event()
    calls = []
    async def resolve(url, referer):
        calls.append(url)
        await gate.wait()
        return 'https://fafda.to/d/a?v=fixture'
    monkeypatch.setattr(extractor, '_resolve_candidate_fast', resolve)
    tasks = [asyncio.create_task(extractor.extract_bzzhr_direct_link('https://bzzhr.to/a')) for _ in range(2)]
    tasks.append(asyncio.create_task(extractor.extract_bzzhr_direct_link('https://bzzhr.to/b')))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert len(calls) == 2
    assert await extractor.extract_bzzhr_direct_link('https://bzzhr.to/c') is None
    gate.set()
    assert all(await asyncio.gather(*tasks))
    assert not extractor._BZZHR_INFLIGHT
    await extractor.extract_bzzhr_direct_link('https://bzzhr.to/a')
    assert len(calls) == 3  # completed signed link is never cached


async def test_no_transaction_during_fetch_and_source_edit_rejected(db, monkeypatch):
    async with db.session() as session:
        app = await repo.create_application(session, name='Source race', devupload_url='https://steamrip.com/qa/')
        app.published = True
        await session.commit()
        async def fetch(url):
            assert not session.in_transaction()
            async with db.session() as editor:
                row = await repo.get_application(editor, app.id)
                row.devupload_url = 'https://steamrip.com/changed/'
                await editor.commit()
            return {'servers': {'BZZHR': 'https://bzzhr.to/a'}}
        monkeypatch.setattr(service, 'fetch_game_data', fetch)
        monkeypatch.setattr(service, 'extract_bzzhr_direct_link', AsyncMock(return_value='https://fafda.to/d/a?v=x'))
        with pytest.raises(ValueError, match='SOURCE_CHANGED'):
            await service.resolve_application_download(session, app.id)


async def test_two_handlers_use_same_duplicate_callback_guard(monkeypatch):
    gate = asyncio.Event()
    async def resolve(session, app_id):
        await gate.wait()
        return SimpleNamespace(id=1, name='QA', size='1MB'), 'https://waleed-zone.up.railway.app/download/1', 'telegram'
    monkeypatch.setattr(service, 'resolve_application_download', resolve)
    call = SimpleNamespace(from_user=SimpleNamespace(id=8), answer=AsyncMock(), message=SimpleNamespace(answer=AsyncMock(), edit_text=AsyncMock()))
    session = SimpleNamespace(rollback=AsyncMock())
    first = asyncio.create_task(service.send_application_download(call, session, 1))
    await asyncio.sleep(0)
    await service.send_application_download(call, session, 1, edit=True)
    gate.set()
    await first
    call.message.answer.assert_awaited_once()
    call.message.edit_text.assert_not_awaited()


def test_no_browser_challenge_bypass_remains():
    from pathlib import Path
    text = Path('integrations/steamrip_extractor.py').read_text()
    assert 'solve_cloudflare=True' not in text
    assert 'StealthySession' not in text
    assert '_configured_proxy' not in text
