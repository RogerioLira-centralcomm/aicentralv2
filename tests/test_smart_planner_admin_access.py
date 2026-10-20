"""O admin interno abre, edita e processa planos de qualquer responsável; os demais só os próprios."""

import pytest

from aicentralv2.smart_planner import service
from aicentralv2.smart_planner.repository import SessionNotFound

OTHERS_PLAN = {"session_token": "tok-outro", "user_email": "ana@centralcomm.media", "user_name": "Ana"}


@pytest.fixture
def as_user(monkeypatch):
    def _set(email, admin):
        monkeypatch.setattr(service, "current_user", lambda: {"user_id": 7, "user_email": email, "user_name": "Eu"})
        monkeypatch.setattr(service, "_is_admin", lambda: admin)
        monkeypatch.setattr(service, "get_by_token", lambda token: dict(OTHERS_PLAN) if token == "tok-outro" else None)
        monkeypatch.setattr(
            "aicentralv2.smart_planner.repository.get_by_token",
            lambda token: dict(OTHERS_PLAN) if token == "tok-outro" else None,
        )
    return _set


def test_admin_loads_a_plan_owned_by_someone_else(as_user):
    as_user("apolo@centralcomm.media", admin=True)
    row = service.load_owned("tok-outro")
    assert row["user_email"] == "ana@centralcomm.media"  # o responsável não muda


def test_regular_user_still_cannot_open_someone_elses_plan(as_user):
    as_user("apolo@centralcomm.media", admin=False)
    with pytest.raises(SessionNotFound):
        service.load_owned("tok-outro")


def test_owner_opens_own_plan_without_admin(as_user):
    as_user("ana@centralcomm.media", admin=False)
    assert service.load_owned("tok-outro")["user_name"] == "Ana"


def test_admin_gets_not_found_for_a_missing_plan(as_user):
    as_user("apolo@centralcomm.media", admin=True)
    with pytest.raises(SessionNotFound):
        service.load_owned("nao-existe")
