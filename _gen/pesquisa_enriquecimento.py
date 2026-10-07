"""Pesquisa pública (Perplexity sonar via OpenRouter) de alcance, viewability e conclusão por canal. Só grava em arquivo de revisão."""
import json, re
from run import app
from aicentralv2.db import get_db
from aicentralv2.services import openrouter_service as s
Q = ("Canal de mídia/publicidade: {nome} ({cat}) no Brasil. Busque dados PÚBLICOS e recentes (2024-2026) para um catálogo de planejamento de mídia. "
 "Responda SOMENTE JSON: {{\"perfil_audiencia\":\"1-2 frases: quem usa (idade, classe, gênero) com números se públicos\",\"formatos_anuncio\":[\"formatos de anúncio oferecidos no Brasil\"],\"segmentacao\":[\"opções de segmentação disponíveis\"],\"medicao\":[\"parceiros/métricas de medição (ex: Nielsen, IAS, brand lift)\"],\"modelo_compra\":\"CPM/CPV/leilão/reserva (sem preços)\",\"melhor_uso\":\"1 frase\",\"novidades\":\"lançamento recente de anúncios, se houver\",\"fontes\":[\"url\"],\"ano\":\"aaaa\"}}. "
 "Nunca informe preços. Use null ou lista vazia quando não houver fonte pública; nunca invente.")
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
        print(r['slug'], (j.get('perfil_audiencia') or '')[:70], len(j.get('formatos_anuncio') or []), j.get('erro',''), flush=True)
json.dump(out, open('_gen/pesquisa_enriquecimento.json', 'w'), ensure_ascii=False, indent=1)
