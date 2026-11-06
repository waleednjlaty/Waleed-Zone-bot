"""خدمة إدارة الجروب: الترحيب، الحماية، التحذيرات، وأوامر الإشراف."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict, deque
from datetime import timedelta

from aiogram import Bot
from aiogram.types import ChatMemberUpdated, ChatPermissions, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.constants import DEFAULT_SETTINGS
from app.utils.helpers import escape_html
from database import repositories as repo
from integrations.telegram import send_with_retry

logger = logging.getLogger(__name__)

# مراقبة الفيض: {chat_id: {user_id: deque(timestamps)}}
_flood_track: dict[int, dict[int, deque[float]]] = defaultdict(lambda: defaultdict(deque))
_LAST_TEXT: dict[int, dict[int, tuple[str, float]]] = defaultdict(dict)


class GroupService:
    """عمليات الجروب: ترحيب، حماية، تحذيرات، أوامر مشرف."""

    # ---------------------------------------------------------- الترحيب
    async def welcome_if_needed(
        self, bot: Bot, session: AsyncSession, event: ChatMemberUpdated
    ) -> None:
        if event.chat.type not in ["group", "supergroup"]:
            return
        if not event.new_chat_member:
            return

        member = event.new_chat_member.user
        if member.is_bot:
            return

        enabled = await repo.get_setting_bool(
            session, "welcome_enabled", True
        )
        if not enabled:
            return

        template = (
            await repo.get_setting(
                session, "welcome_message", DEFAULT_SETTINGS["welcome_message"]
            )
            or DEFAULT_SETTINGS["welcome_message"]
        )

        username = f"@{member.username}" if member.username else member.full_name
        text = template.replace("{username}", escape_html(username))
        text = text.replace("{name}", escape_html(member.full_name))
        
        from app.keyboards.user import back_to_menu_keyboard

        await send_with_retry(
            bot,
            chat_id=event.chat.id,
            text=text,
            reply_markup=back_to_menu_keyboard(),
        )
        await repo.add_group_log(
            session,
            chat_id=event.chat.id,
            user_id=member.id,
            username=member.username,
            action="join",
            detail=f"User {member.id} joined",
        )

    # ---------------------------------------------------------- الحماية
    async def check_message(
        self, bot: Bot, session: AsyncSession, message: Message
    ) -> bool:
        anti_spam = await repo.get_setting_bool(session, "anti_spam_enabled", True)
        if not anti_spam:
            return True
        if not message.from_user or message.from_user.is_bot:
            return True

        text = (message.text or message.caption or "").strip()
        user_id = message.from_user.id
        chat_id = message.chat.id

        banned = await repo.list_banned_words(session)
        if banned and text:
            lowered = text.lower()
            for word in banned:
                if word and word in lowered:
                    await self._handle_violation(
                        bot, session, message, reason=f"كلمة محظورة: {word}"
                    )
                    return False

        if text:
            now = time.monotonic()
            prev = _LAST_TEXT[chat_id].get(user_id)
            if prev and prev[0] == text and now - prev[1] < 60:
                window = _flood_track[chat_id][user_id]
                window.append(now)
                while window and now - window[0] > 60:
                    window.popleft()
                if len(window) >= 3:
                    await self._handle_violation(
                        bot, session, message, reason="تكرار الرسائل (Flood)"
                    )
                    return False
                _LAST_TEXT[chat_id][user_id] = (text, now)
                return True
            _LAST_TEXT[chat_id][user_id] = (text, now)
        return True

    async def _handle_violation(
        self, bot: Bot, session: AsyncSession, message: Message, reason: str
    ) -> None:
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except Exception as exc:
            logger.debug("Cannot delete message: %s", exc)
        await self.warn(bot, session, message, reason=reason)

    # ---------------------------------------------------------- التحذيرات
    async def warn(
        self,
        bot: Bot,
        session: AsyncSession,
        message: Message,
        *,
        target: Message | None = None,
        reason: str = "سلوك مخالف",
    ) -> str | None:
        """تحذير عضو (أو مرسل الرسالة إن لم يُحدد target)."""
        ref = target or message
        user = ref.from_user
        if user is None:
            return None
        chat_id = message.chat.id
        warn_limit = int(
            await repo.get_setting(session, "warn_limit", DEFAULT_SETTINGS["warn_limit"])
            or DEFAULT_SETTINGS["warn_limit"]
        )
        warn_action = await repo.get_setting(
            session, "warn_action", DEFAULT_SETTINGS["warn_action"]
        ) or "mute"

        warn = await repo.increment_warning(
            session, chat_id, user.id, username=user.username, reason=reason
        )
        await repo.add_group_log(
            session,
            chat_id=chat_id,
            user_id=user.id,
            username=user.username,
            action="warn",
            detail=reason,
        )

        if warn.count >= warn_limit:
            await self._apply_action(
                bot, session, message, user.id, warn_action
            )
            await repo.clear_warnings(session, chat_id, user.id)
            action_text = "🔇 كتم" if warn_action == "mute" else "🚫 حظر"
            text = (
                f"⚠️ {escape_html(user.full_name)} تجاوز حد التحذيرات ({warn_limit})\n"
                f"الإجراء: {action_text}\n"
                f"السبب: {escape_html(reason)}"
            )
        else:
            text = (
                f"⚠️ تحذير {warn.count}/{warn_limit} — {escape_html(user.full_name)}\n"
                f"السبب: {escape_html(reason)}\n"
                f"الرجاء الالتزام بقواعد المجموعة."
            )
        await send_with_retry(bot, chat_id=chat_id, text=text)
        return text

    async def _apply_action(
        self,
        bot: Bot,
        session: AsyncSession,
        message: Message,
        target_id: int,
        action: str,
    ) -> None:
        try:
            if action == "ban":
                await bot.ban_chat_member(
                    chat_id=message.chat.id,
                    user_id=target_id,
                    until_date=timedelta(days=1),
                )
            else:
                await bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=target_id,
                    permissions=ChatPermissions(can_send_messages=False),
                )
        except Exception as exc:
            logger.warning("apply_action failed for %s: %s", target_id, exc)

    # ---------------------------------------------------------- أوامر المشرف
    async def ban_member(self, bot: Bot, session: AsyncSession, message: Message) -> str:
        target = message.reply_to_message
        if target is None or target.from_user is None:
            return "⚠️ قم بالرد على رسالة العضو الذي تريد حظره."
        if target.from_user.is_bot:
            return "❌ لا يمكنك حظر البوتات!"
        try:
            await bot.ban_chat_member(message.chat.id, target.from_user.id)
            await message.delete()
            await repo.add_group_log(
                session, chat_id=message.chat.id, user_id=target.from_user.id,
                username=target.from_user.username, action="ban", detail="Admin ban",
            )
            return f"🔨 تم حظر @{target.from_user.username or target.from_user.id}."
        except Exception:
            return "❌ تعذر الحظر (تأكد من صلاحيات البوت)."

    async def unban_member(self, bot: Bot, session: AsyncSession, message: Message) -> str:
        target = message.reply_to_message
        if target is None or target.from_user is None:
            return "⚠️ قم بالرد على رسالة العضو لإلغاء الحظر."
        try:
            await bot.unban_chat_member(message.chat.id, target.from_user.id)
            await message.delete()
            return f"🔓 تم فك الحظر عن @{target.from_user.username or target.from_user.id}."
        except Exception:
            return "❌ تعذر فك الحظر."

    async def mute_member(self, bot: Bot, session: AsyncSession, message: Message) -> str:
        target = message.reply_to_message
        if target is None or target.from_user is None:
            return "⚠️ قم بالرد على رسالة العضو لكتمه."
        if target.from_user.is_bot:
            return "❌ لا يمكنك كتم البوتات!"
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target.from_user.id,
                permissions=ChatPermissions(can_send_messages=False),
            )
            await message.delete()
            return f"🔇 تم كتم @{target.from_user.username or target.from_user.id}."
        except Exception:
            return "❌ تعذر الكتم."

    async def unmute_member(self, bot: Bot, session: AsyncSession, message: Message) -> str:
        target = message.reply_to_message
        if target is None or target.from_user is None:
            return "⚠️ قم بالرد على رسالة العضو لفك الكتم."
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target.from_user.id,
                permissions=ChatPermissions(can_send_messages=True),
            )
            await message.delete()
            return f"🔊 تم فك الكتم عن @{target.from_user.username or target.from_user.id}."
        except Exception:
            return "❌ تعذر فك الكتم."

    async def delete_message(self, bot: Bot, message: Message) -> None:
        if message.reply_to_message is None:
            msg = await message.reply("⚠️ قم بالرد على الرسالة التي تريد حذفها.")
            await asyncio.sleep(3)
            await msg.delete()
            try:
                await message.delete()
            except Exception:
                pass
            return
        try:
            await bot.delete_message(
                chat_id=message.chat.id, message_id=message.reply_to_message.message_id
            )
            await message.delete()
            temp_msg = await message.answer("🗑 تم الحذف.")
            await asyncio.sleep(3)
            await temp_msg.delete()
        except Exception:
            pass

    async def pin_message(self, bot: Bot, message: Message) -> str:
        if message.reply_to_message is None:
            return "⚠️ قم بالرد على الرسالة التي تريد تثبيتها."
        try:
            await bot.pin_chat_message(
                chat_id=message.chat.id, message_id=message.reply_to_message.message_id
            )
            await message.delete()
            return "📌 تم تثبيت الرسالة."
        except Exception:
            return "❌ تعذر تثبيت الرسالة."

    async def promote_member(self, bot: Bot, session: AsyncSession, message: Message) -> str:
        target = message.reply_to_message
        if target is None or target.from_user is None:
            return "⚠️ قم بالرد على رسالة العضو لترفيعه لمشرف."
        if target.from_user.is_bot:
            return "❌ لا يمكنك ترفيع البوتات!"
        try:
            await bot.promote_chat_member(
                chat_id=message.chat.id,
                user_id=target.from_user.id,
                is_anonymous=False,
                can_manage_chat=True,
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_promote_members=False,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True,
            )
            await message.delete()
            return f"⭐ تم ترفيع @{target.from_user.username or target.from_user.id} إلى مشرف بنجاح!"
        except Exception:
            return "❌ تعذر الترفيع (تأكد أن البوت يملك صلاحية إضافة مشرفين)."

    async def demote_member(self, bot: Bot, session: AsyncSession, message: Message) -> str:
        target = message.reply_to_message
        if target is None or target.from_user is None:
            return "⚠️ قم بالرد على رسالة العضو لتنزيله من الإشراف."
        if target.from_user.is_bot:
            return "❌ لا يمكنك تطبيق هذا على البوتات!"
        try:
            await bot.promote_chat_member(
                chat_id=message.chat.id,
                user_id=target.from_user.id,
                is_anonymous=False,
                can_manage_chat=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
            )
            await message.delete()
            return f"📉 تم تنزيل @{target.from_user.username or target.from_user.id} من الإشراف."
        except Exception:
            return "❌ تعذر تنزيل العضو."

    async def lock_chat(self, bot: Bot, message: Message) -> str:
        try:
            await bot.set_chat_permissions(
                chat_id=message.chat.id,
                permissions=ChatPermissions(can_send_messages=False)
            )
            await message.delete()
            return "🔒 تم قفل المجموعة (منع الأعضاء من الكتابة)."
        except Exception:
            return "❌ تعذّر قفل المجموعة. تحقّق من أن البوت مشرف ويملك صلاحية تغيير أذونات المجموعة."

    async def unlock_chat(self, bot: Bot, message: Message) -> str:
        try:
            await bot.set_chat_permissions(
                chat_id=message.chat.id,
                permissions=ChatPermissions(
                    can_send_messages=True,
                    can_send_media_messages=True,
                    can_send_other_messages=True,
                    can_add_web_page_previews=True
                )
            )
            await message.delete()
            return "🔓 تم فتح المجموعة للأعضاء."
        except Exception:
            return "❌ تعذر فتح المجموعة."

    async def get_user_id(self, message: Message) -> str:
        target = message.reply_to_message
        user = target.from_user if target and target.from_user else message.from_user
        chat_id = message.chat.id
        await message.delete()
        return f"🆔 **معلومات الأداة:**\n- معرف المستخدم (User ID): `{user.id}`\n- معرف المجموعة (Chat ID): `{chat_id}`"

    async def help_group_commands(self, message: Message) -> str:
        try:
            await message.delete()
        except Exception:
            pass
        return (
            "🛡 **لوحة تحكم المشرفين الذكية**\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "💡 *طريقة الاستخدام:* قم بالرد (Reply) على رسالة العضو واكتب الكلمة مباشرة:\n\n"
            "🔨 **الإشراف والعقوبات:**\n"
            "• **حظر** أو **طرد** ⟵ لحظر العضو نهائياً\n"
            "• **كتم** ⟵ لمنع العضو من الكتابة\n"
            "• **فك الحظر** ⟵ لإلغاء الحظر عن العضو\n"
            "• **فك الكتم** ⟵ لإلغاء الكتم\n\n"
            "⭐ **الإدارة والصلاحيات:**\n"
            "• **ترفيع** ⟵ ترقية العضو إلى مشرف\n"
            "• **تنزيل** ⟵ إزالة صفة الإشراف عنه\n\n"
            "🧹 **تنظيف وإدارة الدردشة:**\n"
            "• **حذف** أو **مسح** ⟵ حذف الرسالة مع إشعار مؤقت\n"
            "• **تثبيت** ⟵ تثبيت رسالة في المجموعة\n"
            "• **قفل** ⟵ منع الأعضاء من إرسال الرسائل\n"
            "• **فتح** ⟵ السماح للجميع بالكتابة\n"
            "• **آيدي** ⟵ عرض معرفات المستخدم والمجموعة\n"
            "• **الأوامر** ⟵ إظهار هذه القائمة الشاملة"
        )

    async def show_warnings(self, bot: Bot, session: AsyncSession, message: Message) -> str:
        target = message.reply_to_message
        user_id = target.from_user.id if target and target.from_user else message.from_user.id
        warn = await repo.get_warning(session, message.chat.id, user_id)
        count = warn.count if warn else 0
        limit = await repo.get_setting(session, "warn_limit", "3") or "3"
        try:
            await message.delete()
        except Exception:
            pass
        return f"⚠️ تحذيرات العضو: {count}/{limit}"
