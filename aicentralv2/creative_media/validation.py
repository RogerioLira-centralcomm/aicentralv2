"""Inspect actual media, never infer a delivered stream from the request."""
import json
import subprocess
import tempfile
from pathlib import Path


def inspect_video(payload):
    with tempfile.TemporaryDirectory(prefix='studio-probe-') as directory:
        path = Path(directory) / 'video.mp4'
        path.write_bytes(payload)
        try:
            result = subprocess.run(['ffprobe','-v','error','-show_entries',
                'format=duration:stream=codec_type,width,height,sample_aspect_ratio:stream_tags=rotate:stream_side_data=rotation',
                '-of','json',str(path)],check=True,capture_output=True,text=True,timeout=30)
            data = json.loads(result.stdout)
            video = next(row for row in data.get('streams',[]) if row.get('codec_type') == 'video')
            width, height = int(video['width']), int(video['height'])
            sar = str(video.get('sample_aspect_ratio') or '1:1').split(':')
            if len(sar) == 2 and float(sar[1]) > 0:
                width = round(width * float(sar[0]) / float(sar[1]))
            rotation = next((r.get('rotation',0) for r in video.get('side_data_list',[]) if 'rotation' in r), video.get('tags',{}).get('rotate',0))
            if abs(int(rotation)) % 180 == 90:
                width,height = height,width
            duration = float(data['format']['duration'])
            if width <= 0 or height <= 0 or duration <= 0:
                raise ValueError('invalid dimensions')
            return {'width':width,'height':height,'duration':duration,
                    'has_audio':any(row.get('codec_type') == 'audio' for row in data.get('streams',[]))}
        except (OSError, subprocess.SubprocessError, KeyError, ValueError, StopIteration) as error:
            raise ValueError('Não foi possível validar o vídeo recebido. O resultado não foi marcado como pronto.') from error


def validate_delivery(payload, plan, *, technical=False):
    meta = inspect_video(payload)
    ratio = plan.get('aspect_ratio') if technical else plan.get('piece_ratio')
    a,b = (int(v) for v in str(ratio or '16:9').split(':'))
    if abs(meta['width']/meta['height'] - a/b)/(a/b) > .012:
        raise ValueError(f"O provedor entregou {meta['width']}×{meta['height']}, mas o projeto exige {ratio}. O vídeo foi preservado para revisão; nenhuma nova geração foi cobrada.")
    duration = float(plan.get('duration') or 0)
    if duration and abs(meta['duration']-duration) > max(.6,duration*.05):
        raise ValueError(f"O vídeo recebido tem {meta['duration']:.1f}s; o projeto solicita {duration:g}s. Revise o resultado antes de exportar.")
    return meta
