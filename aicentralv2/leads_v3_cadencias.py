"""Leads v3: cadências de conexão por pessoa (tarefas assistidas).

Cada pessoa de uma conta entra numa cadência (modelo escolhido pelo papel). Os passos
vencidos aparecem na Fila do dia; o executivo envia com um clique e marca como feito.
Ao marcar, o passo vira atividade no histórico do lead e a cadência agenda o próximo,
mantendo o espaçamento do modelo a partir de hoje. Resposta da pessoa encerra a cadência.
Nada é enviado sozinho.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .leads_v3_prospeccao import ProspeccaoError, trimestre_atual

# Tipo da atividade no histórico (CHECK de cadu_lead_atividades) para cada canal do passo.
TIPO_ATIVIDADE = {"email": "email_enviado", "whatsapp": "whatsapp", "telefone": "ligacao", "linkedin": "follow_up"}
ACOES = ("feito", "pular", "respondeu", "pausar", "retomar", "cancelar")

# Fluxos editáveis por todos os executivos. O estágio diz para quem o fluxo serve; a etapa de cada
# passo (topo, meio, fundo) orienta a IA a escrever conteúdo daquela etapa para a pessoa.
ESTAGIOS = {
    "novo": "Pessoa nova, ainda sem conversa",
    "em_conversa": "Já conversou com a gente",
    "reativacao": "Conta parada, para reativar",
    "inbound": "Veio do site ou pediu contato",
}
ETAPAS_PASSO = ("topo", "meio", "fundo")
CANAIS_PASSO = {"email": "enviar", "whatsapp": "enviar", "linkedin": "enviar", "telefone": "ligar"}
PAPEIS_FLUXO = ("marketing", "midia", "criacao", "diretoria", "compras", "comercial", "outro")
MAX_PASSOS = 12


def etapa_do_passo(passo, indice, total):
    """Etapa declarada no passo; fluxo antigo sem etapa usa a regra de antes (primeira metade topo)."""
    etapa = str((passo or {}).get("etapa") or "").strip().lower()
    if etapa in ETAPAS_PASSO:
        return etapa
    return "topo" if indice < -(-max(total, 1) // 2) else "meio"


def _texto(valor, limite):
    return " ".join(str(valor or "").split())[:limite]


def normalizar_fluxo(dados):
    """Valida o fluxo vindo da tela. Devolve os campos prontos para gravar ou levanta ProspeccaoError."""
    dados = dados or {}
    nome = _texto(dados.get("nome"), 80)
    if not nome:
        raise ProspeccaoError("Dê um nome ao fluxo.")
    estagio = str(dados.get("estagio") or "novo")
    if estagio not in ESTAGIOS:
        raise ProspeccaoError("Estágio inválido.")
    papeis = [p for p in dict.fromkeys(dados.get("papeis") or []) if p in PAPEIS_FLUXO]
    brutos = dados.get("passos") or []
    if not isinstance(brutos, list) or not brutos:
        raise ProspeccaoError("O fluxo precisa de pelo menos um passo.")
    if len(brutos) > MAX_PASSOS:
        raise ProspeccaoError(f"No máximo {MAX_PASSOS} passos por fluxo.")
    passos, dia_anterior = [], 0
    for numero, bruto in enumerate(brutos, 1):
        bruto = bruto if isinstance(bruto, dict) else {}
        canal = str(bruto.get("canal") or "")
        if canal not in CANAIS_PASSO:
            raise ProspeccaoError(f"Passo {numero}: escolha o canal.")
        etapa = str(bruto.get("etapa") or "")
        if etapa not in ETAPAS_PASSO:
            raise ProspeccaoError(f"Passo {numero}: escolha a etapa do funil.")
        try:
            dia = int(bruto.get("dia") or 0)
        except (TypeError, ValueError):
            raise ProspeccaoError(f"Passo {numero}: o dia precisa ser um número.") from None
        if dia < dia_anterior or dia > 120:
            raise ProspeccaoError(f"Passo {numero}: o dia vem depois do passo anterior e vai até 120.")
        titulo = _texto(bruto.get("titulo"), 80)
        if not titulo:
            raise ProspeccaoError(f"Passo {numero}: dê um título.")
        acao = "conectar" if canal == "linkedin" and bruto.get("acao") == "conectar" else CANAIS_PASSO[canal]
        passos.append({"dia": dia, "canal": canal, "acao": acao, "etapa": etapa, "titulo": titulo,
                       "objetivo": _texto(bruto.get("objetivo"), 300)})
        dia_anterior = dia
    return {"nome": nome, "descricao": _texto(dados.get("descricao"), 300) or None, "estagio": estagio,
            "papeis": papeis, "passos": passos}


def listar_modelos(cursor):
    cursor.execute(
        """
        SELECT cad.id, cad.chave, cad.nome, cad.descricao, cad.papeis, cad.estagio, cad.passos,
               jsonb_array_length(cad.passos) AS total, cad.criado_por, cad.updated_at,
               (SELECT COUNT(*) FROM cadu_lead_cadencia_inscricoes i
                 WHERE i.id_cadencia = cad.id AND i.status IN ('ativa', 'pausada')) AS em_andamento
          FROM cadu_lead_cadencias cad WHERE cad.ativo ORDER BY cad.estagio = 'novo' DESC, cad.chave IS NULL, cad.nome
        """
    )
    modelos = cursor.fetchall()
    for modelo in modelos:
        passos = modelo["passos"] or []
        modelo["passos"] = [{**p, "etapa": etapa_do_passo(p, i, len(passos))} for i, p in enumerate(passos)]
    return modelos


def criar_fluxo(cursor, dados, *, usuario_id):
    f = normalizar_fluxo(dados)
    cursor.execute(
        """
        INSERT INTO cadu_lead_cadencias (nome, descricao, estagio, papeis, passos, criado_por)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """,
        [f["nome"], f["descricao"], f["estagio"], f["papeis"], _json(f["passos"]), usuario_id],
    )
    return cursor.fetchone()["id"]


def atualizar_fluxo(cursor, fluxo_id, dados, *, usuario_id):
    """Grava a edição. Se os passos mudaram e há gente no meio do fluxo, cria uma versão nova:
    quem já estava termina na versão antiga (que sai da lista) e as próximas inscrições usam a nova."""
    f = normalizar_fluxo(dados)
    cursor.execute(
        """
        SELECT id, chave, passos,
               EXISTS (SELECT 1 FROM cadu_lead_cadencia_inscricoes i
                        WHERE i.id_cadencia = cad.id AND i.status IN ('ativa', 'pausada')) AS em_uso
          FROM cadu_lead_cadencias cad WHERE id = %s AND ativo FOR UPDATE
        """,
        [fluxo_id],
    )
    atual = cursor.fetchone()
    if not atual:
        raise ProspeccaoError("Fluxo não encontrado.")
    if atual["em_uso"] and (atual["passos"] or []) != f["passos"]:
        # A chave do sistema (usada para escolher por papel) passa para a versão nova.
        cursor.execute("UPDATE cadu_lead_cadencias SET ativo = FALSE, chave = NULL WHERE id = %s", [fluxo_id])
        cursor.execute(
            """
            INSERT INTO cadu_lead_cadencias (chave, nome, descricao, estagio, papeis, passos, criado_por, id_versao_anterior)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            [atual["chave"], f["nome"], f["descricao"], f["estagio"], f["papeis"], _json(f["passos"]), usuario_id, fluxo_id],
        )
        return {"id": cursor.fetchone()["id"], "nova_versao": True}
    cursor.execute(
        """
        UPDATE cadu_lead_cadencias
           SET nome = %s, descricao = %s, estagio = %s, papeis = %s, passos = %s, updated_at = NOW()
         WHERE id = %s
        """,
        [f["nome"], f["descricao"], f["estagio"], f["papeis"], _json(f["passos"]), fluxo_id],
    )
    return {"id": fluxo_id, "nova_versao": False}


def arquivar_fluxo(cursor, fluxo_id):
    """Tira o fluxo da lista. Quem está nele segue até o fim; o histórico fica."""
    cursor.execute("SELECT COUNT(*) AS n FROM cadu_lead_cadencias WHERE ativo", [])
    if (cursor.fetchone() or {}).get("n", 0) <= 1:
        raise ProspeccaoError("Mantenha pelo menos um fluxo ativo.")
    cursor.execute("UPDATE cadu_lead_cadencias SET ativo = FALSE, chave = NULL, updated_at = NOW() WHERE id = %s AND ativo RETURNING id", [fluxo_id])
    if not cursor.fetchone():
        raise ProspeccaoError("Fluxo não encontrado.")


def contexto_do_passo(cursor, inscricao_id):
    """Fluxo, posição e etapa do passo atual de uma inscrição, para a IA escrever no tom da etapa."""
    cursor.execute(
        """
        SELECT i.passo_atual, i.id_contato, cad.nome, cad.estagio, cad.descricao, cad.passos
          FROM cadu_lead_cadencia_inscricoes i JOIN cadu_lead_cadencias cad ON cad.id = i.id_cadencia
         WHERE i.id = %s
        """,
        [inscricao_id],
    )
    row = cursor.fetchone()
    if not row:
        return None
    passos = row["passos"] or []
    indice = row["passo_atual"]
    passo = passos[indice] if 0 <= indice < len(passos) else {}
    return {
        "id_contato": row["id_contato"],
        "fluxo": row["nome"],
        "estagio": ESTAGIOS.get(row["estagio"], ""),
        "descricao": row["descricao"] or "",
        "posicao": f"passo {indice + 1} de {len(passos)}",
        "etapa": etapa_do_passo(passo, indice, len(passos)),
        "objetivo": passo.get("objetivo") or "",
        "canal": passo.get("canal") or "",
        "anteriores": [p.get("titulo") for p in passos[:indice] if p.get("titulo")],
        "seguintes": [p.get("titulo") for p in passos[indice + 1:indice + 3] if p.get("titulo")],
    }


def escolher_modelo(cursor, papel):
    """Sugestão quando o executivo não escolhe: fluxo de pessoa nova cujo `papeis` contém o papel; senão o de
    marketing e mídia; senão qualquer fluxo de pessoa nova (fluxos de outros estágios só por escolha)."""
    cursor.execute(
        """
        SELECT id FROM cadu_lead_cadencias
         WHERE ativo
         ORDER BY (estagio = 'novo') DESC, (%(papel)s = ANY(papeis)) DESC, (chave = 'marketing_midia') DESC, chave IS NULL, id
         LIMIT 1
        """,
        {"papel": papel or "outro"},
    )
    row = cursor.fetchone()
    if not row:
        raise ProspeccaoError("Nenhum modelo de cadência ativo. Rode a migração do Leads v3.")
    return row["id"]


def inscrever(cursor, contato_id, *, usuario_id, usuario_nome=None, id_cadencia=None):
    cursor.execute(
        """
        SELECT c.id, c.nome, c.papel, c.id_lead, l.id_executivo
          FROM cadu_lead_contatos c JOIN cadu_leads l ON l.id = c.id_lead
         WHERE c.id = %s
        """,
        [contato_id],
    )
    contato = cursor.fetchone()
    if not contato:
        raise ProspeccaoError("Contato não encontrado.")
    modelo = id_cadencia or escolher_modelo(cursor, contato["papel"])
    cursor.execute(
        """
        INSERT INTO cadu_lead_cadencia_inscricoes (id_cadencia, id_lead, id_contato, id_executivo, proxima_em, inscrito_por)
        SELECT %s, %s, %s, %s, NOW(), %s
         WHERE EXISTS (SELECT 1 FROM cadu_lead_cadencias WHERE id = %s AND ativo)
        ON CONFLICT (id_cadencia, id_contato) WHERE status IN ('ativa', 'pausada') DO NOTHING
        RETURNING id
        """,
        [modelo, contato["id_lead"], contato_id, contato["id_executivo"] or usuario_id, usuario_id, modelo],
    )
    row = cursor.fetchone()
    if not row:
        return None  # já está nesta cadência (ativa ou pausada) ou o modelo foi desativado
    cursor.execute("SELECT nome FROM cadu_lead_cadencias WHERE id = %s", [modelo])
    nome_modelo = (cursor.fetchone() or {}).get("nome", "cadência")
    _atividade(cursor, contato["id_lead"], "follow_up", f"Cadência {nome_modelo} iniciada para {contato['nome']}.",
               contato_id, usuario_id, usuario_nome)
    return row["id"]


def _atividade(cursor, lead_id, tipo, descricao, contato_id, usuario_id, usuario_nome):
    cursor.execute(
        """
        INSERT INTO cadu_lead_atividades (id_lead, tipo, descricao, id_contato, id_usuario, usuario_nome)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [lead_id, tipo, descricao, contato_id, usuario_id, usuario_nome],
    )


def avancar(cursor, inscricao_id, acao, *, usuario_id, usuario_nome=None, nota=None, agora=None, id_gancho=None):
    """Aplica uma ação ao passo atual. Devolve o estado novo da inscrição.

    `id_gancho` (passo feito) fica no evento: é assim que se sabe que fato já foi usado com a pessoa.
    """
    if acao not in ACOES:
        raise ProspeccaoError("Ação inválida.")
    agora = agora or datetime.now()
    cursor.execute(
        """
        SELECT i.*, cad.nome AS cadencia, cad.passos, c.nome AS contato_nome
          FROM cadu_lead_cadencia_inscricoes i
          JOIN cadu_lead_cadencias cad ON cad.id = i.id_cadencia
          JOIN cadu_lead_contatos c ON c.id = i.id_contato
         WHERE i.id = %s
           FOR UPDATE OF i
        """,
        [inscricao_id],
    )
    insc = cursor.fetchone()
    if not insc:
        raise ProspeccaoError("Cadência não encontrada.")
    passos = insc["passos"] or []
    atual = passos[insc["passo_atual"]] if 0 <= insc["passo_atual"] < len(passos) else None
    nota = (str(nota or "").strip() or None)

    if acao in ("feito", "pular"):
        if insc["status"] != "ativa" or not atual:
            raise ProspeccaoError("Esta cadência não tem passo pendente.")
        if acao == "feito":
            cursor.execute(
                """
                INSERT INTO cadu_lead_mensagem_eventos (id_lead, id_contato, id_inscricao, canal, direcao, evento, payload)
                VALUES (%s, %s, %s, %s, 'saida', 'tarefa_feita', %s)
                """,
                [insc["id_lead"], insc["id_contato"], inscricao_id, atual["canal"],
                 _json({"passo": insc["passo_atual"], "titulo": atual.get("titulo"), "nota": nota,
                        **({"id_gancho": id_gancho} if id_gancho else {})})],
            )
        descricao = (f"{atual.get('titulo')} — {insc['contato_nome']} (cadência {insc['cadencia']}, passo "
                     f"{insc['passo_atual'] + 1}/{len(passos)}){' · pulado' if acao == 'pular' else ''}"
                     f"{f': {nota}' if nota else ''}")
        tipo = TIPO_ATIVIDADE.get(atual["canal"], "follow_up") if acao == "feito" else "nota"
        _atividade(cursor, insc["id_lead"], tipo, descricao, insc["id_contato"], usuario_id, usuario_nome)
        proximo = insc["passo_atual"] + 1
        if proximo >= len(passos):
            cursor.execute(
                "UPDATE cadu_lead_cadencia_inscricoes SET passo_atual = %s, status = 'concluida', proxima_em = NULL WHERE id = %s",
                [proximo, inscricao_id],
            )
            return {"status": "concluida", "passo_atual": proximo, "proxima_em": None}
        # Mantém o espaçamento do modelo a partir de hoje (passo feito com atraso não amontoa os próximos).
        intervalo = max(0, int(passos[proximo].get("dia", 0)) - int(atual.get("dia", 0)))
        proxima = agora + timedelta(days=intervalo)
        cursor.execute(
            "UPDATE cadu_lead_cadencia_inscricoes SET passo_atual = %s, proxima_em = %s WHERE id = %s",
            [proximo, proxima, inscricao_id],
        )
        return {"status": "ativa", "passo_atual": proximo, "proxima_em": proxima}

    if acao == "respondeu":
        if insc["status"] not in ("ativa", "pausada"):
            raise ProspeccaoError("Esta cadência já foi encerrada.")
        cursor.execute(
            """
            INSERT INTO cadu_lead_mensagem_eventos (id_lead, id_contato, id_inscricao, canal, direcao, evento, payload)
            VALUES (%s, %s, %s, %s, 'entrada', 'respondeu', %s)
            """,
            [insc["id_lead"], insc["id_contato"], inscricao_id, (atual or {}).get("canal", "email"), _json({"nota": nota})],
        )
        cursor.execute(
            "UPDATE cadu_lead_cadencia_inscricoes SET status = 'respondeu', proxima_em = NULL, motivo_parada = %s WHERE id = %s",
            [nota or "Respondeu", inscricao_id],
        )
        _atividade(cursor, insc["id_lead"], "nota", f"{insc['contato_nome']} respondeu à cadência {insc['cadencia']}"
                   f"{f': {nota}' if nota else ''}.", insc["id_contato"], usuario_id, usuario_nome)
        # Resposta tira o lead do Inbox e põe a conta do Golden Circle em contato.
        cursor.execute("UPDATE cadu_leads SET status = 'tentativa_contato' WHERE id = %s AND status = 'inbox'", [insc["id_lead"]])
        cursor.execute(
            "UPDATE cadu_golden_circle SET status = 'em_contato' WHERE id_lead = %s AND trimestre = %s AND status = 'planejada'",
            [insc["id_lead"], trimestre_atual(agora.date())],
        )
        return {"status": "respondeu", "passo_atual": insc["passo_atual"], "proxima_em": None}

    novo = {"pausar": ("pausada", "ativa"), "retomar": ("ativa", "pausada"), "cancelar": ("cancelada", None)}[acao]
    status_novo, exige = novo
    if exige and insc["status"] != exige:
        raise ProspeccaoError("A cadência não está no estado certo para esta ação.")
    if acao == "cancelar" and insc["status"] not in ("ativa", "pausada"):
        raise ProspeccaoError("Esta cadência já foi encerrada.")
    cursor.execute(
        """
        UPDATE cadu_lead_cadencia_inscricoes
           SET status = %s, proxima_em = CASE WHEN %s = 'ativa' THEN %s ELSE NULL END, motivo_parada = %s
         WHERE id = %s
        """,
        [status_novo, status_novo, agora, nota if acao != "retomar" else None, inscricao_id],
    )
    return {"status": status_novo, "passo_atual": insc["passo_atual"], "proxima_em": agora if status_novo == "ativa" else None}


def _json(valor):
    from psycopg.types.json import Json

    return Json(valor)


def fila_do_dia(cursor, *, executivo=None, ate=None):
    """Passos vencidos até `ate` (fim de hoje), Golden Circle primeiro, mais antigos antes."""
    ate = ate or datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    filtro = "AND COALESCE(i.id_executivo, l.id_executivo) = %(executivo)s" if executivo else ""
    cursor.execute(
        f"""
        SELECT i.id, i.id_lead, i.id_contato, i.passo_atual, i.proxima_em, i.created_at,
               {_COLUNAS_PASSO}
         WHERE i.status = 'ativa' AND i.proxima_em <= %(ate)s {filtro}
         ORDER BY golden DESC, i.proxima_em, i.id
         LIMIT 300
        """,
        {"ate": ate, "executivo": executivo, "trimestre": trimestre_atual(ate.date())},
    )
    return cursor.fetchall()


def inscricoes_do_lead(cursor, lead_id):
    cursor.execute(
        """
        SELECT i.id, i.id_contato, i.status, i.passo_atual, i.proxima_em, i.motivo_parada, i.created_at,
               cad.id AS id_cadencia, cad.nome AS cadencia, cad.passos -> i.passo_atual AS passo,
               jsonb_array_length(cad.passos) AS total
          FROM cadu_lead_cadencia_inscricoes i JOIN cadu_lead_cadencias cad ON cad.id = i.id_cadencia
         WHERE i.id_lead = %s
         ORDER BY (i.status IN ('ativa', 'pausada')) DESC, i.created_at DESC
        """,
        [lead_id],
    )
    return cursor.fetchall()


# Colunas e junções comuns da Fila do dia e dos Próximos (a trilha usa `passos` inteiro).
_COLUNAS_PASSO = """
               cad.nome AS cadencia, cad.passos -> i.passo_atual AS passo, cad.passos AS passos,
               jsonb_array_length(cad.passos) AS total,
               c.nome AS contato_nome, c.cargo, c.email, c.telefone, c.linkedin_url, c.papel,
               l.empresa, l.nome AS lead_nome,
               EXISTS (SELECT 1 FROM cadu_golden_circle g WHERE g.id_lead = i.id_lead AND g.trimestre = %(trimestre)s) AS golden
          FROM cadu_lead_cadencia_inscricoes i
          JOIN cadu_lead_cadencias cad ON cad.id = i.id_cadencia
          JOIN cadu_lead_contatos c ON c.id = i.id_contato
          JOIN cadu_leads l ON l.id = i.id_lead"""


def proximos_passos(cursor, *, executivo=None, dias=14, agora=None):
    """Passos agendados depois de hoje, até `dias` à frente (para ver e preparar com antecedência)."""
    agora = agora or datetime.now()
    fim_de_hoje = agora.replace(hour=23, minute=59, second=59, microsecond=0)
    filtro = "AND COALESCE(i.id_executivo, l.id_executivo) = %(executivo)s" if executivo else ""
    cursor.execute(
        f"""
        SELECT i.id, i.id_lead, i.id_contato, i.passo_atual, i.proxima_em, i.created_at,
               {_COLUNAS_PASSO}
         WHERE i.status = 'ativa' AND i.proxima_em > %(de)s AND i.proxima_em <= %(ate)s {filtro}
         ORDER BY i.proxima_em, golden DESC, i.id
         LIMIT 300
        """,
        {"de": fim_de_hoje, "ate": fim_de_hoje + timedelta(days=dias), "executivo": executivo,
         "trimestre": trimestre_atual(agora.date())},
    )
    return cursor.fetchall()


def feitos_hoje(cursor, *, executivo=None, agora=None):
    """O que já foi executado hoje (passos feitos e respostas), com o próximo toque de cada pessoa."""
    agora = agora or datetime.now()
    filtro = "AND COALESCE(i.id_executivo, l.id_executivo) = %(executivo)s" if executivo else ""
    cursor.execute(
        f"""
        SELECT e.id, e.id_lead, e.id_contato, e.id_inscricao, e.canal, e.evento, e.ocorreu_em,
               e.payload ->> 'titulo' AS titulo, c.nome AS contato_nome, COALESCE(l.empresa, l.nome) AS empresa,
               i.status AS status_cadencia, i.proxima_em, cad.nome AS cadencia,
               cad.passos -> i.passo_atual AS proximo_passo,
               EXISTS (SELECT 1 FROM cadu_golden_circle g WHERE g.id_lead = e.id_lead AND g.trimestre = %(trimestre)s) AS golden
          FROM cadu_lead_mensagem_eventos e
          JOIN cadu_leads l ON l.id = e.id_lead
          LEFT JOIN cadu_lead_contatos c ON c.id = e.id_contato
          LEFT JOIN cadu_lead_cadencia_inscricoes i ON i.id = e.id_inscricao
          LEFT JOIN cadu_lead_cadencias cad ON cad.id = i.id_cadencia
         WHERE e.evento IN ('tarefa_feita', 'respondeu') AND e.ocorreu_em >= %(inicio)s {filtro}
         ORDER BY e.ocorreu_em DESC
         LIMIT 200
        """,
        {"inicio": agora.replace(hour=0, minute=0, second=0, microsecond=0), "executivo": executivo,
         "trimestre": trimestre_atual(agora.date())},
    )
    return cursor.fetchall()
