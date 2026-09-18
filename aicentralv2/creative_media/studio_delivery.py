"""Named MP4/GIF exports and explicitly published, token-scoped HTML players."""
import hashlib
import html
import json
from math import gcd
import re
import secrets
import subprocess
import unicodedata
from pathlib import Path
from flask import request,send_file,abort,Response
from .file_lock import exclusive_file_lock
from .studio import _write
from .storage import media_root


def slug(value,fallback):
    value=unicodedata.normalize('NFKD',str(value or '')).encode('ascii','ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+','_',value).strip('_')[:64].rstrip('_') or fallback


def reserve_delivery(root,data,service,ratio):
    raw=data.get('delivery') if isinstance(data.get('delivery'),dict) else {}
    kind=raw.get('format','mp4')
    if kind not in {'mp4','gif','html'}:raise ValueError('Escolha MP4, GIF ou HTML público.')
    brand=str(raw.get('brand') or f"marca_{data.get('client_id')}")
    client=service.get_client(data.get('client_id'))
    if isinstance(client,dict):brand=client.get('name') or client.get('nome') or brand
    creative=str(raw.get('creative') or 'criativo')[:120]
    key=hashlib.sha256(slug(creative,'criativo').encode()).hexdigest()[:32]
    with exclusive_file_lock(root/f'delivery-sequence-{key}.lock'):
        path=root/f'delivery-sequence-{key}.json'
        version=(json.loads(path.read_text()).get('version',0) if path.exists() else 0)+1
        _write(path,{'version':version})
    return {'format':kind,'brand':str(brand)[:120],'creative':creative,'version':version,
            'ratio':ratio if ratio in {'9:16','16:9','1:1','4:5','3:4','4:3','21:9'} else '',
            'client_id':int(data['client_id']),'origin':request.url_root.rstrip('/'),
            'public_base':'/parametros/studio/public' if request.path.startswith('/parametros/') else '/public',
            'public_token':secrets.token_hex(24) if kind=='html' else ''}


def filename(delivery,width,height):
    ratio=delivery.get('ratio') or f'{width//gcd(width,height)}:{height//gcd(width,height)}'
    return f"{slug(delivery.get('brand'),'marca')}_v{int(delivery.get('version',1)):03d}_{slug(delivery.get('creative'),'criativo')}_{slug(ratio.replace(':','x'),'formato')}_{width}x{height}.{delivery.get('format','mp4')}"


def player(title,video_url):
    title=html.escape(title);url=html.escape(video_url,quote=True)
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>{title}</title><style>html,body{{margin:0;min-height:100%;background:#12171c;color:#fff;font-family:system-ui}}main{{min-height:100vh;display:grid;place-content:center;padding:16px;box-sizing:border-box}}h1{{font-size:18px;font-weight:500;text-align:center}}video{{display:block;max-width:100%;width:auto;height:auto;max-height:85vh;margin:auto;background:#000;border-radius:12px}}</style></head><body><main><h1>{title}</h1><video controls playsinline preload="metadata" src="{url}">Seu navegador não suporta vídeo.</video></main></body></html>'''


def finish_delivery(root,ident,envelope):
    delivery=envelope.get('delivery')
    if not delivery:return {}
    info=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(root/f'{ident}.mp4')],check=True,capture_output=True,text=True,timeout=20)
    stream=json.loads(info.stdout)['streams'][0];kind=delivery['format'];public_url=''
    if kind=='gif':
        subprocess.run(['ffmpeg','-y','-v','error','-i',str(root/f'{ident}.mp4'),'-filter_complex_threads','1','-filter_complex','fps=12,scale=640:640:force_original_aspect_ratio=decrease:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=sierra2_4a','-loop','0',str(root/f'{ident}.gif')],check=True,capture_output=True,timeout=600)
        from PIL import Image
        with Image.open(root/f'{ident}.gif') as image:stream={'width':image.width,'height':image.height}
    if kind=='html':
        token=delivery['public_token'];public_url=f"{delivery.get('public_base') or '/public'}/{token}"
        body=player(f"{delivery['brand']} · {delivery['creative']}",delivery['origin']+public_url+'/video')
        (root/f'{ident}.html').write_text(body,encoding='utf-8')
        public_root=media_root()/'studio-public';public_root.mkdir(parents=True,exist_ok=True)
        _write(public_root/f'{token}.json',{'scope':root.name,'id':ident})
    return {'filename':filename(delivery,stream['width'],stream['height']),'format':kind,
            # The worker has no request host. The browser builds the private
            # download URL from its own product API root.
            'download_url':'',
            'public_url':public_url}


def register(bp):
    bp.add_url_rule('/studio/public/<token>',view_func=public_player)
    bp.add_url_rule('/studio/public/<token>/video',view_func=public_video)


def published(token):
    if not re.fullmatch(r'[a-f0-9]{48}',token):abort(404)
    path=media_root()/'studio-public'/f'{token}.json'
    if not path.is_file():abort(404)
    ref=json.loads(path.read_text());root=media_root()/'studio'/ref['scope']
    record=root/f"export-{ref['id']}.json"
    if not record.is_file():abort(404)
    row=json.loads(record.read_text())
    if row.get('status')!='ready' or row.get('delivery',{}).get('public_token')!=token:abort(404)
    return root,ref['id'],row


def public_player(token):
    root,ident,_=published(token)
    response=Response((root/f'{ident}.html').read_text(),mimetype='text/html')
    response.headers['Content-Security-Policy']="default-src 'none'; style-src 'unsafe-inline'; media-src 'self'; base-uri 'none'; frame-ancestors *"
    response.headers['X-Robots-Tag']='noindex, nofollow'
    response.headers['Referrer-Policy']='no-referrer'
    return response


def public_video(token):
    root,ident,row=published(token)
    response=send_file(root/f'{ident}.mp4',mimetype='video/mp4',conditional=True)
    response.headers['X-Robots-Tag']='noindex, nofollow'
    return response
