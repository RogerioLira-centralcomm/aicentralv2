"""Numeric animation contract shared with the browser. No client expressions."""
import math

DEFAULTS={'x':.5,'y':.5,'scale':1.,'rotation':0.,'opacity':1.}
BOUNDS={'x':(-1,2),'y':(-1,2),'scale':(.1,4),'rotation':(-360,360),'opacity':(0,1)}


def normalize_keyframes(raw):
    result={}
    for row in (raw if isinstance(raw,list) else [])[:60]:
        if not isinstance(row,dict):continue
        try:
            at=float(row.get('time',0))
            if not math.isfinite(at):continue
            values={}
            for key,default in DEFAULTS.items():
                value=float(row.get(key,default));low,high=BOUNDS[key]
                values[key]=max(low,min(high,value)) if math.isfinite(value) else default
        except (ValueError,TypeError):continue
        at=round(max(0,min(1200,at)),3)
        result[at]={'time':at,**values,'ease':row.get('ease') if row.get('ease') in {'linear','ease','hold'} else 'linear'}
    return sorted(result.values(),key=lambda row:row['time'])


def value_at(frames,key,time,default=None):
    if not frames:return DEFAULTS[key] if default is None else default
    if time<=frames[0]['time']:return frames[0][key]
    for a,b in zip(frames,frames[1:]):
        if time<b['time']:
            p=(time-a['time'])/(b['time']-a['time'])
            p=0 if a['ease']=='hold' else p*p*(3-2*p) if a['ease']=='ease' else p
            return a[key]+(b[key]-a[key])*p
    return frames[-1][key]


def expression(frames,key,clock='t',offset=0):
    """Build a bounded FFmpeg expression exclusively from normalized numbers."""
    expr=str(frames[-1][key]);t=f'({clock}-{float(offset)})'
    for a,b in reversed(list(zip(frames,frames[1:]))):
        p=f'(({t}-{a["time"]})/{b["time"]-a["time"]})'
        p='0' if a['ease']=='hold' else f'({p}*{p}*(3-2*{p}))' if a['ease']=='ease' else p
        val=f'({a[key]}+({b[key]-a[key]})*{p})'
        expr=f'if(lt({t},{b["time"]}),{val},{expr})'
    return f'if(lte({t},{frames[0]["time"]}),{frames[0][key]},{expr})'


def transform_filters(label,frames,prefix,offset=0):
    scale=expression(frames,'scale',offset=offset)
    angle=expression(frames,'rotation',offset=offset)
    opacity=expression(frames,'opacity',clock='T',offset=offset)
    filters=[f"[{label}]format=rgba,scale=w='max(2,trunc(iw*({scale})/2)*2)':h='max(2,trunc(ih*({scale})/2)*2)':eval=frame,rotate=angle='({angle})*PI/180':ow='hypot(iw,ih)':oh='hypot(iw,ih)':c=none[{prefix}rot]"]
    filters.append(f"[{prefix}rot]geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*({opacity})'[{prefix}]")
    return filters
