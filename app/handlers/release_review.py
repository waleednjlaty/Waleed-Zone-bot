"""Owner-only, confirm-before-write app version review flow."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.services.catalog_ai import normalize_platform, suggest_application_groups
from app.utils.constants import AdminCB
from app.utils.helpers import build_search_text, is_admin
from app.utils.owner_guard import owner_gate
from app.utils.text import escape_html
from config import get_settings
from database import repositories as repo

router = Router(name="release_review")


async def _show_review(call: CallbackQuery, state: FSMContext, index: int) -> None:
    data = await state.get_data()
    groups = data.get("release_groups") or []
    provider = data.get("release_provider") or "heuristic"
    scanned = int(data.get("release_scanned") or 0)
    if index >= len(groups):
        text = (
            "✅ انتهت مراجعة الاقتراحات المعروضة.\n"
            "لم يتم تعديل أي سجل إلا المجموعات التي وافقت عليها صراحةً.\n"
            "يمكنك إعادة الفحص للعثور على اقتراحات أخرى."
            if groups else
            "✅ لا توجد مجموعات تحتاج مراجعة حاليًا.\nلم يتم تعديل أي تطبيق تلقائيًا."
        )
        await call.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 إعادة فحص الكتالوج", callback_data=AdminCB(action="release_review", page=0).pack())],
                [InlineKeyboardButton(text="⚙️ لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())],
            ]),
        )
        return

    group = groups[index]
    items = group.get("items") or []
    lines = [
        "🤖 مراجعة ذكية للإصدارات",
        "────────────────────",
        f"مصدر الاقتراح: {'OpenAI' if provider == 'openai' else 'مطابقة الأسماء الاحتياطية'}",
        f"تم فحص {scanned} سجلًا · الاقتراح {index + 1} من {len(groups)}",
        "",
        f"هل هذه السجلات للتطبيق نفسه؟ الاسم المقترح: <b>{escape_html(group.get('canonical_name') or '')}</b>",
        f"الثقة التقريبية: {round(float(group.get('confidence') or 0) * 100)}%",
        escape_html(str(group.get("reason") or "")),
        "",
        "الإصدارات المراد جمعها:",
    ]
    for item in items:
        current_version = item.get("version")
        suggested_version = item.get("version_suggestion")
        version_label = current_version or suggested_version or "إصدار غير محدد"
        suffix = f" · سيتم استخراج {version_label}" if not current_version and suggested_version else ""
        lines.append(
            f"• {escape_html(str(item.get('name') or ''))} — {escape_html(str(version_label))}"
            f" · {escape_html(str(item.get('platform') or 'نظام غير محدد'))} · #{int(item.get('id') or 0)}"
            f"{escape_html(suffix)}"
        )
    lines += [
        "",
        "بعد الموافقة: يوحّد الاسم، وينقل رقمًا من الاسم إلى حقل الإصدار فقط إذا كان الحقل فارغًا.",
        "تبقى ملفات وروابط التنزيل لكل إصدار مستقلة. لا يحدث أي تغيير قبل ضغط زر الموافقة.",
    ]
    await call.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ نعم، اجمع هذه الإصدارات", callback_data=AdminCB(action="release_accept", page=index).pack()),
                InlineKeyboardButton(text="❌ تطبيقات مختلفة", callback_data=AdminCB(action="release_skip", page=index).pack()),
            ],
            [InlineKeyboardButton(text="➡️ تخطي إلى الاقتراح التالي", callback_data=AdminCB(action="release_next", page=index).pack())],
            [InlineKeyboardButton(text="🔄 إعادة الفحص", callback_data=AdminCB(action="release_review", page=0).pack())],
            [InlineKeyboardButton(text="⚙️ لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())],
        ]),
        parse_mode="HTML",
    )


@router.callback_query(AdminCB.filter(F.action == "release_review"))
async def on_release_review(call: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if not await owner_gate(call):
        return
    if not call.from_user or not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    await call.answer("جارٍ فحص الكتالوج…")
    apps = await repo.list_applications(session, active_only=False, public_only=False, limit=1000)
    settings = get_settings()
    result = await suggest_application_groups(apps, settings.OPENAI_API_KEY, settings.CATALOG_AI_MODEL)
    await state.clear()
    await state.update_data(
        release_groups=result["groups"],
        release_provider=result["provider"],
        release_scanned=result["scanned"],
    )
    await _show_review(call, state, 0)


@router.callback_query(AdminCB.filter(F.action.in_({"release_next", "release_skip"})))
async def on_release_review_next(call: CallbackQuery, callback_data: AdminCB, state: FSMContext) -> None:
    if not await owner_gate(call):
        return
    if not call.from_user or not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    data = await state.get_data()
    groups = data.get("release_groups") or []
    if callback_data.page < 0 or callback_data.page >= len(groups):
        await call.answer("انتهت صلاحية هذا الاقتراح. أعد الفحص.", show_alert=True)
        return
    await call.answer("تم التخطي دون تعديل.")
    await _show_review(call, state, callback_data.page + 1)


@router.callback_query(AdminCB.filter(F.action == "release_accept"))
async def on_release_review_accept(
    call: CallbackQuery, callback_data: AdminCB, state: FSMContext, session: AsyncSession
) -> None:
    if not await owner_gate(call):
        return
    if not call.from_user or not is_admin(call.from_user.id):
        await call.answer("⛔ صلاحية غير متاحة.", show_alert=True)
        return
    data = await state.get_data()
    groups = data.get("release_groups") or []
    index = callback_data.page
    if index < 0 or index >= len(groups):
        await call.answer("انتهت صلاحية هذا الاقتراح. أعد الفحص.", show_alert=True)
        return
    group = groups[index]
    canonical_name = str(group.get("canonical_name") or "").strip()
    items = group.get("items") or []
    if not canonical_name or len(canonical_name) > 255 or len(items) < 2 or len(items) > 20:
        await call.answer("الاقتراح غير صالح. أعد الفحص.", show_alert=True)
        return

    records = []
    try:
        for item in items:
            app = await repo.get_application(session, int(item["id"]))
            if app is None or app.revision != int(item["revision"]):
                raise ValueError("STALE_RELEASE_REVIEW")
            if normalize_platform(app.platform) != normalize_platform(item.get("platform")):
                raise ValueError("PLATFORM_CHANGED")
            records.append((app, item))

        versions = {
            str(app.version).strip().casefold()
            for app, _ in records
            if app.version and str(app.version).strip()
        }
        transferred = 0
        for app, item in records:
            app.name = canonical_name
            if not app.version:
                candidate_version = item.get("version_suggestion")
                if candidate_version and str(candidate_version).casefold() not in versions:
                    app.version = str(candidate_version)
                    versions.add(str(candidate_version).casefold())
                    transferred += 1
            app.search_text = build_search_text(app.name, app.category, app.platform, app.description)
            await repo.update_application(session, app)
        await session.commit()
    except (ValueError, StaleDataError):
        await session.rollback()
        await call.answer("تغيّرت بيانات أحد السجلات أو تعارض الإصدار. لم تُحفظ المجموعة؛ أعد الفحص.", show_alert=True)
        return
    except Exception:
        await session.rollback()
        await call.answer("تعذر تطبيق الاقتراح بأمان. لم تُحفظ المجموعة؛ أعد الفحص.", show_alert=True)
        return

    await call.answer("✅ تم الحفظ بعد موافقتك.")
    await call.message.edit_text(
        f"✅ جمعت {len(records)} سجلات تحت اسم <b>{escape_html(canonical_name)}</b>."
        f"\nتم استخراج {transferred} رقم إصدار من الأسماء الفارغة."
        "\nملفات التنزيل والمصادر لكل سجل بقيت كما هي.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➡️ مراجعة الاقتراح التالي", callback_data=AdminCB(action="release_next", page=index).pack())],
            [InlineKeyboardButton(text="🔄 إعادة الفحص", callback_data=AdminCB(action="release_review", page=0).pack())],
            [InlineKeyboardButton(text="⚙️ لوحة الإدارة", callback_data=AdminCB(action="panel", page=0).pack())],
        ]),
        parse_mode="HTML",
    )
