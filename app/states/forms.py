"""حالات Flow State Machine (FSM) للبوت."""

from aiogram.fsm.state import State, StatesGroup


class UploadStates(StatesGroup):
    waiting_file = State()
    waiting_name = State()
    waiting_description = State()
    waiting_version = State()
    waiting_platform = State()
    waiting_category = State()
    waiting_icon = State()
    waiting_publish_choice = State()

class EditAppStates(StatesGroup):
    """تدفق تعديل تطبيق موجود (للمالك فقط)."""

    choosing_field = State()
    waiting_value = State()


class SearchStates(StatesGroup):
    """تدفق بحث المستخدم عن تطبيق."""

    waiting_query = State()


class RequestStates(StatesGroup):
    """تدفق طلب تطبيق من المستخدم."""

    waiting_app_name = State()


class BroadcastStates(StatesGroup):
    """تدفق إرسال إعلان (للمالك فقط)."""

    waiting_text = State()
    waiting_target = State()


class GroupAdminStates(StatesGroup):
    """تدفق إعدادات الجروب (للمالك فقط)."""

    waiting_welcome_message = State()
    waiting_warn_limit = State()
    waiting_banned_word = State()
    waiting_ban_target = State()
    waiting_mute_target = State()
    waiting_unban_target = State()
