from aicentralv2.creative_lab import runner


class FakeRepository:
    def __init__(self, queued, unevaluated=(), counts=None):
        self.queued = list(queued)
        self.unevaluated = list(unevaluated)
        self.counts = counts or {"queued": len(queued), "running": 0}

    def next_queued(self, _client):
        return self.queued[0] if self.queued else None

    def unevaluated_runs(self, _client, **_kwargs):
        return list(self.unevaluated)

    def pending_counts(self, _client):
        return self.counts


def test_drain_runs_the_queue_in_the_order_the_repository_gives_then_evaluates_leftovers(monkeypatch):
    repo = FakeRepository([30, 31], unevaluated=[7])
    monkeypatch.setattr(runner, "repository", repo)
    executed, evaluated = [], []

    def execute(_client, run_id):
        executed.append(run_id)
        repo.queued.remove(run_id)

    monkeypatch.setattr(runner, "execute_run", execute)
    monkeypatch.setattr(runner.evaluation, "evaluate_run", lambda _client, run_id: (evaluated.append(run_id), repo.unevaluated.remove(run_id)))
    runner._drain(1)
    assert executed == [30, 31]
    assert evaluated == [7]


def test_drain_does_not_spin_on_a_run_that_stays_queued(monkeypatch):
    repo = FakeRepository([5])
    monkeypatch.setattr(runner, "repository", repo)
    calls = []
    monkeypatch.setattr(runner, "execute_run", lambda _client, run_id: calls.append(run_id))  # never leaves the queue
    runner._drain(1)
    assert calls == [5]


def test_an_orphaned_queue_gets_a_worker_again(monkeypatch):
    started = []
    monkeypatch.setattr(runner, "repository", FakeRepository([1, 2]))
    monkeypatch.setattr(runner, "start_worker", lambda client, ids=None: started.append(client))
    assert runner.resume_if_orphaned(9) is True
    assert started == [9]


def test_a_queue_with_a_run_in_progress_is_left_alone(monkeypatch):
    started = []
    monkeypatch.setattr(runner, "repository", FakeRepository([1, 2], counts={"queued": 2, "running": 1}))
    monkeypatch.setattr(runner, "start_worker", lambda client, ids=None: started.append(client))
    assert runner.resume_if_orphaned(9) is False and not started


def test_an_empty_queue_starts_nothing(monkeypatch):
    started = []
    monkeypatch.setattr(runner, "repository", FakeRepository([]))
    monkeypatch.setattr(runner, "start_worker", lambda client, ids=None: started.append(client))
    assert runner.resume_if_orphaned(9) is False and not started
