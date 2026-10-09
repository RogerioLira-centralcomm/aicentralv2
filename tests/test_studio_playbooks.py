"""Playbooks por tipo de criação: leitura do MD, cor de recorte e transparência real."""
import io

from PIL import Image

from aicentralv2.creative_media import studio_playbooks


def test_interface_illustration_playbook():
    book = studio_playbooks.get('ilustracao_interface')
    assert book['brand'] == 'brand_asset' and book['transparent'] is True and book['text'] == 'none'
    assert 'ILUSTRAÇÃO DE INTERFACE' in book['director']
    assert any('ABSOLUTELY NO TEXT' in line for line in book['image'])
    assert book['review'] == {'no_text': True, 'single_cluster': True}


def test_ads_and_unknown_types_have_no_playbook():
    assert studio_playbooks.get('anuncio') is None
    assert studio_playbooks.get('') is None
    assert studio_playbooks.get('../etc/passwd') is None


def test_key_colour_avoids_brand_greens():
    assert studio_playbooks.key_colour(['#6848EB', '#0A0D12']) == '#00FF00'
    assert studio_playbooks.key_colour(['#16BC7B']) == '#FF00FF'
    assert studio_playbooks.key_colour(['#4FFF82']) == '#FF00FF'


def test_magenta_key_out_keeps_green_subject():
    image = Image.new('RGB', (64, 64), (255, 0, 255))
    for x in range(20, 44):
        for y in range(20, 44):
            image.putpixel((x, y), (22, 188, 123))  # verde do Planner
    buffer = io.BytesIO(); image.save(buffer, 'PNG')
    out = Image.open(io.BytesIO(studio_playbooks.key_out(buffer.getvalue(), '#FF00FF')))
    assert out.getpixel((2, 2))[3] == 0
    assert out.getpixel((32, 32))[3] == 255 and out.getpixel((32, 32))[:3] == (22, 188, 123)


def _fake_review(monkeypatch, seen):
    import json
    from aicentralv2.services import openrouter_service
    monkeypatch.setattr(openrouter_service, 'chat_completion', lambda *a, **k: {'message': {'content': json.dumps(seen)}})
    monkeypatch.setattr(openrouter_service, 'message_text', lambda message: message['content'])


def _png_b64():
    import base64
    image = Image.new('RGB', (32, 32), (0, 255, 0)); image.paste((40, 40, 200), (8, 8, 24, 24))
    buffer = io.BytesIO(); image.save(buffer, 'PNG')
    return base64.b64encode(buffer.getvalue()).decode('ascii')


def test_playbook_review_rejects_text_then_own_logo_and_notes_fake_logos(monkeypatch):
    book = studio_playbooks.get('ilustracao_interface')
    _fake_review(monkeypatch, {'visible_text': ['DOOH'], 'own_logo': True, 'third_party_logos': [{'name': 'Exame', 'faithful': False}], 'score': 60})
    verdict = studio_playbooks.review(_png_b64(), book, brief='Portais Valor, Exame', key='#00FF00')
    assert verdict['reviewed'] and not verdict['approved'] and verdict['reason'] == 'stray_text'
    assert 'Exame' in verdict['notes'][0]
    _fake_review(monkeypatch, {'visible_text': [], 'own_logo': True, 'score': 70})
    assert studio_playbooks.review(_png_b64(), book, brief='Formatos', key='#00FF00')['reason'] == 'own_logo'
    _fake_review(monkeypatch, {'visible_text': [], 'own_logo': False, 'frames_or_cards': False, 'finish': 'soft_3d', 'score': 88})
    clean = studio_playbooks.review(_png_b64(), book, brief='Formatos', key='#00FF00')
    assert clean['approved'] and clean['score'] == 88 and clean['notes'] == []


def test_playbook_edit_prompt_keeps_key_background():
    text = studio_playbooks.edit_prompt({'reason': 'own_logo'}, '#FF00FF')
    assert 'REMOVE the project' in text and '#FF00FF' in text
