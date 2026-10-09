"""A variação de anúncio não muda; tipos do Quadro (ilustração, página, post) recebem uma variação de série."""
from aicentralv2.creative_media import studio_review


def test_ad_variation_prompt_is_unchanged():
    text = studio_review.variation_prompt('1:1')
    assert 'It is a finished ad of this campaign' in text and 'layout zones' in text
    assert studio_review.variation_prompt('1:1', 'anuncio') == text


def test_series_variation_does_not_copy_layout():
    for kind in ('ilustracao', 'landing_vendas', 'site', 'post'):
        text = studio_review.variation_prompt('1:1', kind)
        assert 'not an advertisement' in text and 'do not copy its subject, objects or layout' in text
        assert 'finished ad' not in text and '(1:1)' in text
