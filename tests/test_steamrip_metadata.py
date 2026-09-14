from integrations.steamrip_metadata import extract_game_size


def test_extracts_file_size_across_html_tags():
    html = """
    <div class="game-info">
      <strong>File Size:</strong>
      <span>112.4 GB</span>
    </div>
    """

    assert extract_game_size(html) == "112.4 GB"


def test_extracts_download_size_with_split_markup():
    html = """
    <p>Download <b>Size</b> — <span>98 GB</span></p>
    """

    assert extract_game_size(html) == "98 GB"


def test_extracts_game_size_and_normalizes_decimal_comma():
    html = "<p><strong>Game Size:</strong> 10,5 GB</p>"

    assert extract_game_size(html) == "10.5 GB"


def test_does_not_confuse_system_storage_requirement_with_download_size():
    html = """
    <section>
      <h3>System Requirements</h3>
      <p>Memory: 16 GB RAM</p>
      <p>Storage: 120 GB available space</p>
    </section>
    """

    assert extract_game_size(html) == ""
