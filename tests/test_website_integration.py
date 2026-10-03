from app.keyboards.admin import app_manage_keyboard
from app.utils.website import website_app_url


def test_website_app_url_uses_stable_legacy_route():
    assert (
        website_app_url(42, "https://waleed-zone.up.railway.app/")
        == "https://waleed-zone.up.railway.app/app/42"
    )


def test_website_app_url_rejects_unsafe_or_invalid_configuration():
    assert website_app_url(0, "https://example.com") is None
    assert website_app_url(5, "ftp://example.com") is None
    assert website_app_url(5, "https://user:pass@example.com") is None
    assert website_app_url(5, "https://example.com?token=secret") is None
    assert website_app_url(5, "https://example.com/#fragment") is None


def test_published_app_admin_keyboard_can_open_website():
    url = "https://waleed-zone.up.railway.app/app/42"
    keyboard = app_manage_keyboard(42, True, 0, website_url=url)
    buttons = [button for row in keyboard.inline_keyboard for button in row]
    website = next(button for button in buttons if button.text == "🌐 فتح في Waleed Zone")
    assert website.url == url


def test_unpublished_app_admin_keyboard_has_no_website_button():
    keyboard = app_manage_keyboard(42, True, 0)
    assert all(
        button.text != "🌐 فتح في Waleed Zone"
        for row in keyboard.inline_keyboard
        for button in row
    )
