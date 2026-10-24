"""Lab: A/B do diretor de montagem (storyboard → timeline) antes de ir ao Studio.

Compara o plano por regras com modelos via OpenRouter, nos mesmos storyboards e mídias reais do Studio.
Cada montagem é renderizada (GPU se --gpu) e um juiz cego (modelo com visão que não sabe qual variante
gerou o quadro) avalia um quadro do meio de cada cena: texto sobre o sujeito, legibilidade, sujeito visível,
quadro preenchido e nota de 1 a 5. Sem banco; chamadas pagas direto no OpenRouter (centavos por rodada).

Uso: .venv/bin/python scripts/lab_montage.py [--gpu metal] [--models anthropic/claude-opus-5.5,...] [--cases tecnologia,cemig]
"""
import argparse
import base64
import json
import os
import random
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
if (REPO / 'instance/ms-playwright').is_dir():
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(REPO / 'instance/ms-playwright'))
try:
    from dotenv import load_dotenv
    load_dotenv(REPO / '.env')
except ImportError:
    pass

from flask import Flask  # noqa: E402

from aicentralv2.creative_media import studio_montage as montage  # noqa: E402
from aicentralv2.creative_media.studio_video_editor import apply_commands, render_project  # noqa: E402
from aicentralv2.services.openrouter_service import chat_completion  # noqa: E402

ASSETS = REPO / 'aicentralv2/static/uploads/creative_generated'
JUDGE_MODEL = 'anthropic/claude-haiku-5.5'
CASES = {
    'tecnologia': {
        'brand': {'name': 'Conecta', 'primary_color': '#3a0b3d', 'secondary_color': '#2ee6b6', 'tone_of_voice': 'direto, confiante, simples'},
        'briefing': 'App de gestão para pequenas empresas. Oferta: teste grátis por 30 dias.',
        'duration': 12,
        'beats': [
            ('hook', 'close', 'Celular azul em destaque, girando devagar sobre fundo azul', 'Seu negócio cabe na palma da mão.', '4ae3092d598f4780947f8ed0978c5f15.mp4'),
            ('beat', 'médio', 'Ilustração: celular, monitor e tablet com o mesmo app aberto', 'Gerencie de qualquer tela.', '0110880e0e3a4170bb6bd078b5424317.png'),
            ('proof', 'detalhe', 'Painéis do app com gráficos e indicadores', 'Acompanhe seus dados em tempo real.', '09153d03984a4b369c4683a97ba1e324.png'),
            ('beat', 'médio', 'Três pessoas da equipe e um gráfico de barras crescendo', 'Sua equipe conectada.', '4b9cf17b9bdc41f582a32bf9f4e3b215.png'),
            ('end', 'geral', 'Mapa isométrico com prédio e pontos de localização', 'Teste grátis por trinta dias.', 'd71071ac219a47aabbc9432b072c20de.png'),
        ],
    },
    'cemig': {
        'brand': {'name': 'CEMIG', 'primary_color': '#0b5d3b', 'secondary_color': '#b6e61d', 'tone_of_voice': 'acolhedor, regional, confiável'},
        'briefing': 'Campanha institucional: energia que acompanha você em cada canto de Minas.',
        'duration': 12,
        'beats': [
            ('hook', 'médio', 'Família na janela à noite olhando a cidade iluminada', 'Energia que acompanha você.', '005b20d70e5c44b3b1ffd919dda7d862.png'),
            ('beat', 'médio', 'Família reunida no sofá lendo juntos sob a luz do abajur', 'Em cada momento em casa.', '8722078b1a724461a27c1ca4e139a746.png'),
            ('proof', 'médio', 'Família na sala vendo algo no tablet, cidade ao fundo', 'Em cada canto de Minas.', 'd19690401d3b48528e84ccd053ca6287.png'),
            ('end', 'médio', 'Família sorrindo no sofá, luzes da cidade pela janela', 'Saiba mais.', 'fd5b08b7b3f94b6b8c0d4c31c3a1f6e2.png'),
        ],
    },
}

JUDGE_SYSTEM = """Você avalia quadros de anúncios verticais para Reels/Stories. Para cada imagem recebida, responda somente JSON:
{"quadros":[{"indice":1,"texto_sobre_sujeito":false,"texto_legivel":true,"texto_duplicado":false,"sujeito_visivel":true,
"quadro_preenchido":true,"nota":4,"comentario":"..."}]}
- texto_sobre_sujeito: algum texto sobreposto cobre rosto, produto ou o elemento principal.
- texto_legivel: todo texto sobreposto pode ser lido no celular (contraste, tamanho, sem cortar). true se não houver texto.
- texto_duplicado: há texto sobreposto em cima de outro texto ou logo já gravado na imagem.
- sujeito_visivel: o elemento principal aparece inteiro o bastante para entender a cena.
- quadro_preenchido: sem faixas vazias grandes ou bordas sem imagem.
- nota: qualidade profissional do quadro de 1 (amador) a 5 (agência).
Seja exigente e consistente entre imagens."""


def resolve_asset(name):
    path = ASSETS / name
    if path.exists():
        return path
    matches = sorted(ASSETS.glob(name.split('.')[0][:8] + '*.png'))
    matches = [m for m in matches if '@base' not in m.name and '.base' not in m.name]
    if not matches:
        raise SystemExit(f'Mídia ausente: {name}')
    return matches[0]


def media_for(case, work):
    from PIL import Image
    media, scenes, beats = [], {}, []
    for index, (purpose, shot, visual, spoken, name) in enumerate(case['beats'], 1):
        source = resolve_asset(name)
        target = work / f'cena{index}{source.suffix}'
        shutil.copy(source, target)
        if source.suffix == '.mp4':
            import subprocess
            info = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=width,height,codec_type', '-of', 'json',
                                              str(target)], check=True, capture_output=True, text=True).stdout)
            video = next(s for s in info['streams'] if s['codec_type'] == 'video')
            kind, width, height, duration = 'video', video['width'], video['height'], float(info['format']['duration'])
        else:
            with Image.open(target) as image:
                width, height = image.size
            kind, duration = 'image', None
        asset = {'id': f'lab-cena-{index}', 'type': kind, 'width': width, 'height': height, 'duration': duration, 'path': str(target)}
        scenes[f'b{index}'] = asset
        media.append({**asset, 'name': target.name, 'mime': 'video/mp4' if kind == 'video' else 'image/png',
                      'meta': {'id': asset['id'], 'name': target.name, 'type': kind, 'size': target.stat().st_size, 'lastModified': 0,
                               'duration': duration, 'width': width, 'height': height}})
        beats.append({'id': f'b{index}', 'purpose': purpose, 'shot': shot, 'visual': visual, 'spoken': spoken, 'transition': 'cut' if index == 1 else 'cross dissolve'})
    return media, scenes, beats


def plan_for(variant, pkg, briefing):
    if variant == 'regras':
        return montage.rules_plan(pkg), None, 0.0
    started = time.time()
    plan, usage = montage.director_plan(pkg, text_callable=lambda messages, **options: chat_completion(messages, timeout=180, **options),
                                        model=variant, briefing=briefing)
    return plan, usage, time.time() - started


def render(timeline, media, dest, gpu):
    app = Flask('lab_montage', static_folder=str(REPO / 'aicentralv2/static'))
    os.environ.pop('CADU_RENDER_GPU', None)
    if gpu:
        os.environ['CADU_RENDER_GPU'] = gpu
    with app.app_context():
        render_project({'project_id': 'lab', 'revision': 1, 'timeline': timeline, 'media': media,
                        'options': {'format': 'mp4', 'quality': 'very_high', 'includeAudio': True}}, dest, timeout=1800)


def scene_frames(path, plan, pkg, out_prefix):
    import subprocess
    durations = montage._durations(plan, pkg)
    frames, cursor = [], 0.0
    for index, duration in enumerate(durations, 1):
        at = cursor + duration * .6
        target = Path(f'{out_prefix}-cena{index}.jpg')
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{at:.2f}', '-i', str(path), '-frames:v', '1', '-vf', 'scale=540:-2', '-q:v', '3', str(target)],
                       check=True, capture_output=True)
        frames.append(target)
        cursor += duration
    return frames


def judge(frames):
    content = []
    for index, frame in enumerate(frames, 1):
        content.append({'type': 'text', 'text': f'Imagem {index}:'})
        content.append({'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + base64.b64encode(frame.read_bytes()).decode()}})
    from aicentralv2.creative_modeling_generation import _json_content
    response = chat_completion([{'role': 'system', 'content': JUDGE_SYSTEM}, {'role': 'user', 'content': content}], model=JUDGE_MODEL,
                               max_tokens=None, temperature=0, response_format={'type': 'json_object'}, timeout=180)
    raw = response['message'].get('content')
    data = raw if isinstance(raw, dict) else _json_content(raw)
    return data.get('quadros') or []


def summarize(scores):
    count = max(1, len(scores))
    return {'nota': round(sum(float(s.get('nota') or 0) for s in scores) / count, 2),
            'texto_sobre_sujeito': sum(bool(s.get('texto_sobre_sujeito')) for s in scores),
            'texto_duplicado': sum(bool(s.get('texto_duplicado')) for s in scores),
            'ilegivel': sum(not s.get('texto_legivel', True) for s in scores),
            'sujeito_cortado': sum(not s.get('sujeito_visivel', True) for s in scores),
            'bordas': sum(not s.get('quadro_preenchido', True) for s in scores)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', choices=['metal', 'vulkan', 'gl'])
    parser.add_argument('--models', default='anthropic/claude-opus-5.5,anthropic/claude-sonnet-5.5,openai/gpt-5-mini')
    parser.add_argument('--cases', default='tecnologia,cemig')
    parser.add_argument('--out', type=Path, default=REPO / 'instance/lab-montage')
    parser.add_argument('--no-judge', action='store_true', help='só planos, renders e quadros (sem chave do OpenRouter para o juiz)')
    args = parser.parse_args()
    variants = ['regras'] + [m for m in args.models.split(',') if m]
    report = []
    for case_name in args.cases.split(','):
        case = CASES[case_name]
        work = args.out / case_name
        work.mkdir(parents=True, exist_ok=True)
        media, scenes, beats = media_for(case, work)
        pkg = montage.package(beats, scenes, width=1080, height=1920, duration=case['duration'], brand=case['brand'])
        links = {row['id']: {'ref': row['id'], 'type': row['type'], 'name': row['name'], 'duration': row['duration']} for row in media}
        base = json.loads((REPO / 'scripts/fixtures/opencut-empty-timeline.json').read_text())
        rendered = []
        for variant in variants:
            label = variant.split('/')[-1]
            try:
                plan, usage, seconds = plan_for(variant, pkg, case['briefing'])
            except Exception as error:  # um modelo fora do ar não derruba o A/B
                print(f'{case_name} {label}: falhou no plano: {error}')
                continue
            timeline, _ = apply_commands(base, montage.compile_plan(plan, pkg), links)
            dest = work / f'{label}.mp4'
            render(timeline, media, dest, args.gpu)
            frames = scene_frames(dest, plan, pkg, work / label)
            rendered.append({'case': case_name, 'variant': label, 'plan': plan, 'usage': usage, 'plan_seconds': round(seconds, 1),
                             'video': str(dest), 'frames': [str(f) for f in frames]})
            print(f'{case_name} {label}: plano em {seconds:.1f} s; textos: {[s["text"] for s in plan["scenes"]]}')
        # Juiz cego: não sabe qual variante gerou os quadros, que chegam em ordem embaralhada.
        for row in rendered:
            if args.no_judge:
                row['scores'], row['summary'] = [], summarize([])
                report.append(row)
                continue
            order = list(range(len(row['frames'])))
            random.Random(7).shuffle(order)
            scores = judge([Path(row['frames'][i]) for i in order])
            back = {order[pos]: score for pos, score in enumerate(scores[:len(order)])}
            row['scores'] = [back.get(i, {}) for i in range(len(order))]
            row['summary'] = summarize(row['scores'])
            report.append(row)
    print('\ncaso        variante              nota  sobre-sujeito duplicado ilegível cortado bordas  tempo  tokens')
    for row in report:
        s, usage = row['summary'], row['usage'] or {}
        tokens = f"{usage.get('prompt_tokens', 0)}+{usage.get('completion_tokens', 0)}" if usage else '-'
        print(f"{row['case']:11} {row['variant']:20} {s['nota']:5} {s['texto_sobre_sujeito']:13} {s['texto_duplicado']:9} {s['ilegivel']:8} "
              f"{s['sujeito_cortado']:7} {s['bordas']:6} {row['plan_seconds']:5}s {tokens}")
    (args.out / 'relatorio.json').write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str))
    print(f'\nArquivos em {args.out}')


if __name__ == '__main__':
    main()
