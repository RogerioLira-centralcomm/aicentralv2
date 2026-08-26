#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste pontual de envio de e-mail via API Brevo (Python direto, sem Make.com).

Uso (raiz do repo):
  python scripts/test_brevo_email.py --list-templates
  python scripts/test_brevo_email.py --template reset-senha --to seu@email.com --dry-run
  python scripts/test_brevo_email.py --template reset-senha --to seu@email.com --name "Nome Teste"

Formulário web: http://localhost:5000/teste-brevo
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

load_dotenv(os.path.join(ROOT, ".env"))
load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Envia e-mail de teste via API Brevo (sem Make.com)."
    )
    parser.add_argument("--template", help="Chave do template")
    parser.add_argument("--to", help="E-mail destinatário")
    parser.add_argument("--name", default="Teste Brevo", help="Nome do destinatário")
    parser.add_argument("--dry-run", action="store_true", help="Só renderiza, não envia")
    parser.add_argument("--list-templates", action="store_true", help="Lista templates")
    args = parser.parse_args()

    from aicentralv2 import create_app
    from aicentralv2.services.brevo_test_templates import (
        BREVO_TEST_TEMPLATE_LABELS,
        build_brevo_test_templates,
        run_brevo_email_test,
    )

    to_email = (args.to or "").strip()
    to_name = (args.name or "Teste Brevo").strip()
    templates = build_brevo_test_templates(to_email or "teste@example.com", to_name)

    if args.list_templates:
        print("Templates disponíveis:\n")
        for chave in sorted(templates):
            label = BREVO_TEST_TEMPLATE_LABELS.get(chave, chave)
            cfg = templates[chave]
            pasta = cfg["template_folder"].replace("emails/", "")
            print(f"  {chave:<28} {label} ({pasta})")
        return 0

    if not args.template:
        parser.error("Informe --template ou use --list-templates")
    if args.template not in templates:
        print(f"ERRO: template desconhecido: {args.template!r}")
        return 1
    if not to_email:
        parser.error("--to é obrigatório")

    app = create_app()
    with app.app_context(), app.test_request_context():
        result = run_brevo_email_test(
            template_key=args.template,
            to_email=to_email,
            to_name=to_name,
            dry_run=args.dry_run,
        )

    print("=" * 60)
    print(f"Template: {result.get('template_key')} -> {result.get('template_name')}")
    print(f"Assunto:  {result.get('subject')}")
    print(f"Para:     {result.get('to_name')} <{result.get('to_email')}>")
    print(f"Remetente: {result.get('sender_name')} <{result.get('sender_email')}>")
    if result.get("preview_html"):
        print(f"\nHTML (início): {result['preview_html'][:400]}...")

    if result.get("success"):
        if result.get("dry_run"):
            print("\nDRY-RUN: nenhum e-mail enviado.")
        else:
            print(f"\nSUCESSO: messageId={result.get('messageId')}")
        return 0

    print("\nFALHA:")
    if result.get("status_code"):
        print(f"  status: {result.get('status_code')}")
    print(f"  {result.get('user_message') or result.get('error')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
