import os
import requests as http_requests
from flask import request, jsonify, session, current_app
from ..auth import login_required
from ..db import get_db
from . import bp

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"


def _call_openrouter(system_prompt, user_content, max_tokens=1000, temperature=0.7):
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY não configurada")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralComm AI - Sales War Room"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    resp = http_requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content']


# --------------- Melhorar Texto ---------------

@bp.route('/api/ia/melhorar-texto', methods=['POST'])
@login_required
def ia_melhorar_texto():
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip()
    if not texto:
        return jsonify({'success': False, 'error': 'Texto obrigatório'}), 400

    system_prompt = (
        "Você é um assistente comercial. Receba o texto do executivo de vendas "
        "sobre uma interação com cliente e:\n"
        "1. Corrija erros de português\n"
        "2. Amplie brevemente mantendo o sentido original\n"
        "3. Mantenha tom profissional e objetivo\n"
        "4. Não invente informações que não estão no texto original\n"
        "Retorne apenas o texto melhorado, sem explicações."
    )

    try:
        resultado = _call_openrouter(system_prompt, texto)
        return jsonify({'success': True, 'texto_melhorado': resultado})
    except Exception as e:
        current_app.logger.error(f"Erro ia_melhorar_texto: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Sugerir Objetivos ---------------

@bp.route('/api/ia/sugerir-objetivos', methods=['POST'])
@login_required
def ia_sugerir_objetivos():
    data = request.get_json() or {}
    cliente_id = data.get('cliente_id')
    if not cliente_id:
        return jsonify({'success': False, 'error': 'cliente_id obrigatório'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cli.nome_fantasia, cli.categoria_abc,
                       tc.display AS tipo_cliente
                FROM tbl_cliente cli
                LEFT JOIN tbl_tipo_cliente tc ON tc.id_tipo_cliente = cli.id_tipo_cliente
                WHERE cli.id_cliente = %s
            """, (cliente_id,))
            cliente = cur.fetchone()

            if not cliente:
                return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404

            cur.execute("""
                SELECT c.nome_completo, cg.descricao AS cargo
                FROM tbl_contato_cliente c
                LEFT JOIN tbl_cargo_contato cg ON cg.id_cargo_contato = c.pk_id_tbl_cargo
                WHERE c.pk_id_tbl_cliente = %s AND c.status = true
                ORDER BY c.nome_completo LIMIT 10
            """, (cliente_id,))
            contatos = cur.fetchall()

            cur.execute("""
                SELECT texto, data_registro
                FROM sales_historico_cliente
                WHERE cliente_id = %s
                ORDER BY data_registro DESC LIMIT 5
            """, (cliente_id,))
            historico = cur.fetchall()

            cur.execute("""
                SELECT COUNT(*) AS total,
                       COUNT(*) FILTER (WHERE status = 2) AS aprovadas
                FROM cadu_cotacoes
                WHERE cliente_id = %s AND deleted_at IS NULL
                  AND created_at >= CURRENT_DATE - INTERVAL '90 days'
            """, (cliente_id,))
            cot = cur.fetchone()

            cur.execute("""
                SELECT descricao, status
                FROM sales_atividades
                WHERE cliente_id = %s AND status != 'concluida'
                ORDER BY data_atividade DESC LIMIT 5
            """, (cliente_id,))
            atividades = cur.fetchall()

        contatos_str = ", ".join(
            f"{c['nome_completo']} ({c['cargo'] or 'sem cargo'})" for c in contatos
        ) if contatos else "Nenhum contato cadastrado"

        historico_str = "\n".join(
            f"- {h['data_registro']}: {h['texto']}" for h in historico
        ) if historico else "Sem histórico recente"

        atividades_str = "\n".join(
            f"- [{a['status']}] {a['descricao']}" for a in atividades
        ) if atividades else "Sem atividades pendentes"

        contexto = (
            f"Cliente: {cliente['nome_fantasia']}\n"
            f"Categoria: {cliente['categoria_abc'] or 'Sem categoria'}\n"
            f"Tipo: {cliente['tipo_cliente'] or 'Não definido'}\n"
            f"Contatos: {contatos_str}\n"
            f"Cotações últimos 90 dias: {cot['total']} (aprovadas: {cot['aprovadas']})\n"
            f"Histórico recente:\n{historico_str}\n"
            f"Atividades pendentes:\n{atividades_str}"
        )

        system_prompt = (
            "Você é um consultor comercial da CENTRALCOMM, empresa de operação de mídia digital "
            "(programática, interativos, streaming, CTV, áudio, portais, redes sociais e performance).\n\n"
            "Produtos disponíveis: mídia programática, formatos interativos, Serasa Ads (dados e mídia), "
            "Cadu (plataforma SaaS de planejamento de mídia), CTV, áudio digital, mídia em grandes portais.\n\n"
            "Com base no contexto do cliente abaixo, sugira 3-5 objetivos comerciais práticos para o próximo mês. "
            "Foque em:\n"
            "- Apresentar produtos que o cliente ainda não usa\n"
            "- Retomar contatos inativos\n"
            "- Criar touchpoints para manter relevância\n"
            "- Ampliar volume de cotações\n\n"
            "Retorne apenas a lista de objetivos, um por linha, sem numeração."
        )

        resultado = _call_openrouter(system_prompt, contexto)
        objetivos = [o.strip() for o in resultado.strip().split('\n') if o.strip()]

        return jsonify({'success': True, 'objetivos': objetivos})
    except Exception as e:
        current_app.logger.error(f"Erro ia_sugerir_objetivos: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Gerar Comunicação ---------------

@bp.route('/api/ia/gerar-comunicacao', methods=['POST'])
@login_required
def ia_gerar_comunicacao():
    data = request.get_json() or {}
    contato_id = data.get('contato_id')
    cliente_id = data.get('cliente_id')
    tipo = data.get('tipo', 'email')
    tamanho = data.get('tamanho', 'medio')
    objetivo = (data.get('objetivo') or '').strip()
    produto = data.get('produto', '')
    canal = data.get('canal', '')

    if not contato_id or not cliente_id or not objetivo:
        return jsonify({'success': False, 'error': 'contato_id, cliente_id e objetivo são obrigatórios'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.nome_completo, cg.descricao AS cargo
                FROM tbl_contato_cliente c
                LEFT JOIN tbl_cargo_contato cg ON cg.id_cargo_contato = c.pk_id_tbl_cargo
                WHERE c.id_contato_cliente = %s
            """, (contato_id,))
            contato = cur.fetchone()

            cur.execute("SELECT nome_fantasia FROM tbl_cliente WHERE id_cliente = %s", (cliente_id,))
            cliente = cur.fetchone()

        if not contato or not cliente:
            return jsonify({'success': False, 'error': 'Contato ou cliente não encontrado'}), 404

        user_name = session.get('user_name', 'Equipe Comercial')

        system_prompt = (
            "Você é um redator comercial da CENTRALCOMM, empresa de operação de mídia digital.\n\n"
            f"Gere uma mensagem {tipo} de tamanho {tamanho} para o contato "
            f"{contato['nome_completo']} ({contato['cargo'] or 'sem cargo definido'}) "
            f"do cliente {cliente['nome_fantasia']}.\n\n"
            f"Objetivo: {objetivo}\n"
            f"Produto: {produto or 'não especificado'}\n"
            f"{'Canal/audiência: ' + canal if canal else ''}\n\n"
            "Se for WhatsApp: tom direto, pessoal, sem formalidades excessivas. "
            "Máximo 3 parágrafos curtos.\n"
            "Se for Email: inclua assunto, saudação, corpo e despedida. "
            "Tom profissional mas acessível.\n\n"
            "Não use emojis excessivos. Seja natural.\n"
            f"Assine como: {user_name}"
        )

        resultado = _call_openrouter(system_prompt, objetivo, max_tokens=1500)

        return jsonify({'success': True, 'mensagem': resultado, 'tipo': tipo})
    except Exception as e:
        current_app.logger.error(f"Erro ia_gerar_comunicacao: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
