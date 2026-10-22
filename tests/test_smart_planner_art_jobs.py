"""A geração das artes roda fora da requisição e deixa na sessão o estado e o motivo real da falha."""

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from aicentralv2.services.openrouter_service import OpenRouterError
from aicentralv2.smart_planner import art_jobs


def _setup(monkeypatch, render):
    store = {"dados_detectados": {}}
    writes = []

    def merge(token, patch):
        store["dados_detectados"] = {**store["dados_detectados"], **patch}
        writes.append(patch)
        return store

    @contextmanager
    def bound(token):
        yield {}

    monkeypatch.setattr(art_jobs, "get_by_token", lambda token: store)
    monkeypatch.setattr(art_jobs, "merge_dados", merge)
    monkeypatch.setattr(art_jobs, "update_session", lambda token, fields: writes.append(("plan_content", fields)))
    monkeypatch.setattr(art_jobs, "bound_session", bound)
    monkeypatch.setattr(art_jobs, "regenerate_creative", render)
    return store, writes


def _start(**kw):
    return art_jobs.start("tok", {"sections": [1]}, references=[], channels=[], count=3, shape="vertical", **{"plan_mode": "one_page", **kw})


def test_success_saves_plan_and_walks_the_steps(monkeypatch):
    def render(folha, **kw):
        kw["on_variants"]()
        return {**folha, "arte": "nova"}

    store, writes = _setup(monkeypatch, render)
    _start()
    steps = [w[art_jobs.KEY]["step"] for w in writes if isinstance(w, dict) and art_jobs.KEY in w]
    assert steps == ["prep", "arts", "variants", "done"]
    assert store["dados_detectados"]["folha"]["arte"] == "nova"
    assert ("plan_content", {"plan_content": {"sections": [1], "arte": "nova"}}) in writes
    assert art_jobs.job_view(store)["status"] == "done"


def test_failure_keeps_the_real_reason(monkeypatch):
    def render(folha, **kw):
        raise OpenRouterError("Créditos do OpenRouter esgotados.")

    store, _ = _setup(monkeypatch, render)
    _start()
    job = art_jobs.job_view(store)
    assert job["status"] == "error" and job["error"] == "Créditos do OpenRouter esgotados."


def test_internal_error_names_the_type():
    assert art_jobs.error_message(KeyError("url")) == "Erro interno ao gerar as artes (KeyError: 'url')."


def test_running_job_is_not_started_twice_and_stale_one_is_released(monkeypatch):
    calls = []
    store, _ = _setup(monkeypatch, lambda folha, **kw: calls.append(1) or folha)
    now = datetime.now(timezone.utc)
    store["dados_detectados"][art_jobs.KEY] = {"status": "running", "step": "arts", "updatedAt": now.isoformat()}
    assert _start()["step"] == "arts" and calls == []
    store["dados_detectados"][art_jobs.KEY]["updatedAt"] = (now - timedelta(minutes=20)).isoformat()
    assert art_jobs.job_view(store)["status"] == "error"
    _start()
    assert calls == [1]


def test_job_of_a_dead_worker_is_released_at_once(monkeypatch):
    # Worker reciclado pelo max_requests mata a thread; a tela não pode esperar os 15 minutos.
    import socket
    now = datetime.now(timezone.utc).isoformat()
    row = {"dados_detectados": {art_jobs.KEY: {"status": "running", "updatedAt": now, "host": socket.gethostname(), "pid": 2**22 + 12345}}}
    monkeypatch.setattr(art_jobs.os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))
    assert art_jobs.job_view(row)["status"] == "error"
    row["dados_detectados"][art_jobs.KEY]["host"] = "outra-maquina"
    assert art_jobs.job_view(row)["status"] == "running"
