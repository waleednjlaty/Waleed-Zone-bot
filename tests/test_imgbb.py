from types import SimpleNamespace

from app.services.image_migration import _needs_migration
from integrations.imgbb import is_imgbb_url


def test_imgbb_url_detection():
    assert is_imgbb_url("https://i.ibb.co/abc/game_42.jpg")
    assert is_imgbb_url("https://ibb.co/example")
    assert not is_imgbb_url("https://steamrip.com/wp-content/uploads/game.jpg")
    assert not is_imgbb_url(None)


def test_external_source_image_needs_migration():
    app = SimpleNamespace(
        image_url="https://steamrip.com/wp-content/uploads/game.jpg",
        icon_file_id=None,
        devupload_url="https://steamrip.com/game-free-download/",
    )
    assert _needs_migration(app)


def test_imgbb_image_does_not_migrate_again():
    app = SimpleNamespace(
        image_url="https://i.ibb.co/abc/game_12.jpg",
        icon_file_id="telegram-file-id",
        devupload_url="https://steamrip.com/game-free-download/",
    )
    assert not _needs_migration(app)
