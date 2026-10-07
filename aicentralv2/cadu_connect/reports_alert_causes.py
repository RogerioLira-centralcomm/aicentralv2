"""Possible causes of an alert, from what the product already knows about the same period. No model guesses here.

Each cause is a fact that can be checked in the screens (a URL that was down, a slower response, a tracking gap, less traffic) and
that happened in the same window as the alert. A cause only says "this also happened", never "this is why"; the panel words it so.
"""
DOWN_BELOW = 95.0         # a monitored URL under this daily availability counts as having been down
SLOWER_RATIO = 1.5        # response time this much above the previous week...
SLOWER_MIN_MS = 500       # ...and at least this many milliseconds above it
TRAFFIC_SHIFT = 20.0      # percent change in sessions that is worth mentioning


def _window(rows, today, start, end):
    return [row for row in rows if start <= (today - row['day']).days <= end and row['checks']]


def url_causes(rows, today):
    """rows: daily monitor records of one URL (day, checks, online, duration_ms_sum). Compares the last 7 days with the 7 before."""
    current, previous = _window(rows, today, 0, 6), _window(rows, today, 7, 13)
    causes = []
    down = [row for row in current if 100 * row['online'] / row['checks'] < DOWN_BELOW]
    if down:
        worst = min(100 * row['online'] / row['checks'] for row in down)
        causes.append(f"A URL ficou abaixo de {DOWN_BELOW:.0f}% de disponibilidade em {len(down)} {'dia' if len(down) == 1 else 'dias'} dos últimos 7 (pior dia: {worst:.0f}%).")
    if current and previous:
        now_ms = sum(row['duration_ms_sum'] for row in current) / sum(row['checks'] for row in current)
        before_ms = sum(row['duration_ms_sum'] for row in previous) / sum(row['checks'] for row in previous)
        if before_ms > 0 and now_ms >= before_ms * SLOWER_RATIO and now_ms - before_ms >= SLOWER_MIN_MS:
            causes.append(f'O tempo de resposta médio da URL subiu de {before_ms:.0f} ms para {now_ms:.0f} ms (+{100 * (now_ms - before_ms) / before_ms:.0f}%).')
    return causes


def host_causes(rows, day, today):
    """rows: daily monitor records of every URL of the site's host; looks at one day (the one an anomaly refers to)."""
    down = [row for row in rows if row['day'] == day and row['checks'] and 100 * row['online'] / row['checks'] < DOWN_BELOW]
    if not down:
        return []
    return [f"{len(down)} {'URL monitorada ficou' if len(down) == 1 else 'URLs monitoradas ficaram'} abaixo de {DOWN_BELOW:.0f}% de disponibilidade em {day.strftime('%d/%m')}."]


def traffic_cause(current_sessions, previous_sessions):
    if not previous_sessions or current_sessions is None:
        return []
    change = 100 * (current_sessions - previous_sessions) / previous_sessions
    if change <= -TRAFFIC_SHIFT:
        return [f'O tráfego da página caiu {abs(change):.0f}% no período (de {previous_sessions} para {current_sessions} sessões); parte da queda de conversões pode vir daí.']
    return []


def tracking_cause(active):
    return ['A Super Tag ficou sem enviar eventos há pouco tempo; os números do período podem estar incompletos.'] if active else []


def combine(*groups):
    """Concatenate, keeping order and dropping repeats."""
    seen, out = set(), []
    for group in groups:
        for cause in group:
            if cause not in seen:
                seen.add(cause)
                out.append(cause)
    return out

