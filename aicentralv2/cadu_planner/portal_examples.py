"""Public illustrative examples, separate from the internal screenshot archive."""
import json
import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / 'static'
EXAMPLES = STATIC / 'images' / 'portais' / 'examples'
BRANDS = (
    ('Itaú', 'orange and navy blue, Brazilian bank, everyday financial services'),
    ('Vivo', 'purple, Brazilian telecom, connected everyday life'),
    ('Natura', 'warm earth tones, Brazilian cosmetics, botanical skincare'),
    ('Magalu', 'blue, Brazilian retailer, home electronics'),
    ('Havaianas', 'bright Brazilian summer colors, recognizable flip-flops'),
)


def attach_examples(portals):
    """Only published files belonging to this portal are sent to the customer page."""
    for portal in portals:
        portal['ad_examples'] = []
        try:
            folder = EXAMPLES / str(int(portal['id']))
            records = json.loads((folder / 'gallery.json').read_text(encoding='utf-8'))
            for item in records[:5]:
                filename = item.get('file', '')
                if item.get('status') != 'published' or not re.fullmatch(r'[a-z0-9-]+\.webp', filename):
                    continue
                if not (folder / filename).is_file():
                    continue
                portal['ad_examples'].append({
                    'url': f"/static/images/portais/examples/{portal['id']}/{filename}",
                    'title': f"{item['format']} no {portal['name']} — simulação",
                    'format': item['format'], 'size': item.get('size'), 'brand': item['brand'],
                })
        except (OSError, ValueError, TypeError, KeyError):
            continue
    return portals


def _size_in(*texts):
    match = re.search(r'(\d{2,4})\s*[x×]\s*(\d{2,4})', ' '.join(str(t or '') for t in texts))
    return f'{match.group(1)}x{match.group(2)}' if match else None


def device_for(label, size):
    """Mobile formats are shown in the portal's mobile layout."""
    width, height = (int(n) for n in size.split('x')) if size and re.fullmatch(r'\d+x\d+', size) else (0, 0)
    banner = 0 < width <= 336 and 0 < height <= 100  # 320x50 and 320x100 only exist on phones
    return 'mobile' if re.search(r'mobile|smartphone|\bapp\b', str(label), re.I) or banner else 'desktop'


def jobs_for(portal, position=0):
    """Up to five distinct observed/declared formats. Market defaults are never evidence."""
    formats = list(portal.get('ad_formats') or [])
    formats += [{'format': item['nome'], 'size': item.get('size') or _size_in(item['nome'], item.get('dimensoes'))}
                for item in (portal.get('formats') or {}).get('own', [])]
    jobs, seen = [], set()
    for item in formats:
        label = str(item.get('format') or '').strip()
        size = str(item.get('size') or '').replace('×', 'x').strip() or None
        key = (label.casefold(), size)
        if not label or key in seen:
            continue
        seen.add(key)
        brand, identity = BRANDS[(position + len(jobs)) % len(BRANDS)]
        import hashlib
        slug = hashlib.sha256(f"{portal['id']}|{label}|{size}".encode()).hexdigest()[:12]
        jobs.append({'key': f'format-{slug}', 'portal_id': portal['id'], 'portal': portal['name'],
                     'domain': portal['domain'], 'format': label, 'size': size, 'brand': brand, 'identity': identity,
                     'device': device_for(label, size)})
        if len(jobs) == 5:
            break
    return jobs


def prompt_for(job):
    return (
        f"Create a high fidelity flat website advertising mockup of {job['portal']} ({job['domain']}). "
        "The reference is an internal screenshot of this exact portal. Preserve its recognizable masthead, "
        "editorial typography, colors and page layout. Show enough surrounding editorial content to explain placement. "
        f"Feature ONE advertisement in the format {job['format']}"
        + (f" with the ad unit's exact proportions {job['size']} pixels" if job.get('size') else '')
        + f", advertising {job['brand']} ({job['identity']}). "
        "Use the brand name legibly inside the advertisement with tasteful brand imagery and a short Portuguese CTA 'Saiba mais'. "
        "The advertiser identity belongs only inside the ad slot. This is an illustrative fictional placement, not an actual campaign. "
        "Label the slot 'Publicidade'. For mobile formats show the mobile portal layout; for video show a paused advertising frame "
        "inside the appropriate player; for native formats show a sponsored editorial card. "
        "No invented prices, discounts, performance figures, endorsements, or claims about advertiser relationships. "
        "No laptop, monitor, perspective, decorative frame or external caption. Do not turn the whole portal into a brand advertisement. "
        "The ad must be clearly visible with its correct proportions and plausible position. "
        "Keep the complete ad unit and its text fully inside the frame, never cropped by the image edge; the page itself may continue past the edges. "
        + ('Show the portal as seen on a smartphone, a tall mobile page filling the whole frame. ' if job.get('device') == 'mobile' else '')
    )
