"""طبقة الوصول إلى البيانات (Repositories).

كل دالة تستقبل جلسة SQLAlchemy صراحةً — أسهل للاختبار والتحويل لقاعدة بيانات أخرى.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    AppRequest,
    Application,
    BannedWord,
    Download,
    Favorite,
    GroupLog,
    MemberWarning,
    SearchLog,
    Setting,
    User,
)


def _utc_start_of_today() -> datetime:
    """بداية اليوم الحالي بتوقيت UTC لاستخدامها في إحصائيات اليوم."""
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


# --------------------------------------------------------------------------
# Users
# --------------------------------------------------------------------------
async def get_user(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
) -> User:
    user = await get_user(session, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        session.add(user)
        await session.flush()
        return user
    if (username or "") != (user.username or "") or (first_name or "") != (
        user.first_name or ""
    ):
        user.username = username or user.username
        user.first_name = first_name or user.first_name
        user.last_name = last_name or user.last_name
        await session.flush()
    return user


async def set_user_notifications(
    session: AsyncSession, telegram_id: int, enabled: bool
) -> None:
    await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(notifications_enabled=enabled)
    )
    await session.flush()


async def count_users(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(User.id))) or 0


async def count_users_today(session: AsyncSession) -> int:
    since = _utc_start_of_today()
    return (
        await session.scalar(
            select(func.count(User.id)).where(User.created_at >= since)
        )
        or 0
    )


async def list_notification_users(session: AsyncSession) -> list[User]:
    return list(
        (
            await session.scalars(
                select(User).where(User.notifications_enabled.is_(True))
            )
        ).all()
    )


async def list_all_user_ids(session: AsyncSession) -> list[int]:
    return list((await session.scalars(select(User.telegram_id))).all())


# --------------------------------------------------------------------------
# Applications
# --------------------------------------------------------------------------
async def create_application(
    session: AsyncSession,
    *,
    name: str,
    description: str | None = None,
    version: str | None = None,
    size: str | None = None,
    category: str | None = None,
    platform: str | None = None,
    developer: str | None = None,
    image_url: str | None = None,
    icon_file_id: str | None = None,
    devupload_url: str | None = None,
    shrankme_url: str | None = None,
    search_text: str | None = None,
) -> Application:
    app = Application(
        name=name,
        description=description,
        version=version,
        size=size,
        category=category,
        platform=platform,
        developer=developer,
        icon_file_id=icon_file_id,
        image_url=image_url,
        devupload_url=devupload_url,
        shrankme_url=shrankme_url,
        search_text=search_text,
    )
    session.add(app)
    await session.flush()
    return app


async def get_application(session: AsyncSession, app_id: int) -> Application | None:
    return await session.get(Application, app_id)


async def get_active_application(
    session: AsyncSession, app_id: int
) -> Application | None:
    return await session.scalar(
        select(Application).where(Application.id == app_id, Application.active.is_(True))
    )


async def list_applications(
    session: AsyncSession, *, active_only: bool = True, limit: int = 200
) -> list[Application]:
    stmt = select(Application)
    if active_only:
        stmt = stmt.where(Application.active.is_(True))
    stmt = stmt.order_by(Application.created_at.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


async def list_latest(
    session: AsyncSession, *, limit: int = 50, offset: int = 0
) -> list[Application]:
    stmt = (
        select(Application)
        .where(Application.active.is_(True))
        .order_by(Application.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def list_by_category(
    session: AsyncSession, category: str, *, limit: int = 50, offset: int = 0
) -> list[Application]:
    stmt = (
        select(Application)
        .where(
            Application.active.is_(True),
            func.lower(Application.category) == category.lower(),
        )
        .order_by(Application.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def list_categories(session: AsyncSession) -> list[str]:
    rows = await session.execute(
        select(Application.category)
        .where(
            Application.active.is_(True),
            Application.category.is_not(None),
            Application.category != "",
        )
        .distinct()
        .order_by(Application.category)
    )
    return [r[0] for r in rows]


async def search_applications(
    session: AsyncSession, query: str, *, limit: int = 10
) -> list[Application]:
    q = f"%{query}%"
    stmt = (
        select(Application)
        .where(
            Application.active.is_(True),
            Application.search_text.is_not(None),
            Application.search_text.ilike(q),
        )
        .order_by(Application.downloads.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def update_application(session: AsyncSession, app: Application) -> None:
    await session.flush()


async def set_application_active(
    session: AsyncSession, app_id: int, active: bool
) -> None:
    await session.execute(
        update(Application).where(Application.id == app_id).values(active=active)
    )
    await session.flush()


async def delete_application(session: AsyncSession, app_id: int) -> None:
    # حذف السجلات التابعة أولًا لأن قاعدة البيانات الحالية لا تستخدم
    # ON DELETE CASCADE على downloads و favorites.
    await session.execute(delete(Download).where(Download.app_id == app_id))
    await session.execute(delete(Favorite).where(Favorite.app_id == app_id))
    await session.execute(delete(Application).where(Application.id == app_id))
    await session.flush()


async def increment_downloads(session: AsyncSession, app_id: int) -> None:
    await session.execute(
        update(Application)
        .where(Application.id == app_id)
        .values(downloads=Application.downloads + 1)
    )
    await session.flush()


async def increment_views(session: AsyncSession, app_id: int) -> None:
    await session.execute(
        update(Application)
        .where(Application.id == app_id)
        .values(views=Application.views + 1)
    )
    await session.flush()


async def count_applications(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(Application.id))) or 0


# --------------------------------------------------------------------------
# Downloads
# --------------------------------------------------------------------------
async def add_download(session: AsyncSession, user_id: int, app_id: int) -> None:
    session.add(Download(user_id=user_id, app_id=app_id))
    await session.flush()


async def count_downloads(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(Download.id))) or 0


async def count_downloads_today(session: AsyncSession) -> int:
    since = _utc_start_of_today()
    return (
        await session.scalar(
            select(func.count(Download.id)).where(Download.created_at >= since)
        )
        or 0
    )


# --------------------------------------------------------------------------
# App requests
# --------------------------------------------------------------------------
async def create_app_request(
    session: AsyncSession,
    user_id: int,
    app_name: str,
    username: str | None = None,
) -> AppRequest:
    req = AppRequest(user_id=user_id, username=username, app_name=app_name)
    session.add(req)
    await session.flush()
    return req


async def get_app_request(session: AsyncSession, req_id: int) -> AppRequest | None:
    return await session.get(AppRequest, req_id)


async def set_request_status(
    session: AsyncSession, req_id: int, status: str
) -> AppRequest | None:
    req = await session.get(AppRequest, req_id)
    if req is None:
        return None
    req.status = status
    req.resolved_at = datetime.now(timezone.utc)
    await session.flush()
    return req


async def list_requests(
    session: AsyncSession, status: str | None = None, *, limit: int = 20
) -> list[AppRequest]:
    stmt = select(AppRequest)
    if status:
        stmt = stmt.where(AppRequest.status == status)
    stmt = stmt.order_by(AppRequest.created_at.desc()).limit(limit)
    return list((await session.scalars(stmt)).all())


async def count_requests(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(AppRequest.id))) or 0


async def count_pending_requests(session: AsyncSession) -> int:
    return (
        await session.scalar(
            select(func.count(AppRequest.id)).where(AppRequest.status == "pending")
        )
        or 0
    )


# --------------------------------------------------------------------------
# Favorites
# --------------------------------------------------------------------------
async def add_favorite(session: AsyncSession, user_id: int, app_id: int) -> bool:
    """إضافة تطبيق للمفضلة. يعيد True عند الإضافة، False إذا كانت موجودة مسبقًا.

    لا نستخدم rollback داخل الدالة — أي خطأ في flush يجب أن يصل للمتصل
    ولا يمسح كتابات أخرى على نفس الجلسة.
    """
    exists = await session.scalar(
        select(Favorite.id).where(
            Favorite.user_id == user_id, Favorite.app_id == app_id
        )
    )
    if exists:
        return False
    session.add(Favorite(user_id=user_id, app_id=app_id))
    await session.flush()
    return True


async def remove_favorite(session: AsyncSession, user_id: int, app_id: int) -> None:
    await session.execute(
        delete(Favorite).where(
            Favorite.user_id == user_id, Favorite.app_id == app_id
        )
    )
    await session.flush()


async def is_favorite(session: AsyncSession, user_id: int, app_id: int) -> bool:
    exists = await session.scalar(
        select(Favorite.id).where(
            Favorite.user_id == user_id, Favorite.app_id == app_id
        )
    )
    return exists is not None


async def list_favorites(
    session: AsyncSession, user_id: int, *, limit: int = 50, offset: int = 0
) -> list[Application]:
    stmt = (
        select(Application)
        .join(Favorite, Favorite.app_id == Application.id)
        .where(
            Favorite.user_id == user_id,
            Application.active.is_(True),
        )
        .order_by(Favorite.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def count_favorites(session: AsyncSession, user_id: int) -> int:
    return (
        await session.scalar(
            select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
        )
        or 0
    )


# --------------------------------------------------------------------------
# Search logs
# --------------------------------------------------------------------------
async def log_search(
    session: AsyncSession, user_id: int, query: str, results: int
) -> None:
    session.add(SearchLog(user_id=user_id, query=query, results=results))
    await session.flush()


async def count_searches(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(SearchLog.id))) or 0


async def count_searches_today(session: AsyncSession) -> int:
    since = _utc_start_of_today()
    return (
        await session.scalar(
            select(func.count(SearchLog.id)).where(SearchLog.created_at >= since)
        )
        or 0
    )


# --------------------------------------------------------------------------
# Warnings
# --------------------------------------------------------------------------
async def get_warning(session: AsyncSession, chat_id: int, user_id: int) -> MemberWarning | None:
    return await session.scalar(
        select(MemberWarning).where(
            MemberWarning.chat_id == chat_id, MemberWarning.user_id == user_id
        )
    )


async def increment_warning(
    session: AsyncSession,
    chat_id: int,
    user_id: int,
    username: str | None = None,
    reason: str | None = None,
) -> MemberWarning:
    warn = await get_warning(session, chat_id, user_id)
    if warn is None:
        warn = MemberWarning(
            chat_id=chat_id, user_id=user_id, username=username, count=1, reason=reason
        )
        session.add(warn)
    else:
        warn.count += 1
        warn.username = username or warn.username
        warn.reason = reason or warn.reason
    await session.flush()
    return warn


async def clear_warnings(session: AsyncSession, chat_id: int, user_id: int) -> None:
    await session.execute(
        delete(MemberWarning).where(
            MemberWarning.chat_id == chat_id, MemberWarning.user_id == user_id
        )
    )
    await session.flush()


async def count_warnings(session: AsyncSession) -> int:
    return await session.scalar(select(func.count(MemberWarning.id))) or 0


# --------------------------------------------------------------------------
# Banned words
# --------------------------------------------------------------------------
async def list_banned_words(session: AsyncSession) -> list[str]:
    return list((await session.scalars(select(BannedWord.word))).all())


async def add_banned_word(session: AsyncSession, word: str) -> bool:
    word = word.strip().lower()
    exists = await session.scalar(
        select(BannedWord.id).where(BannedWord.word == word)
    )
    if exists:
        return False
    session.add(BannedWord(word=word))
    await session.flush()
    return True


async def remove_banned_word(session: AsyncSession, word: str) -> bool:
    word = word.strip().lower()
    result = await session.execute(
        delete(BannedWord).where(BannedWord.word == word)
    )
    await session.flush()
    return result.rowcount > 0


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    value = await session.scalar(select(Setting.value).where(Setting.key == key))
    return value if value is not None else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    await session.flush()


async def get_setting_bool(session: AsyncSession, key: str, default: bool = False) -> bool:
    raw = await get_setting(session, key)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


async def list_settings(session: AsyncSession) -> dict[str, str | None]:
    rows = await session.execute(select(Setting.key, Setting.value))
    return {key: value for key, value in rows}


# --------------------------------------------------------------------------
# Group logs
# --------------------------------------------------------------------------
async def add_group_log(
    session: AsyncSession,
    *,
    chat_id: int,
    user_id: int | None = None,
    username: str | None = None,
    action: str | None = None,
    detail: str | None = None,
) -> None:
    session.add(
        GroupLog(
            chat_id=chat_id,
            user_id=user_id,
            username=username,
            action=action,
            detail=detail,
        )
    )
    await session.flush()


async def recent_group_logs(
    session: AsyncSession, chat_id: int, *, limit: int = 10
) -> list[GroupLog]:
    stmt = (
        select(GroupLog)
        .where(GroupLog.chat_id == chat_id)
        .order_by(GroupLog.created_at.desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def count_group_logs(session: AsyncSession, chat_id: int) -> int:
    return (
        await session.scalar(
            select(func.count(GroupLog.id)).where(GroupLog.chat_id == chat_id)
        )
        or 0
    )
