from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / 'aicentralv2'
LEDGER_BOUNDARIES = {
    PACKAGE / 'cadu_credit_connector.py',
    PACKAGE / 'cadu_tool_billing.py',
}


def test_product_modules_do_not_write_global_credit_tables_directly():
    forbidden = ('INSERT INTO cadu_tools_token_usage', 'UPDATE cadu_credits_extras')
    violations = []
    for path in PACKAGE.rglob('*.py'):
        if path in LEDGER_BOUNDARIES:
            continue
        source = path.read_text(encoding='utf-8')
        if any(statement in source for statement in forbidden):
            violations.append(str(path.relative_to(ROOT)))
    assert violations == []


def test_provider_cost_conversion_stays_behind_credit_connector():
    violations = []
    for path in PACKAGE.rglob('*.py'):
        if path in LEDGER_BOUNDARIES:
            continue
        source = path.read_text(encoding='utf-8')
        if 'charge_from_provider(' in source:
            violations.append(str(path.relative_to(ROOT)))
    assert violations == []
