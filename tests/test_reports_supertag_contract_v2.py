import json
import uuid
from datetime import datetime, timezone

import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect.reports_supertag import _event

SITE = {'id': 'site', 'client_id': 7, 'config': {}}


def raw(kind='click', **data):
    return {'event_id': str(uuid.uuid4()), 'visitor_id': str(uuid.uuid4()), 'session_id': str(uuid.uuid4()), 'kind': kind,
            'path': '/lp', 'attribution': {}, 'data': data, 'viewport_width': 390, 'viewport_height': 800,
            'occurred_at': datetime.now(timezone.utc).isoformat(), 'consent': 'granted'}


def stored(result):
    return next(json.loads(item) for item in result if isinstance(item, str) and item.startswith('{') and ('"x"' in item or '"dx"' in item))


def test_old_tags_without_document_position_still_validate():
    assert stored(_event(raw(x=10, y=20, element_id='cta'), SITE)) == {'x': 10, 'y': 20, 'element_id': 'cta'}


def test_document_position_is_stored_when_complete():
    data = stored(_event(raw('whatsapp_click', x=10, y=20, dx=450, dy=980, dh=5400), SITE))
    assert data['dx'] == 450 and data['dy'] == 980 and data['dh'] == 5400 and data['x'] == 10


@pytest.mark.parametrize('extra', [
    {'dx': 10, 'dy': 10}, {'dx': 10, 'dh': 100}, {'dx': 1001, 'dy': 1, 'dh': 100}, {'dx': -1, 'dy': 1, 'dh': 100},
    {'dx': 1, 'dy': 1, 'dh': 0}, {'dx': 1, 'dy': 1, 'dh': 100001}, {'dx': True, 'dy': 1, 'dh': 100}, {'dx': 'a', 'dy': 1, 'dh': 100}])
def test_partial_or_out_of_range_document_position_is_rejected(extra):
    with pytest.raises(BadRequest):
        _event(raw(x=1, y=1, **extra), SITE)


def test_document_fields_are_not_allowed_on_other_event_kinds():
    with pytest.raises(BadRequest):
        _event(raw('scroll_depth', depth=25, dx=1, dy=1, dh=10), SITE)


def test_element_name_and_type_are_stored_in_one_line():
    data = stored(_event(raw(x=1, y=1, el_label='  Request\n a   proposal ', el_kind='button'), SITE))
    assert data['el_label'] == 'Request a proposal' and data['el_kind'] == 'button'


@pytest.mark.parametrize('label', ['ana@exemplo.com', 'Ligue (31) 99999-1234', 'CPF 12345678900', '   '])
def test_element_names_that_look_like_personal_data_are_dropped_not_rejected(label):
    data = stored(_event(raw(x=1, y=1, el_label=label, el_kind='link'), SITE))
    assert 'el_label' not in data and data['el_kind'] == 'link'


def test_element_name_is_cut_to_80_characters():
    assert len(stored(_event(raw(x=1, y=1, el_label='a' * 300), SITE))['el_label']) == 80


@pytest.mark.parametrize('extra', [{'el_kind': 'video'}, {'el_label': 12}, {'el_label': ['x']}])
def test_invalid_element_type_or_name_is_rejected(extra):
    with pytest.raises(BadRequest):
        _event(raw(x=1, y=1, **extra), SITE)
