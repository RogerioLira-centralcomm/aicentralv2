"""Audit a tenant's project knowledge sources; optionally repair missing indexes.

Usage:
  python scripts/audit_project_knowledge.py --client-id 42 --project-id UUID
  python scripts/audit_project_knowledge.py --client-id 42 --project-id UUID --repair --user-id 7

The default is read-only. Repair uses the existing source reindexer, which
checks the content hash and charges only when a rebuild is needed.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from aicentralv2 import create_app
from aicentralv2.db import get_db
from aicentralv2.cadu_workspace import project_index_service


def inventory(client_id: int, project_id: str) -> list[dict]:
    with get_db().cursor() as cursor:
        cursor.execute("""SELECT s.id, s.nome_arquivo AS name, s.purpose, s.indexing_status,
                                 s.erro_msg AS error, s.word_count,
                                 LENGTH(COALESCE(s.extracted_text,'')) AS extracted_chars,
                                 COUNT(c.id) AS chunk_count
                            FROM cadu_ci_projeto_arquivos s
                       LEFT JOIN cadu_ci_chunks c ON c.arquivo_id=s.id
                             AND c.projeto_id=s.projeto_id AND c.id_cliente=s.id_cliente
                           WHERE s.id_cliente=%s AND s.projeto_id=%s
                        GROUP BY s.id ORDER BY s.id""", (client_id, project_id))
        return [dict(row) for row in cursor.fetchall()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", type=int, required=True)
    parser.add_argument("--project-id", required=True, help="Native project UUID, without ci: prefix")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--user-id", type=int, help="Actor billed for embedding tokens; required for repair")
    args = parser.parse_args()
    if args.client_id < 1 or (args.repair and not args.user_id):
        parser.error("client-id must be positive and --repair requires --user-id")
    app = create_app()
    with app.app_context():
        with get_db().cursor() as cursor:
            cursor.execute("SELECT id FROM cadu_ci_projetos WHERE id=%s AND id_cliente=%s AND status <> 'deletado'",
                           (args.project_id, args.client_id))
            if not cursor.fetchone():
                parser.error("Project does not exist in this client")
        rows = inventory(args.client_id, args.project_id)
        repair_candidates = 0
        for row in rows:
            repairable = row["purpose"] == "knowledge_source" and (
                row["indexing_status"] != "completed" or int(row["chunk_count"] or 0) == 0
            )
            repair_candidates += int(repairable)
            result = {**row, "repairable": repairable}
            if args.repair and repairable:
                try:
                    result["repair"] = project_index_service.reindex_source(
                        args.client_id, args.project_id, int(row["id"]), args.user_id,
                    )
                except Exception as exc:
                    result["repair"] = {"status": "failed", "error_type": type(exc).__name__}
            print(json.dumps(result, ensure_ascii=False, default=str))
        if args.repair:
            print(json.dumps({"summary": "repair_complete", "sources": len(rows), "candidates": repair_candidates, "remaining": sum(
                row["purpose"] == "knowledge_source" and (row["indexing_status"] != "completed" or not row["chunk_count"])
                for row in inventory(args.client_id, args.project_id)
            )}, ensure_ascii=False))
        else:
            print(json.dumps({"summary": "audit_complete", "sources": len(rows),
                              "repair_candidates": repair_candidates}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
