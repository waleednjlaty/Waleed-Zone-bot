"""إعدادات الاختبارات — تُضبط المتغيرات البيئية قبل استيراد أي وحدة من التطبيق."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio

# جذر المشروع في مسار الاستيراد
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

_TMP = tempfile.mkdtemp(prefix="waleed_bot_test_")

os.environ.setdefault("BOT_TOKEN", "123456:TEST-TOKEN")
os.environ.setdefault("ADMIN_IDS", "111,222")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{Path(_TMP) / 'test.db'}")
os.environ.setdefault("DEVUPLOAD_API_KEY", "test_devupload_key")
os.environ.setdefault("SHRANKME_API_KEY", "test_shrankme_key")


@pytest.fixture()
def mock_httpx(monkeypatch):
    """تثبيت httpx.MockTransport لاختبار العملاء دون اتصال حقيقي."""

    def _install(handler):
        import httpx

        transport = httpx.MockTransport(handler)
        original_async_client = httpx.AsyncClient
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kw: original_async_client(transport=transport, **kw),
        )
        return transport

    return _install


@pytest_asyncio.fixture()
async def db():
    """قاعدة بيانات SQLite مؤقتة لجلسة الاختبار."""
    from config import get_settings
    from database.database import Database

    database = Database(get_settings().DATABASE_URL)
    await database.init_models()
    yield database
    await database.close()
