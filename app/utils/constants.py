"""ثوابت التطبيق: بيانات الـ Callback و القوائم الافتراضية و إعدادات الحماية."""

from aiogram.filters.callback_data import CallbackData

BOT_NAME = "Waleed Zone"
BOT_USERNAME_ENV = "BOT_USERNAME"  # من .env إن وُجد

DEFAULT_CATEGORIES = [
    "أدوات",
    "ألعاب كمبيوتر",
    "ألعاب موبايل",
    "مونتاج",
    "VPN",
    "متصفح",
    "إنتاجية",
    "تواصل اجتماعي",
    "تعليم",
    "صور",
    "موسيقى",
    "أخرى",
]

REQUIRED_PLATFORMS = ["Android", "iOS", "Windows", "macOS", "Linux", "أخرى"]

DEFAULT_SETTINGS = {
    "maintenance_mode": "0",
    "force_subscribe": "0",
    "welcome_enabled": "1",
    "welcome_message": "👋 أهلاً بك يا {username}\n\nنورت الجروب ❤️\n\nلتحميل التطبيقات اضغط الزر أدناه:",
    "anti_spam_enabled": "1",
    "warn_limit": "3",
    "warn_action": "mute",  # mute | ban
    "notifications_enabled": "1",
}

STATUS_TRANSLATIONS = {
    "pending": "⏳ قيد الانتظار",
    "processing": "⏳ قيد المعالجة",
    "completed": "✅ تم التنفيذ",
    "rejected": "❌ مرفوض",
}

EMOJI_STATUS = {
    "pending": "⏳",
    "processing": "🔄",
    "completed": "✅",
    "rejected": "❌",
}


# ---------------------------------------------------------------- Callbacks
class MainMenuCB(CallbackData, prefix="mm"):
    action: str


class AppsCB(CallbackData, prefix="apps"):
    category: str = "all"
    page: int = 0


class AppCB(CallbackData, prefix="app"):
    action: str
    app_id: int = 0


class LatestCB(CallbackData, prefix="latest"):
    page: int = 0


class SearchCB(CallbackData, prefix="search"):
    action: str


class FavsCB(CallbackData, prefix="favs"):
    page: int = 0


class NotifCB(CallbackData, prefix="notif"):
    enabled: int = 1


class ReqCB(CallbackData, prefix="req"):
    action: str
    req_id: int = 0


class BannedWordCB(CallbackData, prefix="bw"):
    action: str
    word: str = ""


class AdminCB(CallbackData, prefix="admin"):
    action: str
    app_id: int = 0
    page: int = 0
