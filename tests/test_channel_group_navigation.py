from types import SimpleNamespace

from app.keyboards import user


def test_channel_links_keyboard_shows_only_channel(monkeypatch):
    monkeypatch.setattr(
        user, "get_settings",
        lambda: SimpleNamespace(CHANNEL_USERNAME="@Waleed_Zone", GROUP_USERNAME="@Waleed_Zone_Group"),
    )

    keyboard = user.channel_group_links_keyboard(include_channel=True, include_group=False)

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert [(button.text, button.url) for button in buttons] == [
        ("📢 القناة", "https://t.me/Waleed_Zone")
    ]


def test_group_links_keyboard_shows_only_group(monkeypatch):
    monkeypatch.setattr(
        user, "get_settings",
        lambda: SimpleNamespace(CHANNEL_USERNAME="@Waleed_Zone", GROUP_USERNAME="@Waleed_Zone_Group"),
    )

    keyboard = user.channel_group_links_keyboard(include_channel=False, include_group=True)

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert [(button.text, button.url) for button in buttons] == [
        ("💬 المجموعة", "https://t.me/Waleed_Zone_Group")
    ]


def test_channel_group_links_keyboard_keeps_both_by_default(monkeypatch):
    monkeypatch.setattr(
        user, "get_settings",
        lambda: SimpleNamespace(CHANNEL_USERNAME="@Waleed_Zone", GROUP_USERNAME="@Waleed_Zone_Group"),
    )

    keyboard = user.channel_group_links_keyboard()

    buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert [button.text for button in buttons] == ["📢 القناة", "💬 المجموعة", "🏠 القائمة"]
