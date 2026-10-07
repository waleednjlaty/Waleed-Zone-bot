"""تنسيقات النصوص التي يراها المستخدم — بسيطة ومرتبة للموبايل."""

from __future__ import annotations

from database.models import Application

from .catalog import PC_GAME_CATEGORY, display_category
from .helpers import format_size, human_time

APP_DOWNLOAD_FOOTER = (
    "━━━━━━━━━━━━━━\n"
    "🎮 لتحميل الألعاب والتطبيقات بسهولة:\n"
    "🤖 البوت: @Waleedzone_bot\n"
    "🌐 الموقع: https://waleed-zone.up.railway.app/"
)


def append_app_footer(text: str) -> str:
    """أضف تذييل التحميل الموحد لرسائل التطبيقات والألعاب."""
    clean = (text or "").rstrip()
    if not clean:
        return APP_DOWNLOAD_FOOTER
    if APP_DOWNLOAD_FOOTER in clean:
        return clean
    return f"{clean}\n\n{APP_DOWNLOAD_FOOTER}"


def download_link_block(url: str, *, title: str = "تحميل التطبيق") -> str:
    """رابط تحميل واضح داخل نص الرسالة بدل زر URL أسفلها."""
    safe_url = escape_html(url).replace('"', "&quot;")
    safe_title = escape_html(title)
    return append_app_footer(
        "━━━━━━━━━━━━━━\n"
        f"⬇️ <b>{safe_title}</b> ⬇️\n\n"
        f'<a href="{safe_url}"><b>🟢 اضغط هنا لبدء التحميل الآن 🟢</b></a>\n\n'
        "━━━━━━━━━━━━━━"
    )


def escape_html(text: str | None) -> str:
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def bounded_html(value: str | None, limit: int) -> str:
    """Truncate plain metadata by UTF-16 units BEFORE escaping/adding HTML tags."""
    raw = str(value or "")
    if len(raw.encode("utf-16-le")) // 2 > limit:
        raw = raw.encode("utf-16-le")[:max(0, limit - 1) * 2].decode("utf-16-le", "ignore") + "…"
    return escape_html(raw)


def final_download_message(app, url: str) -> str:
    return append_app_footer(
        f"⬇️ رابط تحميل {bounded_html(app.name, 200)}\n"
        f"💾 الحجم: {bounded_html(app.size or '—', 60)}\n\n"
        + download_link_block(url)
    )


def app_card(app: Application, *, short: bool = False) -> str:
    """بطاقة تطبيق كاملة للمستخدم."""
    category = display_category(app.category, app.platform)
    is_pc_game = category == PC_GAME_CATEGORY

    lines = [
        f"{'🖥️' if is_pc_game else '📱'} {bounded_html(app.name, 150)}",
        "",
    ]
    if app.version:
        lines.append(f"📦 الإصدار: {bounded_html(app.version, 50)}")
    if app.size:
        lines.append(f"💾 الحجم: {bounded_html(app.size, 50)}")
    if app.platform:
        platform_icon = "💻" if is_pc_game else "📱"
        lines.append(f"{platform_icon} النظام: {bounded_html(app.platform, 50)}")
    if category:
        lines.append(f"🗂 التصنيف: {bounded_html(category, 100)}")
    if app.developer:
        lines.append(f"👨‍💻 المطور: {bounded_html(app.developer, 150)}")
    if app.downloads:
        lines.append(f"📥 التحميلات: {app.downloads}")
    if not short and app.description:
        lines += ["", "📝 الوصف:", "", bounded_html(app.description, 1600)]

    return append_app_footer("\n".join(lines))


def latest_header() -> str:
    return "🆕 أحدث التطبيقات:\n"


def download_line(app: Application) -> str:
    return append_app_footer(f"⬇️ رابط التحميل:\n{escape_html(app.shrankme_url or app.devupload_url or '')}")


def search_prompt() -> str:
    return "🔎 اكتب اسم التطبيق الذي تبحث عنه.\n\nمثال: capcut"


def request_prompt() -> str:
    return "📱 اكتب اسم التطبيق الذي تريد أن نضيفه.\n\nمثال: Photoshop Android"


def maintenance_message() -> str:
    return "🛠 البوت تحت الصيانة حاليًا.\n\nجرّب لاحقًا وشكرًا لتفهمك."


def force_subscribe_message(channel_username: str | None) -> str:
    return (
        "⚠️ اشترك في قناتنا أولًا لتتمكن من استخدام البوت.\n\n"
        f"📢 القناة: @{channel_username or ''}"
    )


def upload_progress(step: int, total: int) -> str:
    bar = "▓" * step + "░" * (total - step)
    return f"⏳ جاري تجهيز التطبيق...\n\n{bar} {step}/{total}"


def app_request_notification(username: str | None, user_id: int, app_name: str, req_id: int) -> str:
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    user = f"@{username}" if username else f"#{user_id}"
    return (
        "📥 طلب تطبيق جديد\n"
        "──────────────\n"
        f"👤 المستخدم: {escape_html(user)}\n"
        f"🆔 Telegram ID: {user_id}\n"
        f"📱 التطبيق المطلوب: {escape_html(app_name)}\n"
        f"📅 التاريخ: {now}\n"
        f"🔖 رقم الطلب: #{req_id}"
    )


def request_summary(req, index: int) -> str:
    from .constants import STATUS_TRANSLATIONS

    status = STATUS_TRANSLATIONS.get(req.status, req.status)
    return (
        f"#{index} — {escape_html(req.app_name)}\n"
        f"👤 @{req.username or '-'} ({req.user_id})\n"
        f"📅 {human_time(req.created_at)} — {status}"
    )
