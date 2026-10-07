from datetime import datetime, timedelta, timezone

from aicentralv2.cadu_radar import feed


def test_score_prefers_angles_then_strong_sources_then_recent():
    now = datetime.now(timezone.utc)
    base = {'published_at': now, 'detected_at': now, 'saved': False, 'tier': 'C', 'angle_count': 0}
    with_angle = {**base, 'angle_count': 1}
    old_strong = {**base, 'tier': 'A', 'published_at': now - timedelta(days=20)}
    old_weak = {**base, 'published_at': now - timedelta(days=20)}
    assert feed._score(with_angle, now) > feed._score(old_strong, now) > feed._score(old_weak, now)
