"""Vital signs of each monitored URL for the "Monitores" tab: current state, response, availability and a pulse of recent readings.

Pure: it reads the last checks of one flow (newest first, as the monitor stores them) and returns one row per page. Nothing
here measures anything new; the flow monitor already records status, HTTP code and response time of every page at each check.
"""
SLOW_MS = 3000            # average response above this puts a page under attention
LOW_UPTIME = 95.0         # availability under this (percent of the recent readings) puts a page under attention
PULSE = 30                # readings kept for the pulse strip
_RANK = {'critical': 0, 'attention': 1, 'stable': 2}


def _vital(state, uptime, average_ms):
    if state == 'offline':
        return 'critical'
    if state != 'online' or (uptime is not None and uptime < LOW_UPTIME) or (average_ms is not None and average_ms > SLOW_MS):
        return 'attention'
    return 'stable'


def url_vitals(flow, checks):
    """flow: {id, name, allowed_host}; checks: [{checked_at, pages:[{host,path,label,status,http_status,duration_ms,detail}]}] newest first."""
    pages = {}
    for check in checks[:PULSE]:
        for page in check.get('pages') or []:
            host, path = (page.get('host') or flow['allowed_host']), page.get('path') or '/'
            pages.setdefault((host, path), []).append({**page, 'checked_at': check['checked_at']})
    rows = []
    for (host, path), readings in pages.items():
        latest = readings[0]
        state = latest.get('status') if latest.get('status') in ('online', 'degraded', 'offline') else 'degraded'
        online = sum(1 for item in readings if item.get('status') == 'online')
        uptime = round(100 * online / len(readings), 1)
        times = [int(item['duration_ms']) for item in readings if item.get('duration_ms') is not None]
        average_ms = round(sum(times) / len(times)) if times else None
        down_since, streak = None, 0
        if state != 'online':
            for item in readings:
                if item.get('status') == 'online':
                    break
                streak, down_since = streak + 1, item['checked_at']
        rows.append({'flow_id': flow['id'], 'flow_name': flow.get('name') or flow['allowed_host'], 'host': host, 'path': path,
                     'label': latest.get('label') or path, 'state': state, 'vital': _vital(state, uptime, average_ms),
                     'http_status': latest.get('http_status'), 'duration_ms': latest.get('duration_ms'), 'average_ms': average_ms,
                     'detail': latest.get('detail'), 'uptime': uptime, 'readings': len(readings), 'streak': streak, 'down_since': down_since,
                     'last_checked_at': latest['checked_at'],
                     'pulse': [item.get('status') if item.get('status') in ('online', 'degraded', 'offline') else 'degraded' for item in reversed(readings)]})
    return sorted(rows, key=lambda row: (_RANK[row['vital']], row['path'], row['host']))


def summarize(rows):
    return {key: sum(1 for row in rows if row['vital'] == key) for key in _RANK} | {'total': len(rows)}


HEAT_DAYS = 90


def attach_heat(urls, rows, today):
    """rows: daily records {flow_id,host,path,day,checks,online,duration_ms_sum}. Adds `heat` (HEAT_DAYS cells, oldest first) to each url.

    A cell is [availability %, average ms] or None when nothing was measured that day; `uptime_90` is over the days that were measured."""
    by_url = {}
    for row in rows:
        by_url.setdefault((row['flow_id'], row['host'], row['path']), {})[(today - row['day']).days] = row
    for url in urls:
        days = by_url.get((url['flow_id'], url['host'], url['path']), {})
        cells = []
        for ago in range(HEAT_DAYS - 1, -1, -1):
            row = days.get(ago)
            cells.append(None if not row or not row['checks'] else [round(100 * row['online'] / row['checks'], 1), round(row['duration_ms_sum'] / row['checks'])])
        checks = sum(row['checks'] for row in days.values())
        url['heat'] = cells
        url['uptime_90'] = round(100 * sum(row['online'] for row in days.values()) / checks, 1) if checks else None
        url['days_measured'] = sum(1 for cell in cells if cell)
    return urls
