import json

from psycopg.types.json import Json, JsonDumper

from aicentralv2 import db


def test_text_and_json_sent_to_postgres_drop_nul():
    assert db._sem_nul({'notes\x00': ['está\x00dio', 0, None]}) == {'notes': ['estádio', 0, None]}
    assert db._StrSemNul(str).dump('a\x00b') == b'ab'
    assert json.loads(bytes(JsonDumper(Json).dump(Json({'notes': 'a\x00b'})))) == {'notes': 'ab'}
