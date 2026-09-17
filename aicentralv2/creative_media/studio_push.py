"""Opt-in Web Push subscriptions and retryable, per-user completion delivery."""
import base64
import hashlib
import json
import time
from urllib.parse import urlsplit
from flask import request,session,send_file,current_app
from .http import studio_http as _http
from .studio_auth import studio_or_admin_required_api
from .studio_csrf import studio_csrf_required
from .studio import _scope,_write
from .storage import media_root


def keys():
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    from .queue_worker import file_claim
    root=media_root();path=root/'studio-vapid.pem'
    with file_claim(root/'studio-vapid.lock') as acquired:
        if not acquired:raise ValueError('Notificações estão sendo configuradas. Tente novamente.')
        if not path.exists():
            key=ec.generate_private_key(ec.SECP256R1())
            with path.open('xb') as handle:
                path.chmod(0o600);handle.write(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        key=serialization.load_pem_private_key(path.read_bytes(),None)
    public=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    return path,base64.urlsafe_b64encode(public).decode().rstrip('=')


def validate_subscription(raw):
    if not isinstance(raw,dict):raise ValueError('Assinatura inválida.')
    endpoint=str(raw.get('endpoint') or '');url=urlsplit(endpoint);host=url.hostname or ''
    allowed=host=='fcm.googleapis.com' or host.endswith('.push.services.mozilla.com') or host=='updates.push.services.mozilla.com' or host=='web.push.apple.com' or host.endswith('.notify.windows.com')
    if not allowed or url.scheme!='https' or url.port not in (None,443) or url.username or url.password or url.fragment or len(endpoint)>4096:raise ValueError('Serviço de notificações não reconhecido.')
    values=raw.get('keys') or {};clean={}
    for key,size in [('p256dh',65),('auth',16)]:
        value=str(values.get(key) or '')
        try:decoded=base64.urlsafe_b64decode(value+'='*(-len(value)%4))
        except Exception:raise ValueError('Chave de notificação inválida.')
        if len(decoded)!=size:raise ValueError('Chave de notificação inválida.')
        clean[key]=value
    return {'endpoint':endpoint,'keys':clean}


def register(bp):
    bp.add_url_rule('/api/format-lab/studio/push',view_func=subscription,methods=['GET','POST','DELETE'])
    bp.add_url_rule('/studio-notifications.js',view_func=service_worker)


def service_worker():
    response=send_file(current_app.static_folder+'/js/studio-notifications.js',mimetype='application/javascript',max_age=0)
    response.headers['Service-Worker-Allowed']='/studio/' if request.path.startswith('/studio/') else '/parametros/'
    response.headers['Cache-Control']='no-cache'
    return response


@studio_or_admin_required_api
@studio_csrf_required
def subscription():
    execute,body,ok,_=_http()
    def run():
        data=request.args if request.method=='GET' else body();root=_scope(data.get('client_id'));user=session.get('user_id')
        if request.method=='GET':
            try:import pywebpush
            except ImportError:return ok({'available':False})
            return ok({'available':True,'public_key':keys()[1]})
        sub=validate_subscription(data.get('subscription'));ident=hashlib.sha256(f'{user}:{sub["endpoint"]}'.encode()).hexdigest()[:32];path=root/f'push-{ident}.json'
        if request.method=='DELETE':path.unlink(missing_ok=True);return ok({'enabled':False})
        existing=[p for p in root.glob('push-*.json') if not p.name.startswith('push-delivery-') and json.loads(p.read_text()).get('user_id')==user]
        if len(existing)>=10 and not path.exists():raise ValueError('Limite de dez dispositivos por marca.')
        created=json.loads(path.read_text()).get('created_at',time.time()) if path.exists() else time.time()
        _write(path,{'id':ident,'user_id':user,'client_id':int(data['client_id']),'subscription':sub,'created_at':created,'origin':request.url_root.rstrip('/'),'enabled':True})
        path.chmod(0o600)
        return ok({'enabled':True})
    return execute(run)


def deliver(root,repository):
    """Terminal jobs are the outbox source; delivery checkpoints survive restarts."""
    from .queue_worker import file_claim
    try:from pywebpush import webpush,WebPushException
    except ImportError:return 0
    sent=0
    for path in root.glob('studio/*/push-*.json'):
        if path.name.startswith('push-delivery-'):continue
        with file_claim(path.with_suffix('.lock')) as acquired:
            if not acquired:continue
            try:
                sub=json.loads(path.read_text());jobs=[]
                if not sub.get('enabled'):continue
                for row in repository.list_jobs(sub['client_id'],sub['user_id']):
                    stamp=row.get('completed_at') or row.get('updated_at') or row.get('created_at')
                    if isinstance(stamp,str):
                        from datetime import datetime
                        stamp=datetime.fromisoformat(stamp.replace('Z','+00:00'))
                    when=stamp.timestamp() if hasattr(stamp,'timestamp') else float(stamp or 0)
                    if row.get('status') in {'ready','failed'} and when>=sub['created_at']:jobs.append((row['public_id'],row['status']))
                for record in list(path.parent.glob('export-*.json'))+list(path.parent.glob('task-*.json')):
                    row=json.loads(record.read_text())
                    if row.get('user_id')==sub['user_id'] and row.get('status') in {'ready','failed'} and row.get('created_at',0)>=sub['created_at']:
                        jobs.append((('task:' if record.name.startswith('task-') else 'export:')+row['id'],row['status']))
                for ident,status in jobs:
                    digest=hashlib.sha256(f'{sub["id"]}:{ident}:{status}'.encode()).hexdigest()[:32]
                    checkpoint=path.parent/f'push-delivery-{digest}.json';delivery=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
                    if delivery.get('sent') or delivery.get('attempts',0)>=5 or delivery.get('retry_at',0)>time.time():continue
                    payload={'title':'Cadu Studio','body':'Seu trabalho está pronto.' if status=='ready' else 'Um trabalho precisa de atenção.','tag':ident,'url':f'/studio/modelagem-criativos/video?client={sub["client_id"]}#render={ident}'}
                    try:
                        webpush(subscription_info=sub['subscription'],data=json.dumps(payload),vapid_private_key=str(keys()[0]),vapid_claims={'sub':sub['origin']},ttl=86400,timeout=10)
                        _write(checkpoint,{'sent':True,'at':time.time()});sent+=1
                    except WebPushException as error:
                        if error.response is not None and error.response.status_code in {404,410}:
                            _write(path,{**sub,'enabled':False});break
                        attempts=delivery.get('attempts',0)+1;_write(checkpoint,{'attempts':attempts,'retry_at':time.time()+min(3600,30*2**attempts)})
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Studio notification delivery failed')
    return sent
