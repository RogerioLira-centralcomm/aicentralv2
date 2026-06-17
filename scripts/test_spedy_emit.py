"""Teste pontual: conexão Spedy + emissão NFS-e sandbox para um PI."""
import json
import sys
import time

from aicentralv2 import create_app, db
from aicentralv2.services.spedy_service import (
    SpedyAPIError,
    SpedyService,
    build_spedy_customer_from_pi,
    build_spedy_transaction_id,
    extract_invoice_from_order,
    map_spedy_invoice_to_nf_update,
    parse_pi_amount,
)


def pick_pi(rows):
    for row in rows:
        pi = db.obter_cadu_pi_por_id(row["id_pi"])
        amount = parse_pi_amount(pi)
        cliente = db.obter_cliente_por_id(pi["id_cliente"])
        cnpj = "".join(ch for ch in (cliente.get("cnpj") or "") if ch.isdigit())
        if amount <= 0 or len(cnpj) != 14:
            continue
        contato = None
        if pi.get("contato_fin_cliente"):
            contato = db.obter_contato_por_id(pi["contato_fin_cliente"])
        try:
            customer = build_spedy_customer_from_pi(pi, cliente, contato)
        except SpedyAPIError as exc:
            print("Customer build failed for PI", row["id_pi"], exc)
            continue
        return row, pi, amount, customer
    return None, None, 0, None


def main():
    app = create_app()
    with app.app_context():
        key = app.config.get("SPEDY_API_KEY", "")
        base = app.config.get("SPEDY_API_BASE_URL", "")
        print("SPEDY_API_KEY:", f"SET ({len(key)} chars)" if key else "MISSING")
        print("SPEDY_API_BASE_URL:", base)

        spedy = SpedyService()
        try:
            companies = spedy.test_connection()
            items = companies.get("items") or [] if isinstance(companies, dict) else []
            print("Connection OK, companies count:", len(items))
            if items:
                c0 = items[0]
                print(
                    "First company:",
                    c0.get("name") or c0.get("legalName"),
                    "| id:",
                    c0.get("id"),
                )
        except SpedyAPIError as exc:
            print("Connection FAILED:", exc)
            return 1

        conn = db.get_db()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id_pi, p.codigo_pi_cc, p.codigo_pi_ag, p.id_cliente,
                       nf.id AS nf_id, nf.spedy_status
                FROM cadu_pi p
                LEFT JOIN cadu_pi_nota_fiscal nf ON nf.id_pi = p.id_pi
                WHERE p.id_cliente IS NOT NULL
                  AND COALESCE(nf.spedy_status, '') <> 'authorized'
                ORDER BY p.id_pi DESC
                LIMIT 50
                """
            )
            rows = cur.fetchall()

        chosen, pi, amount, customer = pick_pi(rows)
        if not chosen:
            print("No suitable PI found")
            return 2

        id_pi = chosen["id_pi"]
        codigo_pi = pi.get("codigo_pi_cc") or pi.get("codigo_pi_ag")
        print(
            "Selected PI:",
            id_pi,
            codigo_pi,
            "amount:",
            amount,
            "phone:",
            customer.get("phone"),
            "nf:",
            chosen.get("nf_id"),
            "spedy:",
            chosen.get("spedy_status"),
        )

        transaction_id = build_spedy_transaction_id(id_pi, codigo_pi)
        print("Emitting order transaction_id:", transaction_id)
        print("Customer:", customer["name"], customer["federalTaxNumber"])

        def emit_with_customer(cust):
            return spedy.emit_order(
                transaction_id=build_spedy_transaction_id(id_pi, codigo_pi),
                customer=cust,
                amount=amount,
                observation=f"TESTE PI {codigo_pi or id_pi}",
            )

        try:
            order = emit_with_customer(customer)
        except SpedyAPIError as exc:
            if "telefone" in str(exc).lower():
                print("Retry with fallback phone 5531999999999")
                customer["phone"] = "5531999999999"
                customer["mobilePhone"] = "5531999999999"
                try:
                    order = emit_with_customer(customer)
                except SpedyAPIError as exc2:
                    print("Emit FAILED:", exc2, "| status:", exc2.status_code)
                    return 3
            else:
                print("Emit FAILED:", exc, "| status:", exc.status_code)
                return 3

        print("Order response id:", order.get("id"))
        spedy_info = extract_invoice_from_order(order) or {}
        print("Spedy info:", json.dumps(spedy_info, default=str))

        inv_id = spedy_info.get("spedy_invoice_id")
        inv = {}
        if inv_id:
            for i in range(12):
                inv = spedy.get_service_invoice(str(inv_id))
                status = (inv.get("status") or "").lower()
                msg = (inv.get("processingDetail") or {}).get("message")
                print(
                    f"Poll {i + 1}: status={status} msg={msg} number={inv.get('number')}"
                )
                if status in ("authorized", "rejected", "denied", "canceled"):
                    break
                time.sleep(3)
            update = map_spedy_invoice_to_nf_update(inv)
            print("NF update fields:", json.dumps(update, default=str))

    return 0


if __name__ == "__main__":
    sys.exit(main())
