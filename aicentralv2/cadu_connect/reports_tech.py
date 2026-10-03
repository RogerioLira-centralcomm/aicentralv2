"""Coarse technology of a visit for Site & Jornada: operating system and browser family from the User-Agent header, screen size
and pixel ratio from the tag. The raw User-Agent is never stored; only these families and numbers leave this module."""
import re

SCREEN_MAX = 10000
ORIENTATIONS = ('portrait', 'landscape')
# In-app browsers come first: they carry the host browser's name too (Instagram on iOS says Safari, on Android Chrome).
_BROWSERS = (
    ('Instagram', r'Instagram'), ('Facebook', r'FBAN|FBAV|FB_IAB'), ('LinkedIn', r'LinkedInApp'),
    ('TikTok', r'TikTok|musical_ly|BytedanceWebview'), ('WebView', r'; wv\)'),
    ('Edge', r'Edg/|EdgA/|EdgiOS/'), ('Opera', r'OPR/|Opera'), ('Samsung Internet', r'SamsungBrowser'),
    ('Firefox', r'Firefox/|FxiOS/'), ('Chrome', r'Chrome/|CriOS/'), ('Safari', r'Safari/'),
)
_SYSTEMS = (('iOS', r'iPhone|iPad|iPod'), ('Android', r'Android'), ('Windows', r'Windows'), ('ChromeOS', r'CrOS'),
            ('macOS', r'Macintosh|Mac OS X'), ('Linux', r'Linux|X11'))
BROWSER_FAMILIES = tuple(name for name, _ in _BROWSERS) + ('Outro',)
SYSTEM_FAMILIES = tuple(name for name, _ in _SYSTEMS) + ('Outro',)


def tech_from_user_agent(user_agent):
    """(system family, browser family) of a User-Agent string; 'Outro' when nothing matches or the header is missing."""
    text = str(user_agent or '')[:512]
    system = next((name for name, pattern in _SYSTEMS if re.search(pattern, text)), 'Outro')
    browser = next((name for name, pattern in _BROWSERS if re.search(pattern, text)), 'Outro')
    return system, browser
