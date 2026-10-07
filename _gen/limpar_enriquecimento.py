import json, re
SRC = json.load(open('pesquisa_enriquecimento.json'))
META = re.compile(r'não (encontr|localiz|há\b|existe|foi |deve|trazem|detalham|informa|divulga|disponibiliza|publica|é exclusivo)|sem (fonte|dado|base|número|detalhar)|nesta (busca|base)|fontes? públicas?|acessadas|consultada|\bnulos?\b|\bnull\b|^portanto|cautela|recorte (público|demográfico)', re.I)

def limpo(texto):
    if not texto: return ''
    t = re.sub(r'\[\d+\]', '', texto)
    t = re.sub(r'\s+', ' ', t).strip()
    frases = re.split(r'(?<=[.;])\s+', t)
    frases = [f[:1].upper() + f[1:] for f in frases]
    manter = [f for f in frases if not META.search(f)]
    t = ' '.join(re.sub(r'[;,]$', '.', f.strip()) for f in manter).strip()
    t = re.sub(r'\s+([.,;])', r'\1', t)
    t = re.sub(r'[,;:]+$', '', t)
    if t and t[-1] not in '.!?': t += '.'
    return t if len(t) >= 40 else ''

EXCLUIR_PERFIL = {'deezer', 'google-dv360'}  # o que sobra é só a ausência de dado
OUT = {}
for slug, d in SRC.items():
    p = d.get('pesquisa') or {}
    OUT[slug] = {c: limpo(p.get(c)) for c in ('perfil_audiencia', 'melhor_uso')}
    if slug in EXCLUIR_PERFIL: OUT[slug]['perfil_audiencia'] = ''
    OUT[slug]['fontes'] = (p.get('fontes') or [])[:4]
json.dump(OUT, open('enriquecimento_limpo.json', 'w'), ensure_ascii=False, indent=1)
tot = sum(1 for v in OUT.values() if v['perfil_audiencia']); mu = sum(1 for v in OUT.values() if v['melhor_uso'])
print(len(OUT), 'canais | perfil_audiencia:', tot, '| melhor_uso:', mu)
print('sem perfil:', [s for s, v in OUT.items() if not v['perfil_audiencia']])
for s in ('experian-dmp', 'eletromidia', 'spotify', 'netflix', 'uber'):
    if s in OUT: print('\n##', s); print('PERFIL:', OUT[s]['perfil_audiencia']); print('USO:', OUT[s]['melhor_uso'])
