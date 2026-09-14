"""Sessão 2 — quatro famílias de inventário digital."""

from ..logos import logo_path
from .markup import block, esc, figure, h2, h3, notes, p, sources

NOTAS = {
    "tese": "Quatro famílias. Cada uma tem regra de substituição. Não é census.",
    "nao_repetir": "Não repetir 185 mi / 9h09. Não definir Instagram. Outdoor fica na sessão Places.",
    "pergunta": "De qual família vocês tirariam 20% do budget deste brief — e para onde mandariam?",
    "tempo": "15 minutos",
}

FONTES = [
    {
        "url": "https://datareportal.com/reports/digital-2026-brazil",
        "titulo": "Digital 2026 Brazil — ad reach por plataforma, out/2025",
        "resumo": "Alcance de anúncio, não MAU. LinkedIn = members.",
    },
    {
        "url": "oficial:catalogo-canais-centralx",
        "titulo": "Catálogo de canais CentralX",
        "resumo": "O que a mesa já transaciona. Floor e alcance são hipótese comercial, não censo.",
    },
]


def _canal(key, name, body, regra):
    logo = figure(logo_path(key), f"Logo {name}", "ts-canal-logo")
    return (
        f'<article class="ts-canal" data-canal="{esc(key)}" id="canal-{key}">'
        f"<!-- CANAL:{key} -->"
        f"{logo}<h3>{esc(name)}</h3>"
        f"{body}"
        f"<p><strong>Tiro verba daqui se…</strong> {regra}</p>"
        f"<!-- /CANAL:{key} -->"
        "</article>"
    )


def html():
    return (
        h2("Quatro famílias de inventário digital")
        + notes(
            "<strong>Palco · 15 min.</strong> Quatro famílias, um case por "
            "família no máximo. Outdoor e aeroporto não entram. Fechar cada "
            "família com a regra de substituição."
        )
        + block(
            "tese",
            p(
                "O bloco anterior escolheu a moeda. Este escolhe de onde sai "
                "e para onde entra a verba. Os cards abaixo usam alcance de "
                "anúncio do Digital 2026 Brazil (final de 2025) e o que o "
                "catálogo CentralX já transaciona. Ad reach não é MAU. "
                "LinkedIn é member.",
            ),
        )
        + h2("Social e profissional")
        + block(
            "case",
            p(
                "Feed versus short-form. B2B versus consumer. A família ganha "
                "quando o brief precisa de recorte de intenção ou de volume "
                "de vídeo curto. Perde quando o KPI é dwell longo ou brand "
                "safety editorial.",
            )
            + _canal(
                "linkedin",
                "LinkedIn",
                p(
                    "<strong>O que se compra.</strong> 90 milhões de membros "
                    "no Brasil (final de 2025) — base cadastrada, não MAU. "
                    "Sponsored Content, document, thought leader, lead gen. "
                    "O CentralX opera o canal no catálogo B2B.",
                    "<strong>Case — pendente de fonte pública com número.</strong> "
                    "Não inventar CPL. Usar o que o time trouxer no anexo.",
                ),
                "o KPI for reach consumer ou o criativo só existir em 9:16.",
            )
            + _canal(
                "instagram",
                "Instagram",
                p(
                    "<strong>O que se compra.</strong> 147 milhões de ad reach "
                    "(87,3% dos adultos 18+). Reels, Stories, feed. Catálogo "
                    "CentralX: formatos 9:16 e 4:5.",
                    "<strong>Case — pendente</strong> com ROAS público. Sem "
                    "número, não abrir.",
                ),
                "o brief for B2B de consideração e o feed estiver canibalizando frequência.",
            )
            + _canal(
                "tiktok",
                "TikTok",
                p(
                    "<strong>O que se compra.</strong> 131 milhões 18+ "
                    "(80,3% dos adultos). In-feed, Spark, TopView. Ambiente "
                    "de vídeo curto — estático aqui é desperdício. O Max "
                    "retoma isso depois do coffee.",
                ),
                "o KPI for completion longo ou o legal bloquear UGC.",
            ),
        )
        + h2("Editorial e portais")
        + block(
            "case",
            p(
                "Contexto e brand safety contra CPM do feed. A família ganha "
                "na primeira onda de construção quando o cliente precisa de "
                "adjacência jornalística. Perde quando o brief é performance "
                "cega em open web.",
            )
            + _canal(
                "g1",
                "g1",
                p(
                    "<strong>O que se compra.</strong> Maior portal de notícia "
                    "do país no catálogo CentralX. Display, native, takeover. "
                    "Viewability de portal ≠ atenção de portal — o Lucas "
                    "separa as famílias de formato às 11h35.",
                ),
                "o inventário aberto estiver sem deal e sem adjacência.",
            )
            + _canal(
                "cnn",
                "CNN Brasil",
                p(
                    "<strong>O que se compra.</strong> Portal + TV. Alcance "
                    "declarado no catálogo: cerca de 36,5 milhões/mês no "
                    "portal em 2024. Classe AB como recorte de venda, não "
                    "como censo.",
                ),
                "o brief for massa e o CPM não pagar o contexto.",
            )
            + _canal(
                "sbt",
                "SBT",
                p(
                    "<strong>O que se compra.</strong> Portal, +SBT e SBT News. "
                    "Copa 2026 no catálogo como janela — não como garantia "
                    "de share. Logo real do acervo CentralX.",
                ),
                "o cliente exigir ambiente news premium e o adjacente não aguentar.",
            )
            + _canal(
                "serasa",
                "Serasa",
                p(
                    "<strong>O que se compra.</strong> Intenção de crédito e "
                    "serviço financeiro no portal Experian. Alto contexto, "
                    "baixo glamour. Serve fintech — o briefing A da banca.",
                ),
                "o legal não assinar ambiente de cobrança / score.",
            ),
        )
        + h2("Utilidade e commerce")
        + block(
            "case",
            p(
                "Atenção em tarefa, não em lazer. Incrementality contra a "
                "mídia do próprio app. A família ganha no hábito e no "
                "deslocamento. Perde quando o KPI é brand fame.",
            )
            + _canal(
                "uber",
                "Uber",
                p(
                    "<strong>O que se compra.</strong> Display e vídeo no app "
                    "durante a corrida. Dwell de espera, não de feed. Logo "
                    "do acervo CentralX.",
                ),
                "o brief for consideração longa e o criativo precisar de som.",
            )
            + _canal(
                "99",
                "99",
                p(
                    "<strong>O que se compra.</strong> Mesma família da Uber, "
                    "outra base. Não somar as duas como UU nacional.",
                ),
                "já houver teto de frequência em mobility na praça.",
            )
            + _canal(
                "ifood",
                "iFood",
                p(
                    "<strong>O que se compra.</strong> Home, busca e intersticial "
                    "no app. Canibaliza mídia própria do marketplace — "
                    "escrever a restrição no brief da rede de food.",
                    "<strong>Case público 2025 — pendente</strong> até o "
                    "agente buscar com a web ligada ou o instrutor anexar PDF.",
                ),
                "o cliente já paga mídia interna do app e o incremental não aparece.",
            )
            + _canal(
                "amazon",
                "Amazon",
                p(
                    "<strong>O que se compra.</strong> Retail media e, no "
                    "catálogo, áudio Amazon Music. Não tratar Prime Video "
                    "aqui — vídeo de sessão está na família seguinte.",
                ),
                "não houver SKU ou retail data para fechar o loop.",
            ),
        )
        + h2("Ambientes de sessão")
        + block(
            "case",
            p(
                "Completion e atenção longa. Custo de entrada contra TV e "
                "portal. A família ganha quando o brief pede dwell. Perde "
                "quando a verba não paga o floor.",
            )
            + _canal(
                "spotify",
                "Spotify",
                p(
                    "<strong>O que se compra.</strong> Audio ads não skipáveis, "
                    "playlist, takeover. Catálogo CentralX declara completion "
                    "alto em áudio — usar como hipótese de formato, não como "
                    "promessa de campanha sem medição.",
                ),
                "o criativo só existir em vídeo e não houver versão de 15s/30s.",
            )
            + _canal(
                "netflix",
                "Netflix",
                p(
                    "<strong>O que se compra.</strong> Plano com anúncios, "
                    "ambiente curado. Floor alto. Brand safety é o produto.",
                ),
                "a verba da primeira onda não pagar o mínimo do catálogo.",
            )
            + _canal(
                "prime",
                "Prime Video",
                p(
                    "<strong>O que se compra.</strong> Pre-roll, mid-roll, "
                    "pause ads. Dado de compra Amazon como hipótese — só "
                    "entrar se o brief tiver retail.",
                ),
                "não houver ponte com Amazon Ads ou o KPI for só fame.",
            )
            + _canal(
                "disney",
                "Disney+",
                p(
                    "<strong>O que se compra.</strong> Plano com anúncios e "
                    "janelas ao vivo. Família e franquia. Não é massa TikTok.",
                ),
                "o recorte de marca for adulto e o conteúdo da adjacência não assinar.",
            )
            + _canal(
                "hbo",
                "Max / HBO",
                p(
                    "<strong>O que se compra.</strong> Premium, séries, brand "
                    "safe. Mesma lógica de floor do Netflix.",
                ),
                "o brief for CPA de app e o cliente recusar ambiente de sessão.",
            ),
        )
        + sources(
            '<a href="https://datareportal.com/reports/digital-2026-brazil">Digital 2026 Brazil — ad reach por plataforma, out/2025</a>',
            "Catálogo de canais CentralX (alcance e floor de entrada — hipótese comercial, não censo)",
        )
    )
