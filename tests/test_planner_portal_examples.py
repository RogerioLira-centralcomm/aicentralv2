import json
from pathlib import Path

from aicentralv2.cadu_planner import portal_examples as examples


def test_only_published_local_images_reach_customer_gallery(tmp_path, monkeypatch):
    monkeypatch.setattr(examples, 'EXAMPLES', tmp_path)
    folder = tmp_path / '1'
    folder.mkdir()
    (folder / 'good.webp').write_bytes(b'image')
    (folder / 'draft.webp').write_bytes(b'image')
    records = [
        {'file': 'good.webp', 'status': 'published', 'format': 'Billboard', 'size': '970x250', 'brand': 'Vivo'},
        {'file': 'draft.webp', 'status': 'needs_review', 'format': 'Banner', 'brand': 'Itaú'},
        {'file': '../outside.webp', 'status': 'published', 'format': 'Banner', 'brand': 'Itaú'},
        {'file': 'missing.webp', 'status': 'published', 'format': 'Banner', 'brand': 'Itaú'},
    ]
    (folder / 'gallery.json').write_text(json.dumps(records))
    portals = [{'id': 1, 'name': 'Portal'}, {'id': 2, 'name': 'Sem imagens'}]
    examples.attach_examples(portals)
    assert len(portals[0]['ad_examples']) == 1
    assert portals[0]['ad_examples'][0]['size'] == '970x250'
    assert 'reference' not in portals[0]['ad_examples'][0]
    assert portals[1]['ad_examples'] == []


def test_jobs_use_real_formats_only_and_limit_to_five():
    portal = {'id': 1, 'name': 'Portal', 'domain': 'portal.example',
              'ad_formats': [{'format': f'Formato {i}', 'size': '300x250'} for i in range(8)],
              'formats': {'market': [{'nome': 'Formato genérico'}]}}
    jobs = examples.jobs_for(portal)
    assert len(jobs) == 5
    assert len({job['key'] for job in jobs}) == 5
    assert all(job['format'] != 'Formato genérico' for job in jobs)
    assert len({job['brand'] for job in jobs}) == 5
    portal['ad_formats'] = []
    assert examples.jobs_for(portal) == []


def test_same_observed_format_is_not_generated_twice():
    portal = {'id': 1, 'name': 'Portal', 'domain': 'portal.example',
              'ad_formats': [{'format': 'Billboard', 'size': '970x250'}, {'format': 'Billboard', 'size': '970×250'}]}
    assert len(examples.jobs_for(portal)) == 1


def test_customer_detail_no_longer_projects_internal_captures(monkeypatch):
    from aicentralv2.cadu_planner import portals
    from aicentralv2.cadu_family import repository
    monkeypatch.setattr(repository, 'rows', lambda *a, **kw: [{'id': 1, 'name': 'Portal'}])
    monkeypatch.setattr(portals, 'attach_prints', lambda *a, **kw: (_ for _ in ()).throw(AssertionError('Internal captures leaked')))
    monkeypatch.setattr(portals, 'attach_formats', lambda p: p.update(formats={'own': [], 'observed': []}) or p)
    monkeypatch.setattr(portals, 'attach_thumbs', lambda p: p)
    result = portals.detail(1)
    assert 'prints' not in result and 'print_url' not in result


def test_customer_detail_drops_market_defaults(monkeypatch):
    from aicentralv2.cadu_planner import portals
    from aicentralv2.cadu_family import repository
    monkeypatch.setattr(repository, 'rows', lambda *a, **kw: [{'id': 1, 'name': 'Portal'}])
    monkeypatch.setattr(portals, 'attach_thumbs', lambda p: p)
    monkeypatch.setattr(portals, 'attach_formats', lambda p: p.update(formats={'own': [], 'observed': [], 'market': [{'nome': 'x'}]}) or p)
    assert 'market' not in portals.detail(1)['formats']


def test_mobile_only_for_phone_formats():
    assert examples.device_for('Mobile banner', '320x50') == 'mobile'
    assert examples.device_for('Half Page', '300x600') == 'desktop'
