"""Traduz a interface do OpenCut vendorizado para PT-BR com cadu/i18n/pt-BR.json.

Só troca textos em contextos visíveis (texto JSX, atributos de rótulo, campos label/title/description,
ternários de texto e toasts), nunca chaves ou valores internos. Idempotente: rode de novo depois de
atualizar o código do OpenCut.  Uso: python3 scripts/apply-pt-br.py [--check]
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
SOURCE = HERE / 'opencut'
SKIP = ('services/storage/migrations/',)
ATTRS = r'(?:label|title|placeholder|aria-label|description|tooltip|emptyText|message|alt)'
FIELDS = r'(?:label|title|description|placeholder|message|tooltip|emptyText|step)'


def patterns(text):
    q = re.escape(text)
    return [
        # Texto JSX: só antes de tag de fechamento; "=> Record<string, T>" é genérico do TypeScript.
        (re.compile(r'(>\s*)' + q + r'(\s*</)'), r'\g<1>{}\g<2>'),
        (re.compile(r'(\b' + ATTRS + r'=\{?")' + q + r'("\}?)'), r'\g<1>{}\g<2>'),
        (re.compile(r'(\b' + FIELDS + r':\s*")' + q + r'(")'), r'\g<1>{}\g<2>'),
        (re.compile(r'(\{\s*")' + q + r'("\s*\})'), r'\g<1>{}\g<2>'),
        (re.compile(r'(\?\s*")' + q + r'("\s*:)'), r'\g<1>{}\g<2>'),
        (re.compile(r'(:\s*")' + q + r'("\s*[}\)\n])'), r'\g<1>{}\g<2>'),
        (re.compile(r'(toast\.(?:error|success|info|warning|message)\(\s*")' + q + r'(")'), r'\g<1>{}\g<2>'),
    ]


def main():
    dictionary = json.loads((HERE / 'cadu/i18n/pt-BR.json').read_text())
    compiled = [(english, [(regex, template.format(pt.replace('\\', r'\\'))) for regex, template in patterns(english)])
                for english, pt in sorted(dictionary.items(), key=lambda item: -len(item[0]))]
    changed = {}
    for path in SOURCE.rglob('*.ts*'):
        rel = str(path.relative_to(SOURCE))
        if any(rel.startswith(prefix) for prefix in SKIP):
            continue
        raw = path.read_bytes().decode('utf-8')
        newline = '\r\n' if '\r\n' in raw else '\n'  # preserva o fim de linha original (o OpenCut mistura CRLF e LF)
        text = original = raw.replace('\r\n', '\n')
        for _, rules in compiled:
            for regex, replacement in rules:
                text = regex.sub(replacement, text)
        if text != original:
            changed[rel] = sum(1 for a, b in zip(original.splitlines(), text.splitlines()) if a != b)
            if '--check' not in sys.argv:
                path.write_bytes(text.replace('\n', newline).encode('utf-8'))
    for rel, lines in sorted(changed.items()):
        print(f'{lines:4} {rel}')
    print(f'{len(changed)} arquivos', '(verificação, nada gravado)' if '--check' in sys.argv else 'traduzidos')


if __name__ == '__main__':
    main()
