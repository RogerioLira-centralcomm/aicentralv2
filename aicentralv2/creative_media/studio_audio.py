"""Bounded, deterministic voice enhancement shared by composition renders."""
from .studio import number


def normalize(raw):
    raw=raw if isinstance(raw,dict) else {}
    return {'preset':raw.get('preset') if raw.get('preset') in {'clean','warm','denoise'} else 'off',
            'amount':number(raw.get('amount'),.5,0,1)}


def filters(raw):
    settings=normalize(raw);preset=settings['preset'];amount=settings['amount']
    if preset=='off' or amount==0:return 'anull'
    noise=6+amount*(18 if preset=='denoise' else 10)
    gain=round(amount*3,2) if preset=='warm' else 0
    return (f'highpass=f=65,afftdn=nr={noise}:nf=-40:tn=1,'
            f'equalizer=f=160:t=q:w=1:g={gain},'
            f'equalizer=f=3000:t=q:w=1:g={amount},'
            'acompressor=threshold=0.125:ratio=2:attack=15:release=150:makeup=1.4,'
            'alimiter=limit=0.95:level=false:latency=true')
