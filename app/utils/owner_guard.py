"""ADMIN_IDS remains the sole authority for privileged handlers and FSM steps."""

from app.utils.helpers import is_admin


async def owner_gate(event) -> bool:
    user = getattr(event, "from_user", None)
    if user and is_admin(user.id):
        return True
    await event.answer("⛔ صلاحية غير متاحة.")
    return False
