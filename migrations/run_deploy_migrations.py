"""Executa, na ordem de ``migrations/ORDER.txt``, as migrações e seeds do deploy.

Uso: python migrations/run_deploy_migrations.py [--check]

``--check`` só valida a lista (arquivos existem, sem duplicata acidental) e não executa nada.
"""

import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORDER_FILE = ROOT / "migrations" / "ORDER.txt"


def read_steps(order_file=ORDER_FILE):
    steps = []
    for number, raw in enumerate(order_file.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        optional = line.startswith("?")
        parts = shlex.split(line.lstrip("?"))
        steps.append({"line": number, "optional": optional, "script": parts[0], "args": parts[1:]})
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


def main(argv):
    steps = read_steps()
    absent = missing_files(steps)
    if absent:
        print("Arquivos ausentes em ORDER.txt: " + ", ".join(absent), file=sys.stderr)
        return 2
    if "--check" in argv:
        print(f"{len(steps)} passos válidos.")
        return 0
    for step in steps:
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
