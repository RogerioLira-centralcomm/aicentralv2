import pytest
from flask import Flask
from werkzeug.exceptions import NotFound

from aicentralv2.cadu_connect import reports_google_ads as gads


def narrowing(monkeypatch, query, rows):
    calls = []

    def fake_rows(sql, params=()):
        calls.append(params)
        return rows

    monkeypatch.setattr(gads, '_rows', fake_rows)
    with Flask(__name__).test_request_context('/?' + query):
        return gads._narrowing(7), calls


def test_no_scope_reads_everything(monkeypatch):
    assert narrowing(monkeypatch, '', [])[0] == (None, None)


def test_registered_campaign_resolves_account_and_google_id(monkeypatch):
    result, calls = narrowing(monkeypatch, 'scope_campaign=5', [{'account_id': 2, 'external_id': 98765}])
    assert result == (2, '98765') and calls[0] == (5, 7)


def test_unregistered_google_campaign_uses_account_and_google_id(monkeypatch):
    result, calls = narrowing(monkeypatch, 'scope_campaign=2:24126926393', [{'x': 1}])
    assert result == (2, '24126926393') and calls[0] == (2, 7)


def test_source_only(monkeypatch):
    assert narrowing(monkeypatch, 'scope_account=2', [{'x': 1}])[0] == (2, None)


@pytest.mark.parametrize('query', ['scope_campaign=5', 'scope_campaign=2:99', 'scope_account=2'])
def test_other_clients_ids_are_not_found(monkeypatch, query):
    with pytest.raises(NotFound):
        narrowing(monkeypatch, query, [])


def test_malformed_values_are_ignored(monkeypatch):
    assert narrowing(monkeypatch, "scope_campaign=1;drop&scope_account=x", [{'x': 1}])[0] == (None, None)
