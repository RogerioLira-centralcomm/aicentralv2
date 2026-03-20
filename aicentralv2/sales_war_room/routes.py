from flask import render_template, request, jsonify, session, current_app
from ..auth import login_required
from ..db import get_db
from . import bp


@bp.route('/')
@login_required
def index():
    from .. import db
    executivos = db.obter_vendedores_centralcomm()
    return render_template('sales_war_room/sales_war_room.html', executivos=executivos)


# --------------- Column 1: Clientes ---------------

@bp.route('/api/clientes')
@login_required
def api_clientes():
    executivo_id = request.args.get('executivo_id', type=int)
    tipo = request.args.get('tipo', '')  # governo | privado
    busca = request.args.get('busca', '').strip()

    if not executivo_id:
        return jsonify({'success': False, 'error': 'executivo_id obrigatório'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT
                    cli.id_cliente,
                    cli.nome_fantasia,
                    cli.razao_social,
                    cli.categoria_abc,
                    cli.pk_id_tbl_agencia,
                    ag.key AS is_agencia,
                    COUNT(DISTINCT cont.id_contato_cliente) AS qtd_contatos,
                    COUNT(DISTINCT sa.id) FILTER (WHERE sa.status = 'pendente') AS atividades_pendentes
                FROM tbl_cliente cli
                LEFT JOIN tbl_agencia ag ON ag.id_agencia = cli.pk_id_tbl_agencia
                LEFT JOIN tbl_contato_cliente cont ON cont.pk_id_tbl_cliente = cli.id_cliente AND cont.status = true
                LEFT JOIN sales_atividades sa ON sa.cliente_id = cli.id_cliente
                LEFT JOIN tbl_tipo_cliente tc ON tc.id_tipo_cliente = cli.id_tipo_cliente
                WHERE cli.vendas_central_comm = %s
                  AND COALESCE(cli.status, true) = true
            """
            params = [executivo_id]

            if tipo == 'governo':
                query += " AND LOWER(tc.display) = 'público'"
            elif tipo == 'privado':
                query += " AND (tc.display IS NULL OR LOWER(tc.display) != 'público')"

            if busca:
                query += " AND (cli.nome_fantasia ILIKE %s OR cli.razao_social ILIKE %s)"
                params.extend([f'%{busca}%', f'%{busca}%'])

            query += """
                GROUP BY cli.id_cliente, cli.nome_fantasia, cli.razao_social,
                         cli.categoria_abc, cli.pk_id_tbl_agencia, ag.key
                ORDER BY
                    CASE cli.categoria_abc WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
                    cli.nome_fantasia
            """

            cur.execute(query, params)
            clientes = cur.fetchall()

        return jsonify({'success': True, 'clientes': clientes})
    except Exception as e:
        current_app.logger.error(f"Erro api_clientes: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 2: Status ---------------

@bp.route('/api/cliente/<int:cliente_id>/status')
@login_required
def api_cliente_status(cliente_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    cli.id_cliente,
                    cli.nome_fantasia,
                    cli.categoria_abc,
                    vend.nome_completo AS executivo_nome,
                    COALESCE(cot.total_cotacoes, 0) AS total_cotacoes,
                    COALESCE(cot.cotacoes_aprovadas, 0) AS cotacoes_aprovadas,
                    COALESCE(cot.valor_bruto, 0) AS valor_bruto,
                    COALESCE(cot.valor_liquido, 0) AS valor_liquido,
                    COALESCE(pi_data.total_pis, 0) AS total_pis,
                    COALESCE(pi_data.pis_concluidos, 0) AS pis_concluidos
                FROM tbl_cliente cli
                LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) AS total_cotacoes,
                        COUNT(*) FILTER (WHERE c.status = '2') AS cotacoes_aprovadas,
                        COALESCE(SUM(c.valor_total_proposta), 0) AS valor_bruto,
                        COALESCE(SUM(c.valor_total_proposta) FILTER (WHERE c.status = '2'), 0) AS valor_liquido
                    FROM cadu_cotacoes c
                    WHERE c.cliente_id = cli.id_cliente
                      AND c.deleted_at IS NULL
                      AND DATE_TRUNC('month', c.created_at) = DATE_TRUNC('month', CURRENT_DATE)
                ) cot ON true
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) AS total_pis,
                        COUNT(*) FILTER (WHERE p.id_status_pi = 4) AS pis_concluidos
                    FROM cadu_pi p
                    WHERE p.id_cliente = cli.id_cliente
                      AND DATE_TRUNC('month', p.created_at) = DATE_TRUNC('month', CURRENT_DATE)
                ) pi_data ON true
                WHERE cli.id_cliente = %s
            """, (cliente_id,))
            status = cur.fetchone()

        if not status:
            return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404

        for key in ('valor_bruto', 'valor_liquido'):
            status[key] = float(status[key]) if status[key] else 0

        pct = 0
        if status['total_cotacoes'] > 0:
            pct = round(status['cotacoes_aprovadas'] / status['total_cotacoes'] * 100, 1)
        status['pct_aprovadas'] = pct

        return jsonify({'success': True, 'status': status})
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_status: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 2: Status Completo (modal) ---------------

@bp.route('/api/cliente/<int:cliente_id>/status-completo')
@login_required
def api_cliente_status_completo(cliente_id):
    ano = request.args.get('ano', type=int)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if not ano:
                from datetime import date
                ano = date.today().year

            cur.execute("""
                SELECT
                    COUNT(*) AS total_cotacoes,
                    COUNT(*) FILTER (WHERE c.status = '2') AS cotacoes_aprovadas,
                    COALESCE(SUM(c.valor_total_proposta), 0) AS valor_total,
                    COALESCE(SUM(c.valor_total_proposta) FILTER (WHERE c.status = '2'), 0) AS valor_aprovado,
                    CASE WHEN COUNT(*) > 0
                         THEN ROUND(COUNT(*) FILTER (WHERE c.status = '2')::numeric / COUNT(*) * 100, 1)
                         ELSE 0 END AS pct_conversao
                FROM cadu_cotacoes c
                WHERE c.cliente_id = %s
                  AND c.deleted_at IS NULL
                  AND EXTRACT(YEAR FROM c.created_at) = %s
            """, (cliente_id, ano))
            resumo_cotacoes = cur.fetchone()

            cur.execute("""
                SELECT
                    COUNT(*) AS total_pis,
                    COUNT(*) FILTER (WHERE p.id_status_pi = 4) AS pis_concluidos,
                    COALESCE(SUM(p.vr_bruto_pi), 0) AS valor_pis
                FROM cadu_pi p
                WHERE p.id_cliente = %s
                  AND EXTRACT(YEAR FROM p.created_at) = %s
            """, (cliente_id, ano))
            resumo_pis = cur.fetchone()

            ticket_medio = 0
            if resumo_cotacoes['total_cotacoes'] > 0:
                ticket_medio = float(resumo_cotacoes['valor_total']) / resumo_cotacoes['total_cotacoes']

            cur.execute("""
                SELECT
                    EXTRACT(MONTH FROM c.created_at)::int AS mes,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE c.status = '2') AS aprovadas,
                    COALESCE(SUM(c.valor_total_proposta) FILTER (WHERE c.status = '2'), 0) AS faturamento
                FROM cadu_cotacoes c
                WHERE c.cliente_id = %s
                  AND c.deleted_at IS NULL
                  AND EXTRACT(YEAR FROM c.created_at) = %s
                GROUP BY EXTRACT(MONTH FROM c.created_at)
                ORDER BY mes
            """, (cliente_id, ano))
            por_mes = cur.fetchall()

            cur.execute("""
                SELECT
                    c.id, c.numero_cotacao, c.nome_campanha,
                    c.valor_total_proposta, c.status,
                    st.descricao AS status_descricao,
                    c.created_at
                FROM cadu_cotacoes c
                LEFT JOIN cadu_cotacoes_status st ON st.id = c.status
                WHERE c.cliente_id = %s
                  AND c.deleted_at IS NULL
                  AND EXTRACT(YEAR FROM c.created_at) = %s
                ORDER BY c.created_at DESC
            """, (cliente_id, ano))
            cotacoes_lista = cur.fetchall()

        for c in cotacoes_lista:
            if c.get('valor_total_proposta'):
                c['valor_total_proposta'] = float(c['valor_total_proposta'])
            if c.get('created_at'):
                c['created_at'] = c['created_at'].isoformat()

        for m in por_mes:
            m['faturamento'] = float(m['faturamento'])

        for key in ('valor_total', 'valor_aprovado'):
            resumo_cotacoes[key] = float(resumo_cotacoes[key])
        resumo_pis['valor_pis'] = float(resumo_pis['valor_pis'])

        return jsonify({
            'success': True,
            'ano': ano,
            'resumo_cotacoes': resumo_cotacoes,
            'resumo_pis': resumo_pis,
            'ticket_medio': round(ticket_medio, 2),
            'por_mes': por_mes,
            'cotacoes': cotacoes_lista
        })
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_status_completo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 2: Histórico ---------------

@bp.route('/api/cliente/<int:cliente_id>/historico')
@login_required
def api_cliente_historico(cliente_id):
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM sales_historico_cliente
                WHERE cliente_id = %s
            """, (cliente_id,))
            total = cur.fetchone()['total']

            cur.execute("""
                SELECT
                    h.id, h.texto, h.data_registro, h.created_at,
                    c.nome_completo AS autor
                FROM sales_historico_cliente h
                JOIN tbl_contato_cliente c ON c.id_contato_cliente = h.executivo_id
                WHERE h.cliente_id = %s
                ORDER BY h.data_registro DESC, h.created_at DESC
                LIMIT %s OFFSET %s
            """, (cliente_id, per_page, offset))
            registros = cur.fetchall()

        for r in registros:
            if r.get('data_registro'):
                r['data_registro'] = r['data_registro'].isoformat()
            if r.get('created_at'):
                r['created_at'] = r['created_at'].isoformat()

        return jsonify({
            'success': True,
            'registros': registros,
            'total': total,
            'page': page,
            'pages': (total + per_page - 1) // per_page
        })
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_historico: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/cliente/<int:cliente_id>/historico', methods=['POST'])
@login_required
def api_criar_historico(cliente_id):
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip()
    if not texto:
        return jsonify({'success': False, 'error': 'Texto obrigatório'}), 400

    executivo_id = session.get('user_id')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sales_historico_cliente (cliente_id, executivo_id, texto)
                VALUES (%s, %s, %s)
                RETURNING id, data_registro
            """, (cliente_id, executivo_id, texto))
            row = cur.fetchone()
        conn.commit()
        return jsonify({
            'success': True,
            'id': row['id'],
            'data_registro': row['data_registro'].isoformat()
        })
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_criar_historico: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 3: Contatos ---------------

@bp.route('/api/cliente/<int:cliente_id>/contatos')
@login_required
def api_cliente_contatos(cliente_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id_contato_cliente,
                    c.nome_completo,
                    c.email,
                    c.telefone,
                    cg.descricao AS cargo,
                    (
                        SELECT MAX(sa.data_atividade)
                        FROM sales_atividades sa
                        WHERE sa.contato_id = c.id_contato_cliente
                          AND sa.status = 'concluida'
                    ) AS ultima_atividade
                FROM tbl_contato_cliente c
                LEFT JOIN tbl_cargo_contato cg ON cg.id_cargo_contato = c.pk_id_tbl_cargo
                WHERE c.pk_id_tbl_cliente = %s AND c.status = true
                ORDER BY c.nome_completo
            """, (cliente_id,))
            contatos = cur.fetchall()

        for ct in contatos:
            if ct.get('ultima_atividade'):
                ct['ultima_atividade'] = ct['ultima_atividade'].isoformat()

        return jsonify({'success': True, 'contatos': contatos})
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_contatos: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/contato/<int:contato_id>/detalhes')
@login_required
def api_contato_detalhes(contato_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    c.id_contato_cliente,
                    c.nome_completo,
                    c.email,
                    c.telefone,
                    cg.descricao AS cargo,
                    cli.id_cliente AS cliente_id,
                    cli.nome_fantasia AS cliente_nome
                FROM tbl_contato_cliente c
                LEFT JOIN tbl_cargo_contato cg ON cg.id_cargo_contato = c.pk_id_tbl_cargo
                LEFT JOIN tbl_cliente cli ON cli.id_cliente = c.pk_id_tbl_cliente
                WHERE c.id_contato_cliente = %s
            """, (contato_id,))
            contato = cur.fetchone()

            if not contato:
                return jsonify({'success': False, 'error': 'Contato não encontrado'}), 404

            cur.execute("""
                SELECT
                    sa.id, sa.descricao, sa.data_atividade, sa.status, sa.created_at
                FROM sales_atividades sa
                WHERE sa.contato_id = %s
                ORDER BY sa.data_atividade DESC
                LIMIT 20
            """, (contato_id,))
            atividades = cur.fetchall()

        for a in atividades:
            if a.get('data_atividade'):
                a['data_atividade'] = a['data_atividade'].isoformat()
            if a.get('created_at'):
                a['created_at'] = a['created_at'].isoformat()

        return jsonify({'success': True, 'contato': contato, 'atividades': atividades})
    except Exception as e:
        current_app.logger.error(f"Erro api_contato_detalhes: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 4: Atividades ---------------

@bp.route('/api/cliente/<int:cliente_id>/atividades')
@login_required
def api_cliente_atividades(cliente_id):
    contato_id = request.args.get('contato_id', type=int)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            query = """
                SELECT
                    sa.id, sa.descricao, sa.data_atividade, sa.status,
                    sa.contato_id, sa.created_at,
                    c.nome_completo AS contato_nome,
                    ex.nome_completo AS responsavel_nome
                FROM sales_atividades sa
                LEFT JOIN tbl_contato_cliente c ON c.id_contato_cliente = sa.contato_id
                LEFT JOIN tbl_contato_cliente ex ON ex.id_contato_cliente = sa.executivo_id
                WHERE sa.cliente_id = %s
            """
            params = [cliente_id]

            if contato_id:
                query += " AND sa.contato_id = %s"
                params.append(contato_id)

            query += " ORDER BY CASE sa.status WHEN 'pendente' THEN 1 WHEN 'em_andamento' THEN 2 ELSE 3 END, sa.data_atividade DESC"

            cur.execute(query, params)
            atividades = cur.fetchall()

        for a in atividades:
            if a.get('data_atividade'):
                a['data_atividade'] = a['data_atividade'].isoformat()
            if a.get('created_at'):
                a['created_at'] = a['created_at'].isoformat()

        return jsonify({'success': True, 'atividades': atividades})
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_atividades: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/cliente/<int:cliente_id>/atividades', methods=['POST'])
@login_required
def api_criar_atividade(cliente_id):
    data = request.get_json() or {}
    descricao = (data.get('descricao') or '').strip()
    data_atividade = data.get('data_atividade')
    contato_id = data.get('contato_id') or None

    if not descricao or not data_atividade:
        return jsonify({'success': False, 'error': 'Descrição e data são obrigatórios'}), 400

    executivo_id = session.get('user_id')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sales_atividades (cliente_id, contato_id, executivo_id, descricao, data_atividade)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (cliente_id, contato_id, executivo_id, descricao, data_atividade))
            row = cur.fetchone()
        conn.commit()
        return jsonify({'success': True, 'id': row['id']})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_criar_atividade: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/atividades/<int:atividade_id>/status', methods=['PATCH'])
@login_required
def api_atualizar_status_atividade(atividade_id):
    data = request.get_json() or {}
    novo_status = data.get('status')
    if novo_status not in ('pendente', 'em_andamento', 'concluida'):
        return jsonify({'success': False, 'error': 'Status inválido'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sales_atividades
                SET status = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id
            """, (novo_status, atividade_id))
            row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({'success': False, 'error': 'Atividade não encontrada'}), 404
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_atualizar_status_atividade: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 5: Objetivos ---------------

@bp.route('/api/cliente/<int:cliente_id>/objetivos')
@login_required
def api_cliente_objetivos(cliente_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, texto, conquistado, data_conquista, created_at
                FROM sales_objetivos_cliente
                WHERE cliente_id = %s
                ORDER BY conquistado ASC, created_at DESC
            """, (cliente_id,))
            objetivos = cur.fetchall()

        for o in objetivos:
            if o.get('data_conquista'):
                o['data_conquista'] = o['data_conquista'].isoformat()
            if o.get('created_at'):
                o['created_at'] = o['created_at'].isoformat()

        return jsonify({'success': True, 'objetivos': objetivos})
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_objetivos: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/cliente/<int:cliente_id>/objetivos', methods=['POST'])
@login_required
def api_criar_objetivo(cliente_id):
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip()
    if not texto:
        return jsonify({'success': False, 'error': 'Texto obrigatório'}), 400

    executivo_id = session.get('user_id')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO sales_objetivos_cliente (cliente_id, executivo_id, texto)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (cliente_id, executivo_id, texto))
            row = cur.fetchone()
        conn.commit()
        return jsonify({'success': True, 'id': row['id']})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_criar_objetivo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/objetivos/<int:objetivo_id>/conquistar', methods=['PATCH'])
@login_required
def api_conquistar_objetivo(objetivo_id):
    data = request.get_json() or {}
    conquistado = data.get('conquistado', True)

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sales_objetivos_cliente
                SET conquistado = %s,
                    data_conquista = CASE WHEN %s THEN CURRENT_DATE ELSE NULL END,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id
            """, (conquistado, conquistado, objetivo_id))
            row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({'success': False, 'error': 'Objetivo não encontrado'}), 404
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_conquistar_objetivo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
