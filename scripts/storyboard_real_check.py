#!/usr/bin/env python3
"""Verificação REAL do caminho "uma imagem por cena" do storyboard do Vídeo. GASTA CRÉDITOS REAIS.

Rode NO SERVIDOR (as imagens são gravadas em disco local e as linhas de biblioteca/histórico/débito vão para o
banco: rodar da máquina de desenvolvimento deixaria itens apontando para arquivos que o servidor não tem).

    venv/bin/python scripts/storyboard_real_check.py --crm 174 --brand 22 --email voce@empresa.com \
        [--user-id N] [--scenes 3] [--aspect 16:9] [--confirm-real-charge] [--cleanup]

Sem --confirm-real-charge: só lê (saldo, preço por imagem, plano). Com ele: monta o storyboard (texto), gera
--scenes imagens pelas MESMAS views do Studio e confere, para cada uma, débito, histórico e biblioteca. No fim soma
todas as linhas de cobrança criadas (inclui tentativas extras de revisão) e imprime o custo real por cena.
--cleanup remove da biblioteca as cenas de teste (o crédito gasto não volta).
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BRIEFING = ("Anúncio de internet fibra para famílias: 500 mega, instalação rápida, suporte local. "
            "Abrir com uma família na sala, mostrar o roteador e fechar com o convite para falar com a marca.")


def response_data(response):
    """As views devolvem Response (ou tupla com status); extrai o JSON e levanta com a mensagem do erro."""
    status = 200
    if isinstance(response, tuple):
        response, status = response[0], response[1]
    body = response.get_json(silent=True) or {}
    if status >= 400 or body.get("success") is False:
        raise RuntimeError(body.get("error") or f"HTTP {status}")
    return body.get("data", body)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crm", type=int, required=True, help="id do cliente que paga (tbl_cliente.id_cliente)")
    parser.add_argument("--brand", type=int, required=True, help="id da marca no Studio (cx_clients.id) deste cliente")
    parser.add_argument("--user-id", type=int, help="id do contato que dispara (tbl_contato_cliente.id_contato_cliente)")
    parser.add_argument("--email", help="e-mail do contato que dispara; o id é buscado no banco (use --user-id se houver mais de um)")
    parser.add_argument("--scenes", type=int, default=3, choices=range(2, 7))
    parser.add_argument("--aspect", default="16:9")
    parser.add_argument("--confirm-real-charge", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    if not args.user_id and not args.email:
        parser.error("informe --email (ou --user-id) de quem dispara o teste")

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    import psycopg
    from aicentralv2 import create_app
    from aicentralv2.cadu_credit_connector import CaduCreditConnector
    from aicentralv2.creative_media import studio
    from aicentralv2.creative_media.studio_costs import image_credits_by_quality

    app = create_app()
    conn = psycopg.connect(
        host=os.environ["DB_HOST"], port=os.getenv("DB_PORT", "5432"), dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"], password=os.getenv("DB_PASSWORD", ""), connect_timeout=10, autocommit=True,
    )
    cur = conn.cursor()
    cur.execute("SELECT crm_client_id, name FROM cx_clients WHERE id = %s", (args.brand,))
    row = cur.fetchone()
    if not row or int(row[0] or 0) != args.crm:
        sys.exit(f"A marca {args.brand} não pertence ao cliente {args.crm}. Nada foi feito.")
    if not args.user_id:
        cur.execute("SELECT id_contato_cliente, pk_id_tbl_cliente FROM tbl_contato_cliente WHERE lower(email) = lower(%s)", (args.email.strip(),))
        found = cur.fetchall()
        if len(found) != 1:
            sys.exit(f"{len(found)} contatos com o e-mail {args.email}: " + (", ".join(f"id {r[0]} (cliente {r[1]})" for r in found) or "nenhum")
                     + ". Use --user-id com o id certo. Nada foi feito.")
        args.user_id = int(found[0][0])
        print(f"Contato encontrado pelo e-mail: id {args.user_id}")
    cur.execute("SELECT now()")
    started = cur.fetchone()[0]

    with app.app_context():
        credits = CaduCreditConnector()
        balance_before = credits.balance(args.crm)
        price = image_credits_by_quality().get("padrão")
        print(f"Marca: {row[1]} (id {args.brand}) · pagador CRM {args.crm} · saldo {balance_before:,} tokens")
        print(f"Preço de referência por imagem (padrão): {price} créditos · {args.scenes} cenas ({args.aspect})")
        if not args.confirm_real_charge:
            print("\nNada foi gerado. Repita com --confirm-real-charge para gastar créditos reais.")
            return
        if balance_before < (price or 0) * args.scenes * 6:
            sys.exit("Saldo insuficiente para o teste com folga (até 3 tentativas por imagem). Nada foi feito.")

        def call(view, path, payload):
            with app.test_request_context(path, method="POST", json=payload):
                from flask import session
                session["user_id"] = args.user_id
                session["cliente_id"] = args.crm
                return response_data(view())

        text_view = studio.studio_agent_storyboard.__wrapped__.__wrapped__
        image_view = studio.studio_storyboard_image.__wrapped__.__wrapped__
        plan = call(text_view, "/studio/agent/storyboard", {
            "client_id": args.brand, "request_id": f"check-{started:%Y%m%d%H%M%S}-text", "briefing": BRIEFING,
            "duration": args.scenes * 4, "aspect_ratio": args.aspect, "scene_count": args.scenes,
        })
        beats = plan["beats"][:args.scenes]
        print(f"\nStoryboard: {len(beats)} cenas ({plan['model']}); avisos: {plan['warnings'] or 'nenhum'}")

        made, anchor, run_id = [], "", ""
        for index, beat in enumerate(beats):
            data = call(image_view, "/studio/agent/storyboard/image", {
                "client_id": args.brand, "request_id": f"check-{started:%Y%m%d%H%M%S}-{index}",
                "beat": {"visual": beat["visual"], "hold": beat["hold"]}, "index": index, "total": len(beats),
                "aspect_ratio": args.aspect, "anchor_url": anchor, "run_id": run_id,
                "title": f"[Teste storyboard] Cena {index + 1} (pode excluir)",
            })
            anchor = anchor or data["image_url"]
            run_id = run_id or data.get("run_id", "")
            made.append(data)
            print(f"  cena {index + 1}: {data['image_url']} · cobrado {data.get('charged_credits')} créditos")

        # ---- conferência ----
        balance_after = credits.balance(args.crm)
        cur.execute(
            "SELECT etapa, modelo, tokens_cobrados, custo_interno, status FROM cadu_tools_token_usage "
            "WHERE id_cliente = %s AND created_at >= %s ORDER BY id", (args.crm, started))
        usage = cur.fetchall()
        print("\nLinhas de cobrança criadas pelo teste:")
        for stage, model, tokens, cost, status in usage:
            print(f"  {stage or '-':24} {model or '-':34} {tokens!s:>8} tokens · interno {cost} · {status}")
        charged = sum(int(r[2] or 0) for r in usage)
        spent = balance_before - balance_after
        print(f"\nDébito do saldo: {spent:,} tokens · soma das linhas de cobrança: {charged:,} tokens")
        print(f"Custo real por cena (imagens): {sum(int(r[2] or 0) for r in usage if 'image' in str(r[0]).lower() or 'imag' in str(r[0]).lower()) / max(1, len(made)):,.0f} tokens")

        with app.test_request_context("/studio/check", method="POST"):
            from flask import session
            session["user_id"] = args.user_id
            modeling = studio._http()[3]()
            items = modeling.load_format_lab_swap_library({"client_id": args.brand, "media": "image"}, args.user_id)
            listed = {str(item.get("id")) for item in (items.get("items") if isinstance(items, dict) else items) or []}
            history = studio._creation_history()
            owned = history.owned_image_urls(args.brand, [m["image_url"] for m in made]) if history else None
            problems = []
            for number, data in enumerate(made, 1):
                if str(data.get("scene_id")) not in listed:
                    problems.append(f"cena {number}: scene_id {data.get('scene_id')} NÃO está na biblioteca")
                if owned is not None and data["image_url"] not in owned:
                    problems.append(f"cena {number}: imagem NÃO aparece no histórico da marca")
            if not usage:
                problems.append("nenhuma linha de cobrança foi criada")
            if spent <= 0:
                problems.append("o saldo não foi debitado")
            print("\nBiblioteca / histórico / débito:", "OK" if not problems else "")
            for problem in problems:
                print("  ✕", problem)
            if args.cleanup:
                modeling.remove_format_lab_swap_library(
                    {"client_id": args.brand, "ids": [m["scene_id"] for m in made if m.get("scene_id")]}, args.user_id)
                print("Cenas de teste removidas da biblioteca (o gasto permanece).")
        sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
