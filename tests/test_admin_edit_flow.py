from app.handlers.admin import _edit_cancel_keyboard


def test_edit_cancel_returns_to_the_current_app_management_page():
    keyboard = _edit_cancel_keyboard(app_id=42, page=3)

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "❌ إلغاء والعودة للتطبيق"
    assert button.callback_data == "admin:edit_cancel:42:3"


from app.keyboards.admin import toggle_confirm_keyboard


def test_toggle_confirmation_targets_the_requested_state():
    enable = toggle_confirm_keyboard(app_id=42, page=3, target_active=True)
    disable = toggle_confirm_keyboard(app_id=42, page=3, target_active=False)

    assert enable.inline_keyboard[0][0].callback_data == "admin:toggle_apply_on:42:3"
    assert enable.inline_keyboard[0][0].text == "✅ نعم، فعّل التطبيق"
    assert disable.inline_keyboard[0][0].callback_data == "admin:toggle_apply_off:42:3"
    assert disable.inline_keyboard[0][0].text == "🚫 نعم، عطّل التطبيق"
    assert enable.inline_keyboard[0][1].callback_data == "admin:app_manage:42:3"
