"""Technology of a visit: User-Agent families, screen data accepted on page_view and never the raw header."""
import json
import uuid

import pytest
from flask import Flask
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect import reports_supertag, reports_tech
from tests.test_reports_supertag import raw_event

SITE = {'id': str(uuid.uuid4()), 'client_id': 7, 'public_id': 'pub', 'allowed_host': 'example.test', 'config': {}, 'config_version': 1}


@pytest.mark.parametrize('agent,expected', [
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1', ('iOS', 'Safari')),
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Instagram 320.0.0 (iPhone14,2)', ('iOS', 'Instagram')),
    ('Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36', ('Android', 'Chrome')),
    ('Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/450.0]', ('Android', 'Facebook')),
    ('Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/117.0.0.0 Mobile Safari/537.36', ('Android', 'Samsung Internet')),
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0', ('Windows', 'Edge')),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:125.0) Gecko/20100101 Firefox/125.0', ('macOS', 'Firefox')),
    ('Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36', ('ChromeOS', 'Chrome')),
    ('Mozilla/5.0 (Linux; Android 13; Pixel 7 Build/TQ3A; wv) AppleWebKit/537.36 Version/4.0 Chrome/124.0 Mobile Safari/537.36', ('Android', 'WebView')),
    ('curl/8.0', ('Outro', 'Outro')), ('', ('Outro', 'Outro')), (None, ('Outro', 'Outro')),
])
def test_user_agent_reduces_to_system_and_browser_families(agent, expected):
    assert reports_tech.tech_from_user_agent(agent) == expected


def page_view(**data):
    return {**raw_event('page_view'), 'data': data}


def test_page_view_keeps_screen_data_and_adds_families_from_the_header():
    agent = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1'
    with Flask(__name__).test_request_context(headers={'User-Agent': agent}):
        row = reports_supertag._event(page_view(sw=390, sh=844, dpr=3.0, orient='portrait'), SITE)
    data = json.loads(row[10])
    assert data == {'sw': 390, 'sh': 844, 'dpr': 3.0, 'orient': 'portrait', 'os': 'iOS', 'browser': 'Safari'}
    assert agent not in json.dumps(row, default=str)


def test_old_tags_without_screen_data_still_work_and_get_families():
    with Flask(__name__).test_request_context(headers={'User-Agent': 'Firefox/125.0 Windows'}):
        data = json.loads(reports_supertag._event(page_view(), SITE)[10])
    assert data == {'os': 'Windows', 'browser': 'Firefox'}


@pytest.mark.parametrize('data', [{'sw': 0}, {'sw': 10001}, {'sh': 'x'}, {'sw': True}, {'sw': 390.5}, {'dpr': 0.1}, {'dpr': 11}, {'dpr': 'x'},
                                  {'orient': 'diagonal'}, {'os': 'Windows'}, {'user_agent': 'x'}])
def test_page_view_rejects_bad_screen_data_and_client_supplied_families(data):
    with pytest.raises(BadRequest):
        reports_supertag._event(page_view(**data), SITE)
