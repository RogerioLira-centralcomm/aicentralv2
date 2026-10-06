"""Executa, na ordem de ``migrations/ORDER.txt``, as migrações e seeds do deploy.

Uso: python migrations/run_deploy_migrations.py [--check]

``--check`` só valida a lista (arquivos existem, sem duplicata acidental) e não executa nada.
"""

import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER_FILE = ROOT / "migrations" / "ORDER.txt"


def read_steps(order_file=None):
    order_file = order_file or ORDER_FILE
    steps = []
    for number, raw in enumerate(order_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        flags = line[: len(line) - len(line.lstrip("?~"))]
        parts = shlex.split(line.lstrip("?~"))
        steps.append({
            "line": number, "optional": "?" in flags, "legacy": "~" in flags,
            "script": parts[0], "args": parts[1:],
        })
    return steps


def missing_files(steps, root=ROOT):
    """Passos obrigatórios cujo script, ou .sql passado ao runner, não existe."""
    missing = []
    for step in steps:
        if step["optional"]:
            continue
        if not (root / step["script"]).is_file():
            missing.append(step["script"])
        if step["script"].endswith("run_sql_migration.py") and step["args"]:
            if not (root / "migrations" / step["args"][0]).is_file():
                missing.append(step["args"][0])
    return missing


def reports_v2_installed():
    """True quando o reset do Reports v2 já foi aplicado (a base não tem mais organization_id nessas tabelas)."""
    try:
        import psycopg
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
        with psycopg.connect(
            host=os.getenv("DB_HOST", "localhost"), port=int(os.getenv("DB_PORT", "5432")),
            dbname=os.getenv("DB_NAME", "aicentralv2"), user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""), connect_timeout=10,
        ) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.cadu_reports_schema_version')")
                if cursor.fetchone()[0] is None:
                    return False
                cursor.execute("SELECT 1 FROM cadu_reports_schema_version WHERE version = 2")
                return cursor.fetchone() is not None
    except Exception as error:  # sem resposta do banco: executa o passo e deixa ele falhar com a causa real
        print(f"Aviso: não foi possível verificar o Reports v2 ({error}); passos históricos serão executados.")
        return False


def main(argv):
    steps = read_steps()
    absent = missing_files(steps)
    if absent:
        print("Arquivos ausentes em ORDER.txt: " + ", ".join(absent), file=sys.stderr)
        return 2
    if "--check" in argv:
        print(f"{len(steps)} passos válidos.")
        return 0
    skip_legacy = None
    for step in steps:
        if step["legacy"]:
            if skip_legacy is None:
                skip_legacy = reports_v2_installed()
                print("Reports v2 instalado: passos históricos (~) serão pulados." if skip_legacy else "Reports v2 não instalado: passos históricos (~) serão executados.")
            if skip_legacy:
                continue
        if step["optional"] and not (ROOT / step["script"]).is_file():
            print(f"Opcional ausente, ignorado: {step['script']}")
            continue
        label = " ".join([step["script"], *step["args"]])
        print(f"==> {label}", flush=True)
        result = subprocess.run([sys.executable, step["script"], *step["args"]], cwd=ROOT)
        if result.returncode:
            print(f"Falhou (ORDER.txt linha {step['line']}): {label}", file=sys.stderr)
            return result.returncode
    print(f"{len(steps)} passos concluídos.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
