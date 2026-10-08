"""Lab dos tipos de ângulo: prompt 1.5 contra 1.6 sobre as mesmas notícias, em vários cenários.

    .venv/bin/python scripts/radar_lab_types.py --client-id 174 --user-id 2 --scenarios cemig,nike,bomfim,nike-concorrencia

Saída em output/radar-lab-types/<data-hora>/: result.json e report.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2 import create_app  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--client-id', type=int, required=True)
    parser.add_argument('--user-id', type=int, required=True)
    parser.add_argument('--scenarios', default='cemig,nike,bomfim,nike-concorrencia')
    args = parser.parse_args()
    scenarios = {item['name']: item for item in json.loads((ROOT / 'scripts' / 'radar_lab_scenarios.json').read_text())}
    app = create_app()
    results = []
    with app.app_context():
        from aicentralv2.cadu_radar import lab_types
        catalog = lab_types.channel_catalog()
        print(f'catálogo: {len(catalog)} canais', flush=True)
        for name in [value.strip() for value in args.scenarios.split(',') if value.strip()]:
            result = lab_types.run_scenario(args.client_id, args.user_id, scenarios[name], catalog)
            results.append(result)
            print(json.dumps(lab_types.summary(result), ensure_ascii=False), flush=True)
    folder = ROOT / 'output' / 'radar-lab-types' / datetime.now().strftime('%Y%m%d%H%M%S')
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'result.json').write_text(json.dumps({'catalog_size': len(catalog), 'results': results}, ensure_ascii=False, indent=2, default=str))
    (folder / 'report.md').write_text(lab_types.report_markdown(results))
    print(folder / 'report.md')


if __name__ == '__main__':
    main()
