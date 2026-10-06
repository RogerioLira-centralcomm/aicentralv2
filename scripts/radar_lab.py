"""Lab do Radar: roda os fluxos F1, F2 e F3 no mesmo cenário e compara qualidade e custo.

Nada vai para as tabelas do Radar. As chamadas pagas passam pelo roteador global
de créditos e são debitadas do cliente informado (``app='Cadu Radar'``,
``stage='radar-lab:...'``). ``--dry-run`` só simula: não chama provedor nem debita.

    .venv/bin/python scripts/radar_lab.py --client-id 1 --user-id 2 --scenario cemig --dry-run
    .venv/bin/python scripts/radar_lab.py --client-id 1 --user-id 2 --scenario cemig
    .venv/bin/python scripts/radar_lab.py ... --flows F1,F3 --model F3.judge=google/gemini-3-flash-preview

    .venv/bin/python scripts/radar_lab.py ... --flows all --revise-rounds 2 --prompt-loops 1

Saída em output/radar-lab/<run>/: result.json, report.md e prompts_best.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2 import create_app  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--client-id', type=int, required=True, help='Cliente que paga os créditos do teste')
    parser.add_argument('--user-id', type=int, required=True, help='Usuário que aparece no livro de créditos')
    parser.add_argument('--scenario', default='cemig', help='Nome em scripts/radar_lab_scenarios.json')
    parser.add_argument('--flows', default='F1,F2,F3', help='Lista (F1,F4) ou "all"')
    parser.add_argument('--revise-rounds', type=int, default=2, help='Voltas de revisão das oportunidades por fluxo')
    parser.add_argument('--target', type=float, default=4.2, help='Nota do revisor (1–5) que encerra a revisão')
    parser.add_argument('--prompt-loops', type=int, default=1, help='Versões de prompt propostas pelo médico de prompts')
    parser.add_argument('--model', action='append', default=[], help='FLUXO.etapa=modelo (troca um modelo)')
    parser.add_argument('--dry-run', action='store_true', help='Só simula o custo; nenhuma chamada paga')
    parser.add_argument('--out', default=str(ROOT / 'output' / 'radar-lab'))
    args = parser.parse_args()

    scenarios = {item['name']: item for item in json.loads((ROOT / 'scripts' / 'radar_lab_scenarios.json').read_text())}
    scenario = scenarios[args.scenario]
    overrides = dict(item.split('=', 1) for item in args.model)
    from aicentralv2.cadu_radar.lab import FLOWS
    flows = tuple(FLOWS) if args.flows == 'all' else tuple(f.strip().upper() for f in args.flows.split(',') if f.strip())

    app = create_app()
    with app.app_context():
        from aicentralv2.cadu_radar.lab import Lab, report_markdown
        lab = Lab(args.client_id, args.user_id, scenario, overrides=overrides, dry_run=args.dry_run)
        result = lab.run(flows, revise_rounds=args.revise_rounds, target=args.target, prompt_loops=args.prompt_loops)
    folder = Path(args.out) / (result['run_id'] + ('-dry' if args.dry_run else ''))
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    (folder / 'report.md').write_text(report_markdown(result))
    (folder / 'prompts_best.json').write_text(json.dumps({'version': result['best_version'], 'prompts': result['best_prompts']},
                                                         ensure_ascii=False, indent=2))
    for flow, row in result['flows'].items():
        print(json.dumps({'flow': flow, **{k: row[k] for k in ('opportunities', 'review_avg', 'history', 'sources_ab_pct',
                                                                'urls_ok_pct', 'real_tokens', 'provider_usd')}}, ensure_ascii=False))
    print(json.dumps({'versions': result['versions'], 'best': result['best_version'], 'noise': result['reviewer_noise']},
                     ensure_ascii=False))
    print(os.path.relpath(folder / 'report.md', ROOT))


if __name__ == '__main__':
    main()
