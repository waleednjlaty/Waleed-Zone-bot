import pytest

@pytest.mark.parametrize('key', ['cf-mitigated', 'Cf-Mitigated', 'CF-MITIGATED'])
def test_header_only_200_human_challenge_is_case_insensitive(key):
    from integrations import steamrip_extractor as e
    with pytest.raises(e.ProviderResolutionError, match='PROVIDER_CHALLENGE'):
        e._require_success(200, '', {key: 'challenge'}, 'steamrip_page', 'https://steamrip.com/qa/')


def test_mixed_case_hx_redirect_header_retains_host_validation():
    from integrations import steamrip_extractor as e
    assert e._direct_link_from_headers({'Hx-Redirect': 'https://ts.bzzhr.co/d/file?v=x'}, 'https://bzzhr.co/file/fetch') == 'https://ts.bzzhr.co/d/file?v=x'
    assert e._direct_link_from_headers({'hX-rEdIrEcT': 'https://evil.test/d/file?v=x'}, 'https://bzzhr.co/file/fetch') is None
