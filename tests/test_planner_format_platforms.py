from unittest import mock

from aicentralv2.cadu_planner import channels


def test_plan_channels_map_to_their_format_platforms():
    rows = [{'slug': 'instagram'}, {'slug': 'youtube'}, {'slug': 'uol'}, {'slug': 'google-dv360'}, {'slug': 'netflix'}]
    with mock.patch.object(channels.repository, 'rows', return_value=rows):
        assert channels.format_platforms(['31', '30', '11', '18', '4']) == ['meta_ads', 'google_ads', 'programatica_iab', 'netflix']
    assert channels.format_platforms([]) == []
