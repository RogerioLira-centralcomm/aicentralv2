"""Read-only structural inventory. Emits identifiers/locations, never source bodies.

This is lexical evidence, not a PHP/JS parser or a feature-parity certification.
No PHP execution, DB connection, configuration scan, or network access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


PATTERNS = {
    'symbols': r'^\s*(?:(?:async|static|public|private|protected|final)\s+)*(?:function\s+)?([A-Za-z_$][\w$]*)\s*\([^;\n]*\)\s*(?::\s*\??[\w\\]+\s*)?\{',
    'php_fields': r'\$(?:params|request|input|data|_GET|_POST|_FILES)\s*\[\s*[\'"]([A-Za-z_][\w-]*)[\'"]\s*\]',
    'event_cases': r'\bcase\s+[\'"]([A-Za-z_][\w-]*)[\'"]\s*:',
    'api_paths': r'[\'"](/api/[A-Za-z0-9_./-]+\.php)',
    'dom_ids': r'\bid\s*=\s*[\'"]([A-Za-z][\w-]*)[\'"]',
    'tables': r'\b(?:FROM|JOIN|INTO|UPDATE)\s+((?:cadu_|tbl_)[A-Za-z0-9_]+)',
}
EXCLUDED_SYMBOLS = {'if', 'while', 'for', 'switch', 'catch', 'with'}
OUT_OF_SCOPE = {'CotacaoCreator.php', 'AnalyticsData.php', 'SearchConsoleData.php',
                'GoogleAnalyticsData.php', 'GoogleAdsData.php', 'MetaAdsData.php',
                'LinkedInAdsData.php', 'LinkedInAdLibrary.php'}
PATTERNS_TO_SCAN = (
    'chat-cadu-dify.php', 'assets/js/dify/*.js', 'includes/dify/*.php',
    'assets/js/chat-projeto-selector.js', 'assets/js/web-search-toggle.js',
    'assets/css/*dify*.css', 'assets/css/chat-cadu.css', 'assets/css/chat-model-select.css',
    'api/dify-*.php', 'api/chat-messages.php', 'api/chat-skills.php',
    'api/extract-file-content.php', 'api/chat/*.php', 'api/chat/tools/*.php',
    'api/projetos/branding.php', 'api/projetos/retrieve.php',
)


def inspect_source(source):
    result = {}
    for kind, pattern in PATTERNS.items():
        found = []
        for match in re.finditer(pattern, source, re.MULTILINE | (re.IGNORECASE if kind == 'tables' else 0)):
            name = match.group(1)
            if kind == 'symbols' and name in EXCLUDED_SYMBOLS:
                continue
            found.append({'name': name, 'line': source.count('\n', 0, match.start(1)) + 1})
        result[kind] = found
    return result


def inventory(root):
    files = sorted({path for pattern in PATTERNS_TO_SCAN for path in root.glob(pattern) if path.is_file() and not path.is_symlink()})
    entries = []
    for path in files:
        raw = path.read_bytes()
        source = raw.decode('utf-8', errors='replace')
        entries.append({'path': path.relative_to(root).as_posix(), 'sha256': hashlib.sha256(raw).hexdigest(),
                        'lines': len(source.splitlines()), **inspect_source(source)})
    registry = (root / 'api/chat/tools.php').read_text(encoding='utf-8')
    tools = [{'alias': match[1], 'file': match[2], 'class': match[3],
              'line': registry.count('\n', 0, match.start()) + 1}
             for match in re.finditer(r"'([a-z_]+)'\s*=>\s*\['file'\s*=>\s*'([A-Za-z]+\.php)',\s*'class'\s*=>\s*'([A-Za-z]+)'", registry)]
    return {'schema_version': 1, 'scope': list(PATTERNS_TO_SCAN),
            'limitations': 'Lexical candidates; aliases and methods are not independent user features. Table names are not verified database schemas.',
            'summary': {'files': len(entries), 'lines': sum(item['lines'] for item in entries),
                        'symbols': sum(len(item['symbols']) for item in entries),
                        'tool_aliases': len(tools), 'tool_implementations': len({tool['file'] for tool in tools})},
            'tools': tools, 'files': entries}


def markdown(data):
    out = ['# Inventário estrutural do Conversas PHP', '',
           'Gerado por `scripts/inventory_cadu_conversations.py`; leitura local, sem executar PHP ou consultar banco.',
           '', data['limitations'], '', '## Resumo', '']
    out += [f'- {key}: {value}' for key, value in data['summary'].items()]
    out += ['', '## Escopo confirmado', '',
            'Documentos pertencem ao Cadu Media/SmartPlanner e mantêm conexão com Conversas. Canais e formatos entram na migração.',
            'Cotações, analytics e dados de mídia ficam fora desta migração do chat; sua presença abaixo é somente referência, sem exclusão de dados.',
            '', '## Ferramentas: aliases agrupados por implementação', '', '| Implementação | Escopo | Aliases |', '|---|---|---|']
    for file in sorted({tool['file'] for tool in data['tools']}):
        aliases = ', '.join(f"`{tool['alias']}` (L{tool['line']})" for tool in data['tools'] if tool['file'] == file)
        scope = 'Fora desta migração' if file in OUT_OF_SCOPE else ('Conexão com Docs do Media/SmartPlanner' if file == 'DocSaver.php' else 'Referência para reconstrução; não entregue')
        out.append(f'| api/chat/tools/{file} | {scope} | {aliases} |')
    out += ['', '## Evidências por arquivo', '', 'Cada identificador traz sua linha. Campos são candidatos: podem incluir parâmetros internos; não constituem uma API pública autorizada.']
    for entry in data['files']:
        out += ['', '### ' + entry['path'], '', f"{entry['lines']} linhas; SHA-256 `{entry['sha256']}`."]
        for kind in PATTERNS:
            names = {}
            for item in entry[kind]:
                names.setdefault(item['name'], []).append(str(item['line']))
            if names:
                out += ['', f'**{kind}**: ' + '; '.join(f'`{name}` (L{", ".join(lines)})' for name, lines in names.items())]
    return '\n'.join(out) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('legacy_root', type=Path)
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    args = parser.parse_args()
    data = inventory(args.legacy_root.resolve())
    print(markdown(data) if args.format == 'markdown' else json.dumps(data, ensure_ascii=False, indent=2))
