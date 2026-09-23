"""Deterministic parsing for pasted Meet, Teams and Zoom invitations."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}


def _platform(url: str) -> tuple[str, str] | None:
    host = (urlparse(url).hostname or "").lower()
    if host == "meet.google.com":
        return "google_meet", "Google Meet"
    if host == "teams.microsoft.com" or host.endswith(".teams.microsoft.com") or host == "teams.live.com":
        return "microsoft_teams", "Microsoft Teams"
    if host == "zoom.us" or host.endswith(".zoom.us"):
        return "zoom", "Zoom"
    return None


def _clock(hour: str, minute: str, meridiem: str) -> tuple[int, int]:
    value = int(hour)
    marker = (meridiem or "").lower()
    if marker == "pm" and value < 12:
        value += 12
    if marker == "am" and value == 12:
        value = 0
    return value, int(minute)


def parse_meeting_invite(value: str, now: datetime | None = None) -> dict | None:
    """Extract safe meeting metadata without opening any URL."""
    text = str(value or "").replace("\\_", "_").strip()
    urls = [item.rstrip(".,;:)") for item in re.findall(r"https?://[^\s<>\]\[\"']+", text, re.IGNORECASE)]
    primary = next(((url, platform) for url in urls if (platform := _platform(url))), None)
    if not primary:
        return None
    url, (provider, platform_label) = primary
    lines = [re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line).strip() for line in text.splitlines() if line.strip()]
    eligible_titles = [line for line in lines if not re.search(
        r"^(?:como participar|join |link da videochamada|ou disque|outros n[uú]meros|fuso hor[aá]rio|https?://)",
        line, re.IGNORECASE,
    ) and not re.search(r"\b\d{1,2}:\d{2}\s*(?:am|pm)?\b", line, re.IGNORECASE)]
    dated_line = next((index for index, line in enumerate(lines) if re.search(
        r"(?:segunda|terça|terca|quarta|quinta|sexta|s[aá]bado|domingo)(?:-feira)?\s*,?\s*\d{1,2}\s+de\s+[a-zç]+",
        line, re.IGNORECASE,
    )), None)
    nearby_titles = [line for line in lines[:dated_line] if line in eligible_titles] if dated_line is not None else []
    title = (nearby_titles[-1] if nearby_titles else eligible_titles[0] if eligible_titles else platform_label)
    timezone_match = re.search(r"(?:fuso hor[aá]rio|time\s*zone)\s*:\s*([A-Za-z_]+/[A-Za-z_]+)", text, re.IGNORECASE)
    timezone = timezone_match.group(1) if timezone_match else ""
    date_match = re.search(
        r"(?:segunda|terça|terca|quarta|quinta|sexta|s[aá]bado|domingo)(?:-feira)?\s*,?\s*(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?",
        text, re.IGNORECASE,
    )
    time_match = re.search(
        r"(\d{1,2}):(\d{2})\s*(am|pm)?\s*[–—-]\s*(\d{1,2}):(\d{2})\s*(am|pm)?",
        text, re.IGNORECASE,
    )
    starts_at = ends_at = None
    year_inferred = False
    if date_match and time_match:
        month = _MONTHS.get(date_match.group(2).casefold())
        if month:
            clock = now or datetime.now(ZoneInfo(timezone or "America/Sao_Paulo"))
            year_inferred = not bool(date_match.group(3))
            year = int(date_match.group(3) or clock.year)
            start_hour, start_minute = _clock(*time_match.group(1, 2, 3))
            end_hour, end_minute = _clock(*time_match.group(4, 5, 6))
            try:
                tz = ZoneInfo(timezone) if timezone else clock.tzinfo
                start_value = datetime(year, month, int(date_match.group(1)), start_hour, start_minute, tzinfo=tz)
                end_value = datetime(year, month, int(date_match.group(1)), end_hour, end_minute, tzinfo=tz)
                if end_value <= start_value:
                    end_value += timedelta(days=1)
                starts_at, ends_at = start_value.isoformat(), end_value.isoformat()
            except (ValueError, KeyError):
                pass
    pin_match = re.search(r"\bPIN\s*:\s*([^\n#]+#?)", text, re.IGNORECASE)
    phone_match = re.search(r"(?:ou disque|dial(?:-in)?)\s*:\s*([^\n]+?)(?:\s+PIN\s*:|$)", text, re.IGNORECASE)
    external_id = urlparse(url).path.strip("/").split("/")[-1][:512]
    return {
        "provider": provider, "platform": platform_label, "url": url,
        "external_id": external_id, "title": title[:180],
        "starts_at": starts_at, "ends_at": ends_at, "timezone": timezone or None,
        "year_inferred": year_inferred, "dial_in": phone_match.group(1).strip() if phone_match else None,
        "pin": pin_match.group(1).strip() if pin_match else None,
        "related_urls": [item for item in urls if item != url][:10],
    }
