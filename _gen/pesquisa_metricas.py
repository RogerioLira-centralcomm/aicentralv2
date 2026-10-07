"""Pesquisa pública (Perplexity sonar via OpenRouter) de alcance, viewability e conclusão por canal. Só grava em arquivo de revisão."""
import json, re
from run import app
from aicentralv2.db import get_db
from aicentralv2.services import openrouter_service as s
Q = ("Canal de mídia/publicidade: {nome} ({cat}) no Brasil. Busque dados PÚBLICOS e recentes (2024-2026) de: "
 "1) alcance (usuários ativos mensais ou audiência no Brasil; se só houver global, diga); 2) viewability média de anúncios; 3) taxa de conclusão (completion rate/VTR) de anúncios em vídeo/áudio. "
 "Responda SOMENTE JSON: {{\"alcance\":\"texto curto ex: +20 mi usuários/mês\",\"alcance_escopo\":\"brasil|global|null\",\"viewability\":número ou null,\"conclusao\":número ou null,\"fontes\":[\"url\"],\"ano\":\"aaaa\",\"obs\":\"curta\"}}. "
 "Use null quando não houver número público confiável; nunca estime.")
out = {}
with app.app_context():
    cur = get_db().cursor()
    cur.execute("select slug,nome,categoria,alcance,viewability,completion_rate from cadu_canais where is_active and coalesce(categoria,'')<>'Portais' and slug<>'waze' order by categoria,nome")
    rows = [dict(r) if isinstance(r, dict) else dict(zip(['slug','nome','categoria','alcance','viewability','completion_rate'], r)) for r in cur.fetchall()]
    for r in rows:
        try:
            m = s._openrouter_chat_completion({"model": "perplexity/sonar", "messages": [{"role": "user", "content": Q.format(nome=r['nome'], cat=r['categoria'])}]}, timeout=120)["message"]
            txt = m.get("content") or ""
            j = json.loads(re.search(r'\{.*\}', txt, re.S).group(0))
        except Exception as e:
            j = {"erro": str(e)[:120]}
        out[r['slug']] = {"atual": {k: r[k] for k in ('alcance','viewability','completion_rate')}, "pesquisa": j}
        print(r['slug'], j.get('alcance'), j.get('viewability'), j.get('conclusao'), j.get('erro',''), flush=True)
json.dump(out, open('_gen/pesquisa_metricas.json', 'w'), ensure_ascii=False, indent=1)
