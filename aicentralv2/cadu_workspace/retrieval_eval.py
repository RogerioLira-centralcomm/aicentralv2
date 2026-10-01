"""Measure project retrieval quality against hand-labelled questions.

Each case names text that a good answer must be grounded in. A result counts as
a hit when any expected string appears in its title or content, so cases do not
break when chunk boundaries move.
"""
from __future__ import annotations

import json
import statistics
import unicodedata
from pathlib import Path
from time import perf_counter

import click
from flask.cli import with_appcontext

from .agent_v2.contracts import RequestContext
from .agent_v2.retrieval_query import retrieval_query

FIELDS = ("title", "label", "fonte", "trecho", "display_value", "description")


def _fold(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(text.lower().split())


def load_cases(path: str) -> list[dict]:
    cases = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        case = json.loads(line)
        if not case.get("question") or not case.get("expect_any"):
            raise click.ClickException(f"Linha {number}: informe question e expect_any.")
        case.setdefault("id", f"case-{number}")
        cases.append(case)
    return cases


def first_hit_rank(results: list[dict], expected: list[str]) -> int | None:
    """1-based rank of the first result containing any expected text, else None."""
    needles = [_fold(item) for item in expected if str(item).strip()]
    for rank, row in enumerate(results, start=1):
        haystack = _fold(" ".join(str(row.get(name) or "") for name in FIELDS))
        if any(needle in haystack for needle in needles):
            return rank
    return None


def summarize(ranks: list[int | None], latencies_ms: list[float], ks=(3, 5, 8)) -> dict:
    total = len(ranks)
    if not total:
        return {"cases": 0}
    summary = {"cases": total, "mrr": round(sum(1 / rank for rank in ranks if rank) / total, 3),
               "not_found": sum(rank is None for rank in ranks)}
    for k in ks:
        summary[f"recall@{k}"] = round(sum(bool(rank and rank <= k) for rank in ranks) / total, 3)
    if latencies_ms:
        ordered = sorted(latencies_ms)
        summary["latency_ms_p50"] = round(statistics.median(ordered))
        summary["latency_ms_p95"] = round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))])
    return summary


def run_cases(cases: list[dict], *, client_id: int, user_id: int, rerank: bool | None) -> tuple[list[dict], dict]:
    from .mcp.registry import load_builtin_tools

    registry = load_builtin_tools()
    rows, ranks, latencies = [], [], []
    for case in cases:
        context = RequestContext(client_id=client_id, user_id=user_id, conversation_id=None,
                                 surface="workspace", project_ref=case["project_ref"],
                                 capabilities=("workspace",))
        query = retrieval_query(case["question"], case.get("history") or "")
        arguments = {"query": query["query"], "mode": "search"}
        if rerank is not None:
            arguments["rerank"] = rerank
        started = perf_counter()
        try:
            found = registry.execute("workspace.search_project_content", arguments, context)
            results, error = found.get("results") or [], ""
        except Exception as exc:
            results, error = [], type(exc).__name__
        latency = (perf_counter() - started) * 1000
        rank = first_hit_rank(results, case["expect_any"])
        ranks.append(rank)
        latencies.append(latency)
        rows.append({"id": case["id"], "question": case["question"], "query": query["query"],
                     "strategy": query["strategy"], "rank": rank, "results": len(results),
                     "latency_ms": round(latency), "error": error})
    return rows, summarize(ranks, latencies)


@click.command("cadu-eval-retrieval")
@click.option("--cases", "cases_path", required=True, type=click.Path(exists=True, dir_okay=False),
              help="Arquivo JSONL com os casos (veja docs/cadu-eval/retrieval-cases.example.jsonl).")
@click.option("--client-id", required=True, type=int)
@click.option("--user-id", required=True, type=int, help="Usuário com acesso aos projetos dos casos.")
@click.option("--compare-rerank/--no-compare-rerank", default=False,
              help="Roda duas vezes: sem e com reranking.")
@click.option("--report", type=click.Path(dir_okay=False), default=None, help="Grava o relatório JSON.")
@with_appcontext
def eval_command(cases_path, client_id, user_id, compare_rerank, report):
    """Mede Recall@k e MRR da busca de contexto do projeto."""
    cases = load_cases(cases_path)
    runs = {"rerank_off": False, "rerank_on": True} if compare_rerank else {"atual": None}
    output = {}
    for name, flag in runs.items():
        rows, summary = run_cases(cases, client_id=client_id, user_id=user_id, rerank=flag)
        output[name] = {"summary": summary, "cases": rows}
        click.echo(f"\n== {name} ==\n" + json.dumps(summary, ensure_ascii=False))
        for row in rows:
            marker = f"#{row['rank']}" if row["rank"] else "NÃO ENCONTRADO"
            click.echo(f"  {row['id']:<24} {marker:<16} {row['results']:>2} resultados  {row['latency_ms']} ms"
                       + (f"  erro={row['error']}" if row["error"] else ""))
    if report:
        Path(report).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        click.echo(f"\nRelatório gravado em {report}")
