import pytest
from werkzeug.exceptions import BadRequest

from aicentralv2.cadu_connect.reports_v1 import (
    _google_ads_account_id,
    _google_ads_account_id_for_update,
)


def test_google_ads_account_id_accepts_hyphenated_and_canonical_values():
    assert _google_ads_account_id('123-456-7890') == '1234567890'
    assert _google_ads_account_id('1234567890') == '1234567890'


def test_google_ads_account_id_rejects_non_customer_ids():
    with pytest.raises(BadRequest):
        _google_ads_account_id('1')


def test_metadata_update_preserves_unchanged_legacy_id():
    assert _google_ads_account_id_for_update('1', '1') == '1'
    assert _google_ads_account_id_for_update('123-456-7890', '123-456-7890') == '1234567890'


def test_account_id_update_validates_and_canonicalizes_changes():
    assert _google_ads_account_id_for_update('123-456-7890', '1') == '1234567890'
    with pytest.raises(BadRequest):
        _google_ads_account_id_for_update('2', '1')
