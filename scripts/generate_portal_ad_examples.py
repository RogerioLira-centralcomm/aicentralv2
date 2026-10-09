"""Build up to 200 portal-format mockups using the Studio creation pipeline.

Plan: .venv/bin/python scripts/generate_portal_ad_examples.py
Generate: same command --generate [--max-images 5] [--workers 4]
Publish checked images: same command --publish
Resume: generated files are skipped, failures remain in report.json, selections are frozen in plan.json.
Original screenshots are read as references and never overwritten.
"""
import argparse
import base64
import io
import json
import sys
import threading
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from aicentralv2.cadu_planner.portal_examples import EXAMPLES, STATIC, jobs_for, prompt_for

REPORT = ROOT / 'output' / 'portal-ad-examples'
LOCK = threading.Lock()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    temporary.replace(path)


def build_plan(args):
    from aicentralv2.cadu_family import repository
    from aicentralv2.cadu_planner import portals
    rows = repository.rows('''SELECT id, name, domain, ad_formats FROM cadu_planner_portals
        WHERE active AND scope = 'nacional_premium'
        ORDER BY featured_rank ASC NULLS LAST, popularity_rank ASC NULLS LAST, id LIMIT %s''', (args.limit,))
    portals.attach_prints(rows, all_kinds=True)
    result, skipped = [], []
    for position, portal in enumerate(rows):
        jobs = jobs_for(portals.attach_formats(portal), position)
        shots = portal.get('prints') or []
        reference = next((item for item in shots if item['kind'] == 'home'), shots[0] if shots else None)
        if not reference or not jobs:
            skipped.append({'portal_id': portal['id'], 'portal': portal['name'],
                            'reason': 'Sem captura aprovada' if not reference else 'Sem formato observado ou declarado'})
            continue
        for job in jobs:
            job.update({'reference': reference['url'].removeprefix('/static/'), 'reference_date': reference['captured_at'],
                        'reference_source': reference['source_url'], 'prompt': prompt_for(job)})
            result.append(job)
    return {'created_at': datetime.now(timezone.utc).isoformat(), 'portal_limit': args.limit,
            'portals_selected': len(rows), 'portals_ready': len({j['portal_id'] for j in result}),
            'images': len(result), 'jobs': result, 'skipped': skipped}


REVIEW_SYSTEM = (
    "You review a fictional website advertising mockup. Answer only JSON with booleans portal_recognizable, ad_visible, "
    "ad_fully_inside_frame, ad_proportion_plausible, empty_ad_slot (true when ANY other blank or grey placeholder box where an ad should be is left empty on the page), brand_legible, placement_plausible, device_matches, invented_claims "
    "(prices, discounts, numbers or endorsements), distorted_text (garbled or unreadable key text), an integer score 0-100, "
    "and issues (short list). The page may bleed off the frame; only the ad unit itself must be whole. Be strict.")
PROMPT_EXTRA = ' Every ad slot visible on the page must be either the single featured ad or removed: no empty grey boxes or blank reserved areas anywhere.'


def review_mockup(encoded, job):
    """Mockup-specific review: the Studio's ad reviewer penalises page content that touches the frame, which a portal page always does."""
    from aicentralv2.creative_lab import evaluation
    from aicentralv2.creative_media import studio_review
    from aicentralv2.services.openrouter_service import chat_completion, message_text
    _, url = studio_review._jpeg_data_url(encoded, 1024)
    ask = (f"Portal: {job['portal']} ({job['domain']}). Expected ad format: {job['format']} {job.get('size') or ''}. "
           f"Brand: {job['brand']}. Device: {job['device']}. Judge the image.")
    result = chat_completion([{'role': 'system', 'content': REVIEW_SYSTEM}, {'role': 'user', 'content': [
        {'type': 'text', 'text': ask}, {'type': 'image_url', 'image_url': {'url': url}}]}],
        model=evaluation.OBSERVER_MODEL, max_tokens=1500, response_format={'type': 'json_object'}, timeout=60, provider='openrouter')
    text = message_text(result.get('message') or {})
    verdict = json.loads(text[text.find('{'):text.rfind('}') + 1])
    good = all(verdict.get(k) is True for k in ('portal_recognizable', 'ad_visible', 'ad_fully_inside_frame',
                                                 'ad_proportion_plausible', 'brand_legible', 'placement_plausible', 'device_matches'))
    verdict['approved'] = good and not verdict.get('empty_ad_slot') and not verdict.get('invented_claims') and not verdict.get('distorted_text') and (verdict.get('score') or 0) >= 75
    verdict['reviewed'] = True
    return verdict


def generate(job, app, model, force=False):
    from aicentralv2.creative_lab.studio_bridge import LabModeling
    from aicentralv2.creative_media import studio_create
    target = EXAMPLES / str(job['portal_id']) / f"{job['key']}.webp"
    if target.exists() and not force:
        return {'key': job['key'], 'portal_id': job['portal_id'], 'status': 'existing'}
    reference = (STATIC / job['reference']).resolve()
    reference.relative_to(STATIC.resolve())
    with app.app_context():
        modeling = LabModeling(model)
        # Studio's Lab adapter records provider costs, without charging a customer for catalog assets.
        modeling.refine_target = None
        modeling.auto_review = False  # reviewed below with the mockup rubric, not the paid-social ad one
        with Image.open(reference) as source:
            source = source.convert('RGB')
            source.thumbnail((1600, 1600))
            stream = io.BytesIO()
            source.save(stream, 'JPEG', quality=90)
        mobile = job.get('device') == 'mobile'
        reference_item = {'url': 'data:image/jpeg;base64,' + base64.b64encode(stream.getvalue()).decode(),
                          'role': 'primary', 'source': 'user', 'label': f"Captura interna — {job['portal']}"}
        verdict, encoded, calls, notes = {}, None, [], ''
        for attempt in range(2):
            created = studio_create.create_image({
                'prompt': job['prompt'] + PROMPT_EXTRA + notes, 'original_prompt': job['prompt'], 'creation_intent': 'neutral_asset',
                'aspect_ratio': '2:3' if mobile else '3:2', 'quality': 'padrão', 'width': 1024 if mobile else 1536,
                'height': 1536 if mobile else 1024, 'auto_mask': False, 'references': [reference_item],
            }, modeling, 1, 1)
            index = int(created['image_url'].split(':')[-1]) - 1
            candidate, _ = modeling.capture.saved[index]
            try:
                candidate_verdict = review_mockup(candidate, job)
            except Exception as error:
                candidate_verdict = {'reviewed': False, 'approved': False, 'error': str(error)[:200]}
            candidate_verdict['attempt'] = attempt + 1
            if encoded is None or (candidate_verdict.get('score') or 0) >= (verdict.get('score') or 0):
                encoded, verdict = candidate, candidate_verdict
            if candidate_verdict.get('approved'):
                break
            notes = ' CORRECTION: ' + '; '.join(candidate_verdict.get('issues') or ['make the ad whole, larger and clearly visible'])[:400]
        calls = [{k: v for k, v in call.items() if k != 'raw_b64'} for call in modeling.capture.calls]
        with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
            image.load()
            target.parent.mkdir(parents=True, exist_ok=True)
            image.convert('RGB').save(target, 'WEBP', quality=90)
        status = 'ready' if verdict.get('approved') is True and verdict.get('reviewed') is True else 'needs_review'
        entry = {**job, 'file': target.name, 'status': status, 'review': verdict, 'calls': calls}
        with LOCK:
            manifest = target.parent / 'gallery.json'
            records = json.loads(manifest.read_text()) if manifest.exists() else []
            records = [r for r in records if r['key'] != job['key']] + [entry]
            write_json(manifest, records)
        return {'key': job['key'], 'portal_id': job['portal_id'], 'status': status,
                'cost_usd': sum(call.get('cost_usd') or 0 for call in calls), 'review': verdict}


def publish(plan):
    count = 0
    for portal_id in dict.fromkeys(job['portal_id'] for job in plan['jobs']):
        path = EXAMPLES / str(portal_id) / 'gallery.json'
        if not path.exists():
            continue
        records = json.loads(path.read_text())
        for entry in records:
            if entry['status'] == 'ready' and (path.parent / entry['file']).exists():
                entry['status'] = 'published'
                count += 1
        write_json(path, records)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, choices=range(1, 41), default=40)
    parser.add_argument('--generate', action='store_true')
    parser.add_argument('--redo', action='append', default=[], help='regenerate this job key even if it exists')
    parser.add_argument('--keys', help='comma-separated job keys to generate (pilot)')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--max-images', type=int, default=200)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--model', default='gpt-image-2.5-sunburst--openai')
    args = parser.parse_args()
    if not 1 <= args.max_images <= 200:
        parser.error('--max-images deve ser de 1 a 200')
    from run import app
    with app.app_context():
        plan_path = REPORT / 'plan.json'
        plan = json.loads(plan_path.read_text()) if plan_path.exists() else build_plan(args)
        write_json(plan_path, plan)
    print(json.dumps({k: v for k, v in plan.items() if k != 'jobs'}, ensure_ascii=False), flush=True)
    if args.generate:
        keys = set(args.keys.split(',')) if args.keys else None
        jobs = [job for job in plan['jobs'] if (keys is None or job['key'] in keys) and (job['key'] in args.redo
                or not (EXAMPLES / str(job['portal_id']) / f"{job['key']}.webp").exists())][:args.max_images]
        report_path = REPORT / 'report.json'
        report = json.loads(report_path.read_text()) if report_path.exists() else []
        def run(job):
            try:
                entry = generate(job, app, args.model, job['key'] in args.redo)
            except Exception as error:
                entry = {'key': job['key'], 'portal_id': job['portal_id'], 'status': 'failed', 'error': str(error)[:500]}
            with LOCK:
                report.append(entry)
                write_json(report_path, report)
            print(json.dumps(entry, ensure_ascii=False), flush=True)
            return entry
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            results = list(pool.map(run, jobs))
        print('Resultado:', {s: sum(r['status'] == s for r in results) for s in ('ready', 'needs_review', 'failed')}, flush=True)
    if args.publish:
        print('Publicadas:', publish(plan), flush=True)


if __name__ == '__main__':
    main()
