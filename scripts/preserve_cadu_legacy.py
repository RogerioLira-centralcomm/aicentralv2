"""Create a private, non-executable migration reference from local PHP sources.

No network, database access, deletion, or changes to the source tree. Possible
credential literals are redacted and recorded in the manifest. This scanner
is conservative but is not a secret-scanner certification or a disaster backup.
"""
import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {'vendor', 'node_modules', '.git', 'uploads', 'logs', 'cache', 'tmp',
             'temp', 'sessions', 'backups', 'backup', 'storage', '.agents', '.cursor', '.firecrawl'}
TEXT = {'.php', '.js', '.css', '.html', '.htm', '.json', '.yaml', '.yml', '.md',
        '.txt', '.sql', '.xml', '.svg', '.lock'}
ASSETS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.ico', '.woff', '.woff2', '.ttf', '.otf', '.eot'}
SECRET = re.compile(
    r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|'
    r'\b(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{25,}|gh[pousr]_[A-Za-z0-9]{20,})|'
    r'(?i:bearer\s+[a-z0-9_.-]{20,})|'
    r'(?i:(?:password|passwd|senha|secret|api[_-]?key|access[_-]?token|refresh[_-]?token)'
    r'[\w]*[\s\x22\x27]*[=:,][\s]*(?:\x22[^\x22\n]{3,}\x22|\x27[^\x27\n]{3,}\x27))|'
    r'(?i:postgres(?:ql)?://[^\s]+:[^\s]+@)'
)


def product(path):
    name = path.lower()
    if any(word in name for word in ('chat', 'dify', 'copilot', 'tokenusage', 'embedding', 'projetorag')):
        return 'conversas'
    if any(word in name for word in ('login', 'auth', 'senha', 'sso', 'cadastro', 'google-callback', 'convite')):
        return 'auth'
    if any(word in name for word in ('link-tester', 'creative-analyzer', 'ferramentas-copy')):
        return 'studio'
    if any(word in name for word in ('configuracoes', 'integraco', 'centro-inteligencia', 'projeto', 'branding', 'checkout', 'plano')):
        return 'workspace'
    if any(word in name for word in ('audien', 'canais', 'formato', 'interativ', 'cotac', 'docs', 'smart-planner')):
        return 'smartplanner'
    if any(word in name for word in ('relatorio', 'campanha', '_dv360', '_socialads')):
        return 'connect'
    return 'shared-or-review'


def preserve(source, destination):
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if destination == source or source in destination.parents:
        raise ValueError('The destination must not be inside the legacy source.')
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    records, routes, tables = [], [], set()
    for root, dirs, names in os.walk(source, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS
                         and not d.lower().startswith('_session') and not (Path(root) / d).is_symlink())
        for name in sorted(names):
            path = Path(root) / name
            relative = path.relative_to(source).as_posix()
            record = {'path': relative, 'product_hint': product(relative)}
            records.append(record)
            if path.is_symlink():
                record['status'] = 'excluded-symlink'
                continue
            if (name.startswith('.env') or re.search(r'(?i)(credential|secret|config.*local|service.account|debug|dump)', name)
                    or path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.log', '.csv'}):
                record['status'] = 'excluded-sensitive-or-runtime'
                continue
            suffix = path.suffix.lower()
            if suffix not in TEXT | ASSETS and name != '.htaccess':
                record['status'] = 'excluded-unclassified'
                continue
            data = path.read_bytes()
            record.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            text = data.decode('utf-8', errors='replace') if suffix in TEXT or name == '.htaccess' else ''
            if text:
                tables.update(re.findall(r'\b(?:cadu_[a-z0-9_]+|cx_[a-z0-9_]+|tbl_[a-z0-9_]+)\b', text))
                # Store dependency paths only; never include source lines or literal values.
                record['dependencies'] = sorted(set(re.findall(
                    r'[\x22\x27]([\w./-]+\.(?:php|js|css))[\x22\x27]', text)))
                if relative == '.htaccess':
                    routes = [match.groups() for match in re.finditer(
                        r'^RewriteRule\s+(\S+)\s+([\w./?=$()-]+\.php[^\s]*)', text, re.M)]
                if SECRET.search(text):
                    text, count = SECRET.subn('[REDACTED: configure on the Python server]', text)
                    data = text.encode('utf-8')
                    record.update(status='preserved-sanitized', redactions=count)
            target = destination / 'source' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            # .reference prevents PHP execution if this directory is accidentally served.
            target = target.with_name(target.name + '.reference')
            with target.open('xb') as output:
                os.chmod(target, 0o600)
                output.write(data)
            record.setdefault('status', 'preserved')
            record['snapshot_sha256'] = hashlib.sha256(data).hexdigest()
    counts = dict(Counter(row['status'] for row in records))
    manifest = {'created_at': datetime.now(timezone.utc).isoformat(), 'source': str(source),
                'counts': counts, 'excluded_directories': sorted(SKIP_DIRS),
                'routes': routes, 'table_candidates': sorted(tables), 'files': records}
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    copied = [row for row in records if row['status'].startswith('preserved')]
    for row in copied:
        target = destination / 'source' / (row['path'] + '.reference')
        if hashlib.sha256(target.read_bytes()).hexdigest() != row['snapshot_sha256']:
            raise RuntimeError('Snapshot checksum mismatch')
    print(json.dumps({'destination': str(destination), 'counts': counts,
                      'verified_files': len(copied), 'route_count': len(routes),
                      'table_candidates': len(tables)}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    preserve(args.source, args.destination)
