from app.handlers.admin import _edit_cancel_keyboard


def test_edit_cancel_returns_to_the_current_app_management_page():
    keyboard = _edit_cancel_keyboard(app_id=42, page=3)

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "❌ إلغاء والعودة للتطبيق"
    assert button.callback_data == "admin:edit_cancel:42:3"
