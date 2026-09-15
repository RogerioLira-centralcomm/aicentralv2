"""Non-destructive speech edits. All intervals remain in source seconds."""
import math
import re
import subprocess


def options(raw):
    raw=raw if isinstance(raw,dict) else {}
    def bounded(key,default,low,high):
        try:value=float(raw.get(key,default))
        except (TypeError,ValueError):value=default
        return max(low,min(high,value)) if math.isfinite(value) else default
    return {'enabled':raw.get('enabled',False) is True,'mode':'aggressive' if raw.get('mode')=='aggressive' else 'moderate',
            'max_cuts':int(bounded('max_cuts',30,1,30)), 'transition':raw.get('transition') if raw.get('transition') in {'fade','fadeblack'} else 'cut',
            'transition_duration':bounded('transition_duration',.1,.05,.5)}


def silences(source,duration,mode):
    threshold=.4 if mode=='aggressive' else .7
    result=subprocess.run(['ffmpeg','-v','info','-i',str(source),'-vn','-af',f'silencedetect=noise=-35dB:d={threshold}','-f','null','-'],capture_output=True,text=True,check=True,timeout=300)
    rows=[];start=None
    for kind,value in re.findall(r'silence_(start|end): ([0-9.]+)',result.stderr):
        if kind=='start':start=float(value)
        elif start is not None:rows.append((start,min(duration,float(value))));start=None
    if start is not None:rows.append((start,duration))
    return rows


def analyze(duration,words,quiet,raw):
    config=options(raw);aggressive=config['mode']=='aggressive'
    threshold=.4 if aggressive else .7;pad=.06 if aggressive else .125
    words=sorted([w for w in words if 0<=w['start']<w['end']<=duration],key=lambda w:w['start'])
    if not words:
        return {'cuts':[],'review':[],'duration':duration,'options':config,'removed_duration':0}
    candidates=[]
    for start,end in quiet:
        # Silence detector alone can mistake soft consonants for silence.
        a=max(0,start)+pad;b=min(duration,end)-pad
        if end-start<threshold or b-a<.1:continue
        if any(w['start']-.04<b and w['end']+.04>a for w in words):continue
        candidates.append({'in':round(a,3),'out':round(b,3),'reason':'Pausa','confidence':1.0})
    review=[]
    for i,w in enumerate(words):
        token=re.sub(r'[^\w]','',w['text'].lower())
        previous=words[i-1] if i else None;following=words[i+1] if i+1<len(words) else None
        isolated=(not previous or w['start']-previous['end']>=.12) and (not following or following['start']-w['end']>=.12)
        if token in {'hum','hmm','ahn','ãh'} and isolated and w.get('probability',0)>=.9:
            candidates.append({'in':max(0,w['start']-.03),'out':min(duration,w['end']+.03),'reason':'Hesitação isolada','confidence':.95})
        elif previous and token and token==re.sub(r'[^\w]','',previous['text'].lower()):
            review.append({'in':w['start'],'out':w['end'],'reason':'Repetição — revisar antes de remover'})
    chosen=[]
    for row in sorted(candidates,key=lambda c:(-c['confidence'],-(c['out']-c['in']))):
        if len(chosen)>=config['max_cuts']:break
        if any(row['in']<r['out']+.1 and row['out']>r['in']-.1 for r in chosen):continue
        chosen.append(row)
    chosen.sort(key=lambda c:c['in'])
    return {'cuts':chosen,'review':review,'duration':duration,'options':config,'removed_duration':sum(c['out']-c['in'] for c in chosen)}
