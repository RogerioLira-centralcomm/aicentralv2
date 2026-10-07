"""The server-drawn first paint of the Planner navbar must list the same destinations as the live PlannerNav."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSX = (ROOT / 'frontend/planner/PlannerNav.jsx').read_text()
BOOT = (ROOT / 'aicentralv2/templates/cadu_planner/_nav_boot.html').read_text()


def test_boot_nav_lists_the_same_destinations_as_the_live_nav():
    live = re.findall(r"\['(\w+)', '([^']+)', '(\w+)'\]", JSX.split('const DESTINATIONS = [')[1].split('];')[0])
    boot = re.findall(r"\('(\w+)', '([^']+)', '(\w+)'\)", BOOT.split('set destinations = [')[1].split('] -%}')[0])
    assert live and live == boot


def test_boot_nav_is_only_drawn_for_signed_views_and_replaced_by_react():
    template = (ROOT / 'aicentralv2/templates/cadu_planner/react.html').read_text()
    assert "include 'cadu_planner/_nav_boot.html'" in template
    assert "planner_view in ('public-plan', 'public-doc')" in template
    main = (ROOT / 'frontend/planner/main.jsx').read_text()
    assert "createRoot(root).render(" in main
