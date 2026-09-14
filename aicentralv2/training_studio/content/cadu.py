"""Sessão 4 — operar o plano com a Skill Cadu."""

from .markup import block, h2, h3, notes, p, sources, ul

NOTAS = {
    "tese": "Cadu é a mesa, não a demo de IA. Restrição → catálogo → first-wave → correção.",
    "nao_repetir": "Não repetir 185 mi, 9h09, ANAC. Sem tour de feature.",
    "pergunta": "Qual restrição deste brief o Cadu não pode inventar?",
    "tempo": "15 minutos",
}

FONTES = [
    {
        "url": "oficial:skill-cadu",
        "titulo": "Skill Cadu / catálogo CentralX",
        "resumo": "Restrição → catálogo real → first-wave → correção. Sem inventar mix.",
    },
]


def html():
    return (
        h2("Operar o plano — Skill Cadu")
        + notes(
            "<strong>Palco · 15 min.</strong> Cinco passos no quadro. "
            "Places entra como família de inventário se o brief tiver lugar. "
            "Sem slide de produto."
        )
        + block(
            "tese",
            p(
                "O planejador desta sala não começa no Excel vazio. Começa "
                "com restrição. A Skill de mídia com inteligência de "
                "planejamento Cadu amarra o que já foi decidido: moeda de "
                "valor, família de inventário, e — se o brief tiver sítio — "
                "o recorte Places. IA aqui é consulta ao catálogo real. "
                "Não é mix alucinado.",
            ),
        )
        + block(
            "tese",
            h3("Cinco passos na mesa")
            + ul(
                [
                    "<strong>1. Briefing e restrições.</strong> Objetivo, praça, verba, recorte de marca, brand safety, se pode ou não open web, se Places entra.",
                    "<strong>2. Catálogo CentralX.</strong> Famílias digitais + Places. Só o que se transaciona. Sem canal fantasma.",
                    "<strong>3. Hipótese de mix.</strong> Percentual por família, não por 16 logos. Substituição escrita (“tiro 20% de sessão se o floor não caber”).",
                    "<strong>4. KPI da primeira onda.</strong> Uma métrica por formato — atenção, VTR, CTR qualificado, CPA de teste, presença no recorte. A moeda da abertura.",
                    "<strong>5. Loop de correção.</strong> Ciclo curto. Escalar só o que a first-wave aguentou. O Max retoma o método depois do coffee.",
                ]
            ),
        )
        + block(
            "tese",
            h3("O que o Cadu consulta para não mentir no mix")
            + p(
                "Produtos digitais do CentralX entram como prova de dado: "
                "modelagem de criativos, operação de PI, Places, inteligência "
                "de marca. Se o dado não está no catálogo, o campo fica "
                "<em>pendente</em> — o mesmo critério desta imersão.",
                "Não usar esta sessão para listar roadmap. Fechar com a "
                "restrição que a banca vai cobrar: unidade de valor, família, "
                "first-wave.",
            ),
        )
        + sources(
            "Skill Cadu / catálogo CentralX — estrutura de planejamento da imersão",
        )
    )
