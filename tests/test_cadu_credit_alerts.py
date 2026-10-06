from unittest import mock

from flask import Flask

from aicentralv2 import cadu_credit_alerts as alerts


def bal(total, extras=0, active=False, f_total=100_000, f_avail=0):
    return {"franchise": {"active": active, "total": f_total, "available": f_avail if active else 0,
                          "cycle_start": "2026-10-01", "renews_on": "2026-11-01"},
            "extras": {"available": extras}, "total_available": total}


def test_legacy_low_and_empty_use_packages_cta_and_tokens():
    low = alerts.decide_alert(bal(10_000))
    assert low["key"] == "low:2026-10-01" and low["cta_path"] == "/workspace/app/creditos"
    assert "tokens" in low["description"] and "crédito" not in low["description"]
    empty = alerts.decide_alert(bal(0))
    assert empty["kind"] == "empty" and empty["cta_path"] == "/workspace/app/creditos"
    assert alerts.decide_alert(bal(90_000)) is None


def test_franchise_low_and_empty_point_to_plans():
    low = alerts.decide_alert(bal(15_000, active=True, f_avail=15_000))
    assert low["kind"] == "franchise_low" and low["cta_path"] == "/workspace/app/planos"
    ended = alerts.decide_alert(bal(50_000, extras=50_000, active=True, f_avail=0))
    assert ended["kind"] == "franchise_empty" and "2026-11-01" in ended["description"]
    pk = alerts.decide_alert(bal(5_000, extras=5_000, active=True, f_avail=0))
    assert pk["kind"] == "packages_low" and pk["cta_path"] == "/workspace/app/creditos"
    assert alerts.decide_alert(bal(0, active=True))["kind"] == "empty"
    assert alerts.decide_alert(bal(80_000, active=True, f_avail=80_000)) is None


def test_key_changes_each_cycle():
    a = bal(0)
    b = bal(0); b["franchise"]["cycle_start"] = "2026-11-01"
    assert alerts.decide_alert(a)["key"] != alerts.decide_alert(b)["key"]


def _conn(created):
    cur = mock.MagicMock()
    cur.fetchone.side_effect = [{"table_name": "cadu_credit_alerts"}, created]
    conn = mock.MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def test_notify_sends_once_and_mail_failure_is_swallowed():
    app = Flask(__name__)
    conn, cur = _conn({"id": 1})
    svc = mock.MagicMock()
    svc.enviar_email_com_template.side_effect = RuntimeError("brevo down")
    with app.app_context(), \
         mock.patch("aicentralv2.cadu_plan_allowance.get_balance", return_value=bal(0)), \
         mock.patch("aicentralv2.db.get_db", return_value=conn), \
         mock.patch("aicentralv2.db.obter_contatos_por_cliente",
                    return_value=[{"status": True, "user_type": "admin", "email": "a@x.com"}]), \
         mock.patch.object(alerts, "_enabled", return_value=True), \
         mock.patch.object(alerts, "get_brevo_product_service", return_value=svc), \
         mock.patch.object(alerts, "product_email_brand", return_value={}), \
         mock.patch.object(alerts, "product_url", side_effect=lambda p, path: path):
        alerts.notify_balance(7, usage_id=3)  # não levanta
    params = svc.enviar_email_com_template.call_args.kwargs["params"]
    assert params["CTA_URL"] == "/workspace/app/creditos" and "tokens" in params["TITLE"]
    assert cur.execute.call_args_list[1].args[1][1] == "empty:2026-10-01"


def test_notify_skips_mail_when_already_alerted():
    app = Flask(__name__)
    conn, _ = _conn(None)
    svc = mock.MagicMock()
    with app.app_context(), \
         mock.patch("aicentralv2.cadu_plan_allowance.get_balance", return_value=bal(0)), \
         mock.patch("aicentralv2.db.get_db", return_value=conn), \
         mock.patch.object(alerts, "_enabled", return_value=True), \
         mock.patch.object(alerts, "get_brevo_product_service", return_value=svc):
        alerts.notify_balance(7)
    svc.enviar_email_com_template.assert_not_called()
