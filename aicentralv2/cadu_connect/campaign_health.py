"""Explainable health signals; callers provide reviewed, comparable data only."""
from decimal import Decimal


def assess(*, elapsed_pct, delivered_pct, coverage_pct, days_remaining):
    elapsed, delivered, coverage = map(lambda value: Decimal(str(value)), (elapsed_pct, delivered_pct, coverage_pct))
    gap = delivered - elapsed
    if coverage < 70:
        state, reason = 'Sem leitura', 'Cobertura de dados insuficiente para avaliar o ritmo.'
    elif gap >= 5:
        state, reason = 'Saudável', 'Entrega está acima do ritmo esperado para o período.'
    elif gap >= -5:
        state, reason = 'Atenção', 'Entrega está próxima do ritmo esperado; acompanhe a próxima atualização.'
    else:
        state, reason = 'Risco', 'Entrega está abaixo do ritmo esperado para o período.'
    estimate = None if elapsed == 0 else (delivered / elapsed * 100)
    return {'state': state, 'reason': reason, 'pace_gap': str(gap),
            'estimated_goal_pct': str(estimate) if estimate is not None else None,
            'days_remaining': max(0, int(days_remaining))}
