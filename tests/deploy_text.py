"""Texto do deploy para testes: o script e os passos de migrations/ORDER.txt, no formato antigo do script."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def deploy_text(root=ROOT):
    root = Path(root)
    steps = [
        f'"$VENV_PYTHON" {line.strip().lstrip("?")}'
        for line in (root / "migrations" / "ORDER.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    script = (root / "deploy.sh").read_text(encoding="utf-8")
    # Os passos entram onde o script chama o runner, para manter a ordem relativa ao resto do deploy.
    return script.replace('"$VENV_PYTHON" migrations/run_deploy_migrations.py', "\n".join(steps))
