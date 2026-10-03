from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from pathlib import Path
import pytest
from sqlalchemy.orm.exc import StaleDataError
from app.services.upload_service import files_channel, UploadService, validate_source
from app.utils.website import website_download_url
from database import repositories as repo


def settings(**kwargs):
    return SimpleNamespace(FILES_CHANNEL_ID=kwargs.get('fid'),FILES_CHANNEL_USERNAME=kwargs.get('fname'),CHANNEL_ID=-1001,CHANNEL_USERNAME='main_channel',MAX_UPLOAD_BYTES=1000)


def source():
    return dict(telegram_chat_id=-1001,telegram_message_id=42,telegram_channel_username='main_channel',telegram_file_id='FILE_TEST',filename='qa.apk',size_bytes=24,mime_type='application/vnd.android.package-archive')


def test_download_url_stable():
    assert website_download_url(123)=='https://waleed-zone.up.railway.app/download/123'
    assert website_download_url(0) is None
    assert website_download_url(123,'https://example.test/evil') is None


def test_files_channel_safe_fallback():
    assert files_channel(settings())==(-1001,'main_channel')
    assert files_channel(settings(fid=-1002,fname='@FILES_channel'))==(-1002,'files_channel')
    assert files_channel(settings(fname='files_channel'))==(None,'files_channel')


@pytest.mark.parametrize('s',[settings(fid=-1002),settings(fid=1,fname='files_channel'),settings(fid=-1002,fname='bad/url')])
def test_files_channel_partial_or_invalid_rejected(s):
    with pytest.raises(ValueError): files_channel(s)


@pytest.mark.parametrize('value',[0,-1,1.5,True,2147483648,'42'])
def test_invalid_message_id(value):
    metadata=source();metadata['telegram_message_id']=value
    with pytest.raises(ValueError): validate_source(metadata)


@pytest.mark.parametrize('value',['a','bad/channel','https://t.me/channel','channel?token=x','channel#x'])
def test_invalid_channel(value):
    metadata=source();metadata['telegram_channel_username']=value
    with pytest.raises(ValueError): validate_source(metadata)


def incoming(user=111,username='main_channel'):
    bot=SimpleNamespace(get_chat=AsyncMock(return_value=SimpleNamespace(id=-1001,type='channel',username=username,has_protected_content=False)),copy_message=AsyncMock(return_value=SimpleNamespace(message_id=42)),download=AsyncMock(),get_file=AsyncMock())
    return SimpleNamespace(from_user=SimpleNamespace(id=user),bot=bot,chat=SimpleNamespace(id=111),message_id=7,document=SimpleNamespace(file_id='FILE_TEST',file_name='qa.apk',file_size=24,mime_type='application/vnd.android.package-archive'),answer=AsyncMock())


async def test_copy_uses_only_telegram_message_api(monkeypatch):
    monkeypatch.setattr('app.services.upload_service.get_settings',lambda:settings())
    message=incoming(); metadata=await UploadService().copy(message)
    assert metadata==source()
    message.bot.copy_message.assert_awaited_once_with(chat_id=-1001,from_chat_id=111,message_id=7,caption='',disable_notification=True)
    message.bot.download.assert_not_called();message.bot.get_file.assert_not_called()


async def test_copy_resolves_files_channel_id_from_username(monkeypatch):
    monkeypatch.setattr('app.services.upload_service.get_settings',lambda:settings(fname='main_channel'))
    message=incoming()
    metadata=await UploadService().copy(message)
    message.bot.get_chat.assert_awaited_once_with('@main_channel')
    assert metadata['telegram_chat_id']==-1001
    message.bot.copy_message.assert_awaited_once_with(chat_id=-1001,from_chat_id=111,message_id=7,caption='',disable_notification=True)


async def test_non_admin_upload_denied(monkeypatch):
    monkeypatch.setattr('app.services.upload_service.get_settings',lambda:settings())
    message=incoming(user=999)
    with pytest.raises(PermissionError): await UploadService().copy(message)
    message.bot.copy_message.assert_not_called()


async def test_channel_id_username_mismatch_denied(monkeypatch):
    monkeypatch.setattr('app.services.upload_service.get_settings',lambda:settings())
    message=incoming(username='other_channel')
    with pytest.raises(ValueError): await UploadService().copy(message)
    message.bot.copy_message.assert_not_called()


async def test_protected_channel_denied(monkeypatch):
    monkeypatch.setattr('app.services.upload_service.get_settings',lambda:settings())
    message=incoming();message.bot.get_chat.return_value.has_protected_content=True
    with pytest.raises(ValueError): await UploadService().copy(message)
    message.bot.copy_message.assert_not_called()


async def test_website_created_app_attachment(db):
    from app.handlers.upload import on_attach_file,on_file
    from app.utils.constants import AdminCB
    async with db.session() as session:
        app=await repo.create_application(session,name='Site Created',description='shared catalog')
        await session.commit()
        call=SimpleNamespace(from_user=SimpleNamespace(id=111),answer=AsyncMock(),message=SimpleNamespace(answer=AsyncMock()))
        state=SimpleNamespace(clear=AsyncMock(),update_data=AsyncMock(),set_state=AsyncMock(),get_data=AsyncMock())
        await on_attach_file(call,AdminCB(action='attach_file',app_id=app.id,page=0),state,session)
        state.get_data.return_value=state.update_data.call_args.kwargs
        message=incoming()
        with patch('app.services.upload_service.get_settings',lambda:settings()): await on_file(message,state,session)
        bound=await repo.get_delivery_source(session,app.id)
        assert bound.telegram_message_id==42 and bound.filename=='qa.apk'
        assert app.published is False
        assert app.devupload_url is None and app.shrankme_url is None


async def test_bot_admin_sees_draft_but_public_does_not(db):
    async with db.session() as session:
        app=await repo.create_application(session,name='Hidden Site Draft')
        assert any(a.id==app.id for a in await repo.list_applications(session,active_only=False,public_only=False))
        assert not any(a.id==app.id for a in await repo.list_applications(session))
        assert await repo.get_active_application(session,app.id) is None
        app.published=True;await session.flush()
        assert (await repo.get_active_application(session,app.id)).id==app.id
        app.active=False;await session.flush()
        assert await repo.get_active_application(session,app.id) is None


async def test_attachment_stale_revision_denied(db):
    async with db.session() as session:
        app=await repo.create_application(session,name='Revision App')
        old=app.revision;app.version='changed';await session.flush()
        with pytest.raises(StaleDataError): await repo.bind_telegram_source(session,app.id,source(),expected_revision=old)
        assert await repo.get_delivery_source(session,app.id) is None


def test_channel_publishing_download_cta_is_website():
    from app.handlers.upload import channel_promo
    app=SimpleNamespace(id=123,name='App',version='1',size='24 B',description='Test')
    text,kb=channel_promo(app)
    assert kb.inline_keyboard[0][0].text=='🌐 تحميل من Waleed Zone'
    assert kb.inline_keyboard[0][0].url=='https://waleed-zone.up.railway.app/download/123'
    assert 'devuploads' not in text and 'shrinkme' not in text and 't.me/' not in text


async def test_non_admin_router_middleware_denies_all_mutations():
    from app.handlers.upload import OwnerUploadMiddleware
    event=SimpleNamespace(from_user=SimpleNamespace(id=999),answer=AsyncMock());handler=AsyncMock()
    await OwnerUploadMiddleware()(handler,event,{})
    handler.assert_not_awaited();event.answer.assert_awaited()


def test_no_devuploads_or_shrinkme_runtime_imports():
    for path in list(Path('app').rglob('*.py'))+[Path('main.py')]:
        text=path.read_text()
        assert 'integrations.devupload' not in text and 'integrations.shrankme' not in text
        assert 'build_devupload_client' not in text and 'build_shrankme_client' not in text
    from config.settings import Settings
    assert 'DEVUPLOAD_API_KEY' not in Settings.model_fields and 'SHRANKME_API_KEY' not in Settings.model_fields


async def test_steamrip_download_regression(db,monkeypatch):
    from app.handlers.applications import on_download
    from app.utils.constants import AppCB
    fetch=AsyncMock(return_value={'servers':{'BZZHR':'https://buzzheavier.com/test'}})
    extract=AsyncMock(return_value='https://dl.buzzheavier.com/test')
    monkeypatch.setattr('app.handlers.applications.fetch_game_data',fetch)
    monkeypatch.setattr('app.handlers.applications.extract_bzzhr_direct_link',extract)
    async with db.session() as session:
        await repo.get_or_create_user(session,111)
        app=await repo.create_application(session,name='Steam QA',devupload_url='https://steamrip.com/qa-game/',category='ألعاب كمبيوتر',platform='Windows')
        app.published=True;await session.flush()
        status=SimpleNamespace(edit_text=AsyncMock())
        call=SimpleNamespace(from_user=SimpleNamespace(id=111),answer=AsyncMock(),message=SimpleNamespace(answer=AsyncMock(return_value=status)))
        await on_download(call,AppCB(action='download',app_id=app.id),session)
        fetch.assert_awaited_once_with('https://steamrip.com/qa-game/');extract.assert_awaited_once()
        assert 'https://dl.buzzheavier.com/test' in status.edit_text.call_args.args[0]


def test_logs_redact_tokens_file_urls_and_db_credentials():
    import logging
    from app.utils.logging_config import SecretRedactingFormatter
    from config import get_settings
    settings = get_settings()
    message = f"{settings.BOT_TOKEN} {settings.DATABASE_URL} https://api.telegram.org/file/botOTHER_TOKEN/secret.apk postgres://user:password@db/private"
    rendered = SecretRedactingFormatter().format(logging.LogRecord("qa",logging.ERROR,"",0,message,(),None))
    assert settings.BOT_TOKEN not in rendered
    assert settings.DATABASE_URL not in rendered
    assert "OTHER_TOKEN" not in rendered and "password@db" not in rendered
