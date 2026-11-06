from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.handlers import admin


def _callback():
    return SimpleNamespace(
        answer=AsyncMock(),
        message=SimpleNamespace(edit_text=AsyncMock()),
    )


@pytest.mark.asyncio
async def test_archive_success_confirms_only_after_repository_success(monkeypatch):
    call = _callback()
    app = SimpleNamespace(active=True, published=True)
    monkeypatch.setattr(admin, "owner_gate", AsyncMock(return_value=True))
    monkeypatch.setattr(admin, "_guard", lambda _: True)
    monkeypatch.setattr(admin.repo, "get_application", AsyncMock(return_value=app))
    monkeypatch.setattr(admin.repo, "archive_application", AsyncMock(return_value=True))
    monkeypatch.setattr(admin.repo, "list_applications", AsyncMock(return_value=[]))

    await admin.on_delete_yes(
        call, SimpleNamespace(app_id=42, page=0), session=object()
    )

    call.answer.assert_awaited_once_with("🗑 تمت أرشفة التطبيق بنجاح.")
    edited_text = call.message.edit_text.await_args.args[0]
    assert "إدارة التطبيقات\n" in edited_text
    assert "\\n" not in edited_text


@pytest.mark.asyncio
async def test_archive_race_does_not_report_success_when_app_disappears(monkeypatch):
    call = _callback()
    app = SimpleNamespace(active=True, published=True)
    monkeypatch.setattr(admin, "owner_gate", AsyncMock(return_value=True))
    monkeypatch.setattr(admin, "_guard", lambda _: True)
    monkeypatch.setattr(admin.repo, "get_application", AsyncMock(return_value=app))
    monkeypatch.setattr(admin.repo, "archive_application", AsyncMock(return_value=False))
    list_apps = AsyncMock(return_value=[])
    monkeypatch.setattr(admin.repo, "list_applications", list_apps)

    await admin.on_delete_yes(
        call, SimpleNamespace(app_id=42, page=0), session=object()
    )

    call.answer.assert_awaited_once()
    assert call.answer.await_args.kwargs["show_alert"] is True
    assert "لم يعد التطبيق موجودًا" in call.answer.await_args.args[0]
    call.message.edit_text.assert_not_awaited()
    list_apps.assert_not_awaited()


@pytest.mark.asyncio
async def test_already_inactive_and_unpublished_app_is_not_archived_twice(monkeypatch):
    call = _callback()
    app = SimpleNamespace(active=False, published=False)
    monkeypatch.setattr(admin, "owner_gate", AsyncMock(return_value=True))
    monkeypatch.setattr(admin, "_guard", lambda _: True)
    monkeypatch.setattr(admin.repo, "get_application", AsyncMock(return_value=app))
    archive = AsyncMock(return_value=True)
    monkeypatch.setattr(admin.repo, "archive_application", archive)

    await admin.on_delete_yes(
        call, SimpleNamespace(app_id=42, page=0), session=object()
    )

    call.answer.assert_awaited_once()
    assert call.answer.await_args.kwargs["show_alert"] is True
    assert "بالفعل" in call.answer.await_args.args[0]
    archive.assert_not_awaited()
