from app.handlers.start import HELP_TEXT, WELCOME_TEXT


def test_welcome_text_has_clean_website_section():
    assert "🌐 لواجهة تصفّح أسهل" in WELCOME_TEXT
    assert "https://waleedzone.xyz/" in WELCOME_TEXT
    assert "الموقع الخاص بنا :" not in WELCOME_TEXT
    assert "\\n" not in WELCOME_TEXT


def test_help_text_explains_main_user_actions():
    for phrase in ("تصفّح التطبيقات", "بحث عن تطبيق", "المفضلة", "طلب تطبيق", "الإشعارات"):
        assert phrase in HELP_TEXT
    assert "https://waleedzone.xyz/" in HELP_TEXT
    assert "\\n" not in HELP_TEXT
