"""Import map com o hash de cada módulo ES da cadeia de imports de uma página.

O nginx serve /static/ com ``Cache-Control: public, immutable`` por 30 dias. Só o arquivo de
entrada leva ``?v=``; os módulos que ele importa (``./render.js``) são pedidos sem versão e ficam
no navegador do usuário, misturados com a entrada nova. O import map reescreve cada URL de
módulo para a URL com hash do conteúdo, então qualquer edição muda a URL sozinha.
"""

import json
import os
import re
from urllib.parse import urljoin, urlsplit

from markupsafe import Markup

_SPECIFIER = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(?\s*)['"](\.{1,2}/[^'"]+)['"]""")
_CACHE = {}


def _read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def _stamp(path):
    stat = os.stat(path)
    return (stat.st_mtime_ns, stat.st_size)


def module_import_map(static_folder, entry, url_prefix="/static/"):
    """Retorna ``{url sem query: url?v=hash}`` para ``entry`` e tudo que ele importa por caminho relativo."""
    from . import static_fingerprint  # reaproveita o hash por conteúdo já usado nas páginas

    entry_url = url_prefix + entry.lstrip("/")
    mapping, aliases, pending = {}, {}, [entry_url]
    while pending:
        url = pending.pop()
        if url in mapping:
            continue
        relative = url[len(url_prefix):]
        path = os.path.join(static_folder, relative)
        if not os.path.isfile(path):
            continue
        mapping[url] = f"{url}?v={static_fingerprint(static_folder, relative)}"
        key = (path, _stamp(path))
        if _CACHE.get(path, (None,))[0] != key:
            _CACHE[path] = (key, sorted(set(_SPECIFIER.findall(_read(path)))))
        for specifier in _CACHE[path][1]:
            target = urljoin(url, specifier)
            clean = urlsplit(target)._replace(query="", fragment="").geturl()
            if not clean.startswith(url_prefix) or not clean.endswith(".js"):
                continue
            if target != clean:
                aliases[target] = clean  # ex.: ./api.js?v=2 passa a apontar para o mesmo módulo com hash
            pending.append(clean)
    for alias, clean in aliases.items():
        if clean in mapping:
            mapping[alias] = mapping[clean]
    return mapping


def import_map_tag(static_folder, entry, url_prefix="/static/"):
    mapping = module_import_map(static_folder, entry, url_prefix)
    payload = json.dumps({"imports": mapping}, ensure_ascii=False, sort_keys=True).replace("</", "<\\/")
    return Markup(f'<script type="importmap">{payload}</script>')


def register_static_helpers(app):
    """Registra nos templates ``static_fingerprint`` e ``module_import_map`` (create_app e apps de teste)."""
    from . import static_fingerprint

    app.jinja_env.globals.setdefault("static_fingerprint", lambda relative_path: static_fingerprint(app.static_folder, relative_path))
    app.jinja_env.globals["module_import_map"] = lambda entry: import_map_tag(app.static_folder, entry)
