"""Quanto tempo uma busca do Radar poupou: estimativa simples e explicável, no mesmo molde do plano.

Cada atividade tem o tempo que um planejador costuma gastar fazendo à mão. A busca soma só o que o Radar de fato
entregou: se não saiu nenhum ângulo, não há tempo poupado a mostrar. Os números são referência interna e aparecem
como estimativa, com a conta aberta.
"""
from __future__ import annotations

from ..cadu_planner.time_saved import label

# Minutos de trabalho manual por atividade: (minutos, descrição, se é por item).
MANUAL_MINUTES = {
    'buzz': (30, 'Pesquisar o que está em alta em portais, redes e buscas', False),
    'check': (5, 'Abrir cada fonte e confirmar data e link', True),
    'angle': (15, 'Escrever cada ângulo: gancho, por que agora, formatos e canais', True),
}


def estimate(buzz_count: int, angle_count: int) -> dict:
    """Minutos poupados com a conta por atividade. Sem ângulos, nada é poupado."""
    if angle_count <= 0:
        return {'minutes': 0, 'label': '', 'lines': [], 'note': ''}
    counts = {'buzz': 1, 'check': max(0, int(buzz_count)), 'angle': int(angle_count)}
    lines = []
    for key, (minutes, text, per_item) in MANUAL_MINUTES.items():
        count = counts[key]
        if count > 0:
            lines.append({'key': key, 'label': text, 'count': count if per_item else 1, 'minutes': minutes * count})
    total = sum(line['minutes'] for line in lines)
    return {'minutes': total, 'label': label(total), 'lines': lines,
            'note': 'Estimativa com tempos de referência do trabalho manual de pesquisa e ideação.'}


def account(saved: dict) -> str:
    """A conta em uma linha, para o e-mail e para a dica da tela."""
    parts = []
    for line in saved.get('lines') or []:
        parts.append(f"{label(line['minutes'])} {line['label'][0].lower()}{line['label'][1:]}"
                     + (f" (× {line['count']})" if line['count'] > 1 else ''))
    return ' + '.join(parts)
