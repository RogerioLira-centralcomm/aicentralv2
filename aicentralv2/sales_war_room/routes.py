import re
from flask import render_template, request, jsonify, session, current_app
from ..auth import login_required
from ..db import get_db
from . import bp


def _eh_agencia_row(is_agencia_key, agencia_display):
    """
    Cadastro: Agência Sim/Não (tbl_agencia.key boolean e/ou display 'Sim'/'Não').
    Usado na API e nos contadores A/C para não depender só de === true no JSON.
    """
    if is_agencia_key is True:
        return True
    if is_agencia_key is False:
        pass
    elif is_agencia_key is not None:
        s = str(is_agencia_key).strip().lower()
        if s in ('true', 't', '1', 'yes'):
            return True
        if s in ('false', 'f', '0', 'no', 'none'):
            return False
    disp = (agencia_display or '').strip().lower()
    if disp in ('sim', 's'):
        return True
    return False


def _parse_vr_bruto(raw):
    """Parse vr_bruto_pi text (e.g. 'R$ 1.234,56', '10000.50', '10000') to float."""
    if not raw:
        return 0.0
    s = str(raw).strip()
    s = re.sub(r'[^\d.,]', '', s)
    if not s:
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif s.count('.') > 1:
        s = s.replace('.', '')
    try:
        return float(s)
    except ValueError:
        return 0.0


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
    perfil = request.args.get('perfil', '').strip()  # direto | agencia
    busca = request.args.get('busca', '').strip()

    if not executivo_id:
        return jsonify({'success': False, 'error': 'executivo_id obrigatório'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            # Filtro perfil: "é agência" = key TRUE OU display Sim (JOIN nulo = cliente final).
            _sql_eh_ag = (
                "(COALESCE((ag.key IS TRUE), false) OR "
                "LOWER(TRIM(COALESCE(ag.display, ''))) IN ('sim', 's'))"
            )
            query = """
                SELECT
                    cli.id_cliente,
                    cli.nome_fantasia,
                    cli.razao_social,
                    cli.categoria_abc,
                    cli.pk_id_tbl_agencia,
                    ag.key AS is_agencia,
                    ag.display AS agencia_display,
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

            if perfil == 'direto':
                query += f" AND NOT ({_sql_eh_ag})"
            elif perfil == 'agencia':
                query += f" AND ({_sql_eh_ag})"

            if busca:
                query += " AND (cli.nome_fantasia ILIKE %s OR cli.razao_social ILIKE %s)"
                params.extend([f'%{busca}%', f'%{busca}%'])

            query += """
                GROUP BY cli.id_cliente, cli.nome_fantasia, cli.razao_social,
                         cli.categoria_abc, cli.pk_id_tbl_agencia, ag.key, ag.display
                ORDER BY
                    CASE cli.categoria_abc WHEN 'A' THEN 1 WHEN 'B' THEN 2 ELSE 3 END,
                    cli.nome_fantasia
            """

            cur.execute(query, params)
            rows = cur.fetchall()
            clientes = []
            for r in rows:
                d = dict(r)
                d['eh_agencia'] = _eh_agencia_row(d.get('is_agencia'), d.get('agencia_display'))
                clientes.append(d)

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
                    COALESCE(pi_data.pis_concluidos, 0) AS pis_concluidos,
                    COALESCE(pi_data.valor_pis, 0) AS valor_pis
                FROM tbl_cliente cli
                LEFT JOIN tbl_contato_cliente vend ON vend.id_contato_cliente = cli.vendas_central_comm
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) AS total_cotacoes,
                        COUNT(*) FILTER (WHERE c.status IN ('Aprovada', '3')) AS cotacoes_aprovadas,
                        COALESCE(SUM(c.valor_total_proposta), 0) AS valor_bruto,
                        COALESCE(SUM(c.valor_total_proposta) FILTER (WHERE c.status IN ('Aprovada', '3')), 0) AS valor_liquido
                    FROM cadu_cotacoes c
                    WHERE (c.client_id = cli.id_cliente OR c.agencia_id = cli.id_cliente)
                      AND c.deleted_at IS NULL
                      AND DATE_TRUNC('month', c.created_at) = DATE_TRUNC('month', CURRENT_DATE)
                ) cot ON true
                LEFT JOIN LATERAL (
                    SELECT
                        COUNT(*) AS total_pis,
                        COUNT(*) FILTER (WHERE sp.descricao ILIKE '%%fatur%%'
                                           OR sp.descricao ILIKE '%%nf emitida%%'
                                           OR sp.descricao ILIKE '%%conclu%%'
                                           OR sp.descricao ILIKE '%%finaliz%%') AS pis_concluidos,
                        COALESCE(SUM(
                            CASE
                                WHEN p.vr_bruto_pi IS NULL OR TRIM(p.vr_bruto_pi) = '' THEN 0
                                WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '') ~ '^[0-9]+,[0-9]+$'
                                    THEN REPLACE(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), ',', '.')::numeric
                                WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '') ~ '^[0-9.]+,[0-9]+$'
                                    THEN REPLACE(REPLACE(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '.', ''), ',', '.')::numeric
                                WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '') ~ '^[0-9]+\.[0-9]{1,2}$'
                                    THEN REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.]', '', 'g')::numeric
                                WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9]', '', 'g'), '') IS NOT NULL
                                    THEN REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9]', '', 'g')::numeric
                                ELSE 0
                            END
                        ), 0) AS valor_pis
                    FROM cadu_pi p
                    LEFT JOIN cadu_pi_aux_status sp ON sp.id = p.id_status_pi
                    WHERE (p.id_cliente = cli.id_cliente OR p.id_agencia = cli.id_cliente)
                      AND DATE_TRUNC('month', p.created_at) = DATE_TRUNC('month', CURRENT_DATE)
                ) pi_data ON true
                WHERE cli.id_cliente = %s
            """, (cliente_id,))
            status = cur.fetchone()

        if not status:
            return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404

        for key in ('valor_bruto', 'valor_liquido', 'valor_pis'):
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

            # Ano civil em America/Sao_Paulo (alinha totais ao calendário local)
            y_cot = "EXTRACT(YEAR FROM (c.created_at AT TIME ZONE 'America/Sao_Paulo'))"
            y_pi = "EXTRACT(YEAR FROM (p.created_at AT TIME ZONE 'America/Sao_Paulo'))"
            m_cot = "EXTRACT(MONTH FROM (c.created_at AT TIME ZONE 'America/Sao_Paulo'))::int"
            m_pi = "EXTRACT(MONTH FROM (p.created_at AT TIME ZONE 'America/Sao_Paulo'))::int"

            cur.execute(f"""
                SELECT
                    COUNT(*) AS total_cotacoes,
                    COUNT(*) FILTER (WHERE c.status IN ('Aprovada', '3')) AS cotacoes_aprovadas,
                    COALESCE(SUM(c.valor_total_proposta), 0) AS valor_total,
                    COALESCE(SUM(c.valor_total_proposta) FILTER (WHERE c.status IN ('Aprovada', '3')), 0) AS valor_aprovado,
                    CASE WHEN COUNT(*) > 0
                         THEN ROUND(COUNT(*) FILTER (WHERE c.status IN ('Aprovada', '3'))::numeric / COUNT(*) * 100, 1)
                         ELSE 0 END AS pct_conversao
                FROM cadu_cotacoes c
                WHERE (c.client_id = %s OR c.agencia_id = %s)
                  AND c.deleted_at IS NULL
                  AND {y_cot} = %s
            """, (cliente_id, cliente_id, ano))
            resumo_cotacoes = cur.fetchone()

            cur.execute(f"""
                SELECT
                    COUNT(*) AS total_pis,
                    COUNT(*) FILTER (WHERE sp.descricao ILIKE '%%fatur%%'
                                       OR sp.descricao ILIKE '%%nf emitida%%'
                                       OR sp.descricao ILIKE '%%conclu%%'
                                       OR sp.descricao ILIKE '%%finaliz%%') AS pis_concluidos,
                    COALESCE(SUM(
                        CASE
                            WHEN p.vr_bruto_pi IS NULL OR TRIM(p.vr_bruto_pi) = '' THEN 0
                            WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '') ~ '^[0-9]+,[0-9]+$'
                                THEN REPLACE(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), ',', '.')::numeric
                            WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '') ~ '^[0-9.]+,[0-9]+$'
                                THEN REPLACE(REPLACE(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '.', ''), ',', '.')::numeric
                            WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.,]', '', 'g'), '') ~ '^[0-9]+\.[0-9]{{1,2}}$'
                                THEN REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9.]', '', 'g')::numeric
                            WHEN NULLIF(REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9]', '', 'g'), '') IS NOT NULL
                                THEN REGEXP_REPLACE(p.vr_bruto_pi, '[^0-9]', '', 'g')::numeric
                            ELSE 0
                        END
                    ), 0) AS valor_pis
                FROM cadu_pi p
                LEFT JOIN cadu_pi_aux_status sp ON sp.id = p.id_status_pi
                WHERE (p.id_cliente = %s OR p.id_agencia = %s)
                  AND {y_pi} = %s
            """, (cliente_id, cliente_id, ano))
            resumo_pis = cur.fetchone()

            # Ticket médio só sobre cotações aprovadas (expectativa comercial)
            ticket_medio = 0.0
            if resumo_cotacoes['cotacoes_aprovadas'] and resumo_cotacoes['cotacoes_aprovadas'] > 0:
                ticket_medio = float(resumo_cotacoes['valor_aprovado']) / resumo_cotacoes['cotacoes_aprovadas']

            cur.execute(f"""
                SELECT
                    {m_cot} AS mes,
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE c.status IN ('Aprovada', '3')) AS aprovadas,
                    COALESCE(SUM(c.valor_total_proposta) FILTER (WHERE c.status IN ('Aprovada', '3')), 0) AS faturamento
                FROM cadu_cotacoes c
                WHERE (c.client_id = %s OR c.agencia_id = %s)
                  AND c.deleted_at IS NULL
                  AND {y_cot} = %s
                GROUP BY {m_cot}
                ORDER BY mes
            """, (cliente_id, cliente_id, ano))
            por_mes = cur.fetchall()

            cur.execute(f"""
                SELECT
                    c.id, c.numero_cotacao, c.nome_campanha,
                    c.valor_total_proposta,
                    c.status AS status_descricao,
                    c.created_at
                FROM cadu_cotacoes c
                WHERE (c.client_id = %s OR c.agencia_id = %s)
                  AND c.deleted_at IS NULL
                  AND {y_cot} = %s
                ORDER BY c.created_at DESC
            """, (cliente_id, cliente_id, ano))
            cotacoes_lista = cur.fetchall()

            resumo_briefings = {'total_briefings': 0}
            briefings_lista = []
            briefings_por_mes = []

            try:
                y_br = "EXTRACT(YEAR FROM (b.created_at AT TIME ZONE 'America/Sao_Paulo'))"
                m_br = "EXTRACT(MONTH FROM (b.created_at AT TIME ZONE 'America/Sao_Paulo'))::int"
                cur.execute(f"""
                    SELECT COUNT(*) AS total_briefings
                    FROM cadu_briefings b
                    WHERE b.id_cliente = %s AND b.deleted_at IS NULL AND {y_br} = %s
                """, (cliente_id, ano))
                resumo_briefings = cur.fetchone() or {'total_briefings': 0}

                cur.execute(f"""
                    SELECT b.id, b.titulo, b.status, b.created_at
                    FROM cadu_briefings b
                    WHERE b.id_cliente = %s AND b.deleted_at IS NULL AND {y_br} = %s
                    ORDER BY b.created_at DESC
                """, (cliente_id, ano))
                briefings_lista = cur.fetchall()

                cur.execute(f"""
                    SELECT {m_br} AS mes, COUNT(*) AS total
                    FROM cadu_briefings b
                    WHERE b.id_cliente = %s AND b.deleted_at IS NULL AND {y_br} = %s
                    GROUP BY {m_br}
                    ORDER BY mes
                """, (cliente_id, ano))
                briefings_por_mes = cur.fetchall()
            except Exception:
                resumo_briefings = {'total_briefings': 0}
                briefings_lista = []
                briefings_por_mes = []

            try:
                cur.execute(f"""
                    SELECT
                        p.id_pi AS id,
                        p.codigo_pi_cc AS numero_pi,
                        p.titulo_pi AS campanha,
                        p.vr_bruto_pi AS vr_bruto_raw,
                        sp.descricao AS status_descricao,
                        p.created_at
                    FROM cadu_pi p
                    LEFT JOIN cadu_pi_aux_status sp ON sp.id = p.id_status_pi
                    WHERE (p.id_cliente = %s OR p.id_agencia = %s)
                      AND {y_pi} = %s
                    ORDER BY p.created_at DESC
                """, (cliente_id, cliente_id, ano))
                pis_lista = cur.fetchall()

                cur.execute(f"""
                    SELECT
                        {m_pi} AS mes,
                        p.vr_bruto_pi AS vr_bruto_raw
                    FROM cadu_pi p
                    WHERE (p.id_cliente = %s OR p.id_agencia = %s)
                      AND {y_pi} = %s
                """, (cliente_id, cliente_id, ano))
                pis_mes_raw = cur.fetchall()
            except Exception:
                pis_lista = []
                pis_mes_raw = []

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

        for p in pis_lista:
            p['valor_bruto'] = _parse_vr_bruto(p.pop('vr_bruto_raw', None))
            if p.get('created_at'):
                p['created_at'] = p['created_at'].isoformat()

        for b in briefings_lista:
            if b.get('created_at'):
                b['created_at'] = b['created_at'].isoformat()

        faturamento_mensal = [0.0] * 12
        for row in pis_mes_raw:
            idx = (row.get('mes') or 1) - 1
            if 0 <= idx < 12:
                faturamento_mensal[idx] += _parse_vr_bruto(row.get('vr_bruto_raw'))

        briefings_mensal = [0] * 12
        for row in briefings_por_mes:
            idx = (row.get('mes') or 1) - 1
            if 0 <= idx < 12:
                briefings_mensal[idx] = int(row.get('total') or 0)

        return jsonify({
            'success': True,
            'ano': ano,
            'resumo_cotacoes': resumo_cotacoes,
            'resumo_pis': resumo_pis,
            'resumo_briefings': resumo_briefings,
            'ticket_medio': round(ticket_medio, 2),
            'por_mes': por_mes,
            'faturamento_mensal': faturamento_mensal,
            'briefings_mensal': briefings_mensal,
            'cotacoes': cotacoes_lista,
            'pis_lista': pis_lista,
            'briefings_lista': briefings_lista
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


# --------------- Helpers: column existence cache ---------------

_col_cache = {}

def _check_column_exists(cur, table, column):
    key = f"{table}.{column}"
    if key not in _col_cache:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
            ) AS col_exists
        """, (table, column))
        row = cur.fetchone()
        _col_cache[key] = row['col_exists'] if isinstance(row, dict) else row[0]
    return _col_cache[key]

def _check_atividades_columns(cur):
    return _check_column_exists(cur, 'sales_atividades', 'tipo')

def _check_objetivos_columns(cur):
    return _check_column_exists(cur, 'sales_objetivos_cliente', 'data_prazo')


_NOTA_CLIENTE_MAX = 8000


@bp.route('/api/cliente/<int:cliente_id>/nota')
@login_required
def api_cliente_nota(cliente_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if not _check_column_exists(cur, 'tbl_cliente', 'nota_executivo_vendas'):
                return jsonify({'success': True, 'nota': ''})
            cur.execute("""
                SELECT nota_executivo_vendas
                FROM tbl_cliente
                WHERE id_cliente = %s
            """, (cliente_id,))
            row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404
        return jsonify({'success': True, 'nota': row.get('nota_executivo_vendas') or ''})
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_nota: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/cliente/<int:cliente_id>/nota', methods=['PUT'])
@login_required
def api_cliente_nota_salvar(cliente_id):
    data = request.get_json() or {}
    nota = data.get('nota')
    if nota is None:
        return jsonify({'success': False, 'error': 'Campo nota obrigatório'}), 400
    nota = (nota or '').strip()
    if len(nota) > _NOTA_CLIENTE_MAX:
        return jsonify({'success': False, 'error': f'Nota muito longa (máx. {_NOTA_CLIENTE_MAX} caracteres)'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            if not _check_column_exists(cur, 'tbl_cliente', 'nota_executivo_vendas'):
                return jsonify({
                    'success': False,
                    'error': 'Coluna nota_executivo_vendas ausente no banco. Reinicie a aplicação para o init_db criar a coluna, ou adicione manualmente em tbl_cliente.'
                }), 503
            cur.execute("""
                UPDATE tbl_cliente
                SET nota_executivo_vendas = %s, data_modificacao = NOW()
                WHERE id_cliente = %s
                RETURNING id_cliente
            """, (nota or None, cliente_id))
            row = cur.fetchone()
        if not row:
            return jsonify({'success': False, 'error': 'Cliente não encontrado'}), 404
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_cliente_nota_salvar: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 4: Atividades ---------------

@bp.route('/api/cliente/<int:cliente_id>/atividades')
@login_required
def api_cliente_atividades(cliente_id):
    contato_id = request.args.get('contato_id', type=int)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            has_new_cols = _check_atividades_columns(cur)
            if has_new_cols:
                query = """
                    SELECT
                        sa.id, sa.descricao, sa.data_atividade, sa.status,
                        sa.contato_id, sa.created_at,
                        COALESCE(sa.tipo, 'atividade') AS tipo,
                        sa.data_prazo,
                        sa.titulo,
                        c.nome_completo AS contato_nome,
                        ex.nome_completo AS responsavel_nome
                    FROM sales_atividades sa
                    LEFT JOIN tbl_contato_cliente c ON c.id_contato_cliente = sa.contato_id
                    LEFT JOIN tbl_contato_cliente ex ON ex.id_contato_cliente = sa.executivo_id
                    WHERE sa.cliente_id = %s
                """
            else:
                query = """
                    SELECT
                        sa.id, sa.descricao, sa.data_atividade, sa.status,
                        sa.contato_id, sa.created_at,
                        'atividade' AS tipo,
                        NULL AS data_prazo,
                        NULL AS titulo,
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

            if has_new_cols:
                query += " ORDER BY CASE sa.status WHEN 'pendente' THEN 1 WHEN 'em_andamento' THEN 2 ELSE 3 END, sa.data_prazo ASC NULLS LAST, sa.data_atividade DESC"
            else:
                query += " ORDER BY CASE sa.status WHEN 'pendente' THEN 1 WHEN 'em_andamento' THEN 2 ELSE 3 END, sa.data_atividade DESC"

            cur.execute(query, params)
            atividades = cur.fetchall()

        for a in atividades:
            if a.get('data_atividade'):
                a['data_atividade'] = a['data_atividade'].isoformat()
            if a.get('data_prazo'):
                a['data_prazo'] = a['data_prazo'].isoformat()
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
    tipo = data.get('tipo', 'atividade')
    titulo = (data.get('titulo') or '').strip() or None
    data_prazo = data.get('data_prazo') or None

    if not descricao or not data_atividade:
        return jsonify({'success': False, 'error': 'Descrição e data são obrigatórios'}), 400

    executivo_id = session.get('user_id')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if _check_atividades_columns(cur):
                cur.execute("""
                    INSERT INTO sales_atividades (cliente_id, contato_id, executivo_id, descricao, data_atividade, tipo, titulo, data_prazo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (cliente_id, contato_id, executivo_id, descricao, data_atividade, tipo, titulo, data_prazo))
            else:
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


@bp.route('/api/atividades/<int:atividade_id>', methods=['PATCH'])
@login_required
def api_atualizar_atividade(atividade_id):
    data = request.get_json() or {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            has_new = _check_atividades_columns(cur)
            sets = []
            vals = []

            if 'descricao' in data:
                d = (data.get('descricao') or '').strip()
                if not d:
                    return jsonify({'success': False, 'error': 'Descrição não pode ser vazia'}), 400
                sets.append('descricao = %s')
                vals.append(d)
            if 'data_atividade' in data and data['data_atividade']:
                sets.append('data_atividade = %s')
                vals.append(data['data_atividade'])
            if 'status' in data:
                st = data.get('status')
                if st not in ('pendente', 'em_andamento', 'concluida'):
                    return jsonify({'success': False, 'error': 'Status inválido'}), 400
                sets.append('status = %s')
                vals.append(st)
            if has_new:
                if 'titulo' in data:
                    t = (data.get('titulo') or '').strip() or None
                    sets.append('titulo = %s')
                    vals.append(t)
                if 'tipo' in data:
                    sets.append('tipo = %s')
                    vals.append(data.get('tipo') or 'atividade')
                if 'data_prazo' in data:
                    sets.append('data_prazo = %s')
                    vals.append(data.get('data_prazo') or None)
                if 'contato_id' in data:
                    sets.append('contato_id = %s')
                    cid = data.get('contato_id')
                    vals.append(int(cid) if cid else None)

            if not sets:
                return jsonify({'success': False, 'error': 'Nenhum campo para atualizar'}), 400

            sets.append('updated_at = NOW()')
            vals.append(atividade_id)
            cur.execute(
                f"UPDATE sales_atividades SET {', '.join(sets)} WHERE id = %s RETURNING id",
                vals
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({'success': False, 'error': 'Atividade não encontrada'}), 404
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_atualizar_atividade: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/atividades/<int:atividade_id>', methods=['DELETE'])
@login_required
def api_excluir_atividade(atividade_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales_atividades WHERE id = %s RETURNING id", (atividade_id,))
            row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({'success': False, 'error': 'Atividade não encontrada'}), 404
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_excluir_atividade: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# --------------- Column 5: Objetivos ---------------

@bp.route('/api/cliente/<int:cliente_id>/objetivos')
@login_required
def api_cliente_objetivos(cliente_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if _check_objetivos_columns(cur):
                cur.execute("""
                    SELECT id, texto, conquistado, data_conquista, data_prazo, created_at
                    FROM sales_objetivos_cliente
                    WHERE cliente_id = %s
                    ORDER BY conquistado ASC, created_at DESC
                """, (cliente_id,))
            else:
                cur.execute("""
                    SELECT id, texto, conquistado, data_conquista, NULL AS data_prazo, created_at
                    FROM sales_objetivos_cliente
                    WHERE cliente_id = %s
                    ORDER BY conquistado ASC, created_at DESC
                """, (cliente_id,))
            objetivos = cur.fetchall()

        for o in objetivos:
            if o.get('data_conquista'):
                o['data_conquista'] = o['data_conquista'].isoformat()
            if o.get('data_prazo'):
                o['data_prazo'] = o['data_prazo'].isoformat()
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
    data_prazo = data.get('data_prazo') or None
    if not texto:
        return jsonify({'success': False, 'error': 'Texto obrigatório'}), 400

    executivo_id = session.get('user_id')
    conn = get_db()
    try:
        with conn.cursor() as cur:
            if _check_objetivos_columns(cur) and data_prazo:
                cur.execute("""
                    INSERT INTO sales_objetivos_cliente (cliente_id, executivo_id, texto, data_prazo)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (cliente_id, executivo_id, texto, data_prazo))
            else:
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


@bp.route('/api/objetivos/<int:objetivo_id>', methods=['PATCH'])
@login_required
def api_atualizar_objetivo(objetivo_id):
    data = request.get_json() or {}
    texto = (data.get('texto') or '').strip() if 'texto' in data else None
    data_prazo = data.get('data_prazo') if 'data_prazo' in data else None

    if texto is not None and not texto:
        return jsonify({'success': False, 'error': 'Texto não pode ser vazio'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            has_prazo = _check_objetivos_columns(cur)
            sets = []
            vals = []
            if texto is not None:
                sets.append('texto = %s')
                vals.append(texto)
            if has_prazo and 'data_prazo' in data:
                sets.append('data_prazo = %s')
                vals.append(data_prazo or None)
            if not sets:
                return jsonify({'success': False, 'error': 'Nenhum campo para atualizar'}), 400
            sets.append('updated_at = NOW()')
            vals.append(objetivo_id)
            cur.execute(
                f"UPDATE sales_objetivos_cliente SET {', '.join(sets)} WHERE id = %s RETURNING id",
                vals
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({'success': False, 'error': 'Objetivo não encontrado'}), 404
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_atualizar_objetivo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/objetivos/<int:objetivo_id>', methods=['DELETE'])
@login_required
def api_excluir_objetivo(objetivo_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sales_objetivos_cliente WHERE id = %s RETURNING id", (objetivo_id,))
            row = cur.fetchone()
        conn.commit()
        if not row:
            return jsonify({'success': False, 'error': 'Objetivo não encontrado'}), 404
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        current_app.logger.error(f"Erro api_excluir_objetivo: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


def _defaults_cargo_setor_contato(cur):
    cur.execute("""
        SELECT c.id_cargo_contato, c.pk_id_aux_setor
        FROM tbl_cargo_contato c
        ORDER BY c.id_cargo_contato
        LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        return None, None
    return row.get('id_cargo_contato'), row.get('pk_id_aux_setor')


@bp.route('/api/cliente/<int:cliente_id>/contato-rapido', methods=['POST'])
@login_required
def api_cliente_contato_rapido(cliente_id):
    from .. import db as db_mod
    data = request.get_json() or {}
    nome = (data.get('nome_completo') or '').strip()
    email = (data.get('email') or '').strip().lower()
    telefone = (data.get('telefone') or '').strip() or None
    if not nome or not email:
        return jsonify({'success': False, 'error': 'Nome e email são obrigatórios'}), 400

    conn = get_db()
    try:
        with conn.cursor() as cur:
            cargo_id, setor_id = _defaults_cargo_setor_contato(cur)
            if not cargo_id or not setor_id:
                return jsonify({
                    'success': False,
                    'error': 'Cadastre ao menos um cargo/setor em tbl_cargo_contato para usar contato rápido.'
                }), 503
        try:
            novo_id = db_mod.criar_contato(
                nome_completo=nome,
                email=email,
                senha=None,
                pk_id_tbl_cliente=cliente_id,
                telefone=telefone,
                pk_id_tbl_cargo=cargo_id,
                pk_id_tbl_setor=setor_id,
                user_type='client',
            )
        except ValueError as ve:
            return jsonify({'success': False, 'error': str(ve)}), 400
        return jsonify({'success': True, 'id_contato_cliente': novo_id})
    except Exception as e:
        current_app.logger.error(f"Erro api_cliente_contato_rapido: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/cliente/<int:cliente_id>/contatos/importar', methods=['POST'])
@login_required
def api_cliente_contatos_importar(cliente_id):
    from .. import db as db_mod
    data = request.get_json() or {}
    raw = (data.get('texto') or '').strip()
    if not raw:
        return jsonify({'success': False, 'error': 'Cole as linhas no campo de texto'}), 400

    conn = get_db()
    with conn.cursor() as cur:
        cargo_id, setor_id = _defaults_cargo_setor_contato(cur)
    if not cargo_id or not setor_id:
        return jsonify({
            'success': False,
            'error': 'Cadastre ao menos um cargo/setor em tbl_cargo_contato para importar.'
        }), 503

    criados = 0
    erros = []
    for i, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = [p.strip() for p in line.replace('\t', ';').split(';')]
        if len(parts) < 2:
            parts = [p.strip() for p in line.split(',')]
        nome = (parts[0] or '').strip()
        email = (parts[1] or '').strip().lower() if len(parts) > 1 else ''
        telefone = (parts[2] or '').strip() if len(parts) > 2 else None
        if not nome or not email:
            erros.append({'linha': i, 'msg': 'Nome e email obrigatórios'})
            continue
        try:
            db_mod.criar_contato(
                nome_completo=nome,
                email=email,
                senha=None,
                pk_id_tbl_cliente=cliente_id,
                telefone=telefone,
                pk_id_tbl_cargo=cargo_id,
                pk_id_tbl_setor=setor_id,
                user_type='client',
            )
            criados += 1
        except ValueError as ve:
            erros.append({'linha': i, 'msg': str(ve)})
        except Exception as ex:
            erros.append({'linha': i, 'msg': str(ex)})

    return jsonify({'success': True, 'criados': criados, 'erros': erros})


@bp.route('/atividades-consolidadas')
@login_required
def atividades_consolidadas():
    from .. import db
    executivos = db.obter_vendedores_centralcomm()
    return render_template('sales_war_room/atividades_consolidadas.html', executivos=executivos)


@bp.route('/objetivos-consolidadas')
@login_required
def objetivos_consolidadas():
    from .. import db
    executivos = db.obter_vendedores_centralcomm()
    return render_template('sales_war_room/objetivos_consolidadas.html', executivos=executivos)


@bp.route('/api/atividades-consolidadas')
@login_required
def api_atividades_consolidadas():
    executivo_id = request.args.get('executivo_id', type=int)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            has_new = _check_atividades_columns(cur)
            q = """
                SELECT sa.id, sa.descricao, sa.data_atividade, sa.status, sa.cliente_id,
                       sa.contato_id, sa.executivo_id,
                       cli.nome_fantasia AS cliente_nome,
                       ex.nome_completo AS executivo_nome
            """
            if has_new:
                q += """,
                       COALESCE(sa.tipo, 'atividade') AS tipo,
                       sa.data_prazo,
                       sa.titulo
                """
            else:
                q += """,
                       'atividade' AS tipo,
                       NULL AS data_prazo,
                       NULL AS titulo
                """
            q += """
                FROM sales_atividades sa
                JOIN tbl_cliente cli ON cli.id_cliente = sa.cliente_id
                LEFT JOIN tbl_contato_cliente ex ON ex.id_contato_cliente = sa.executivo_id
                WHERE COALESCE(cli.status, true) = true
            """
            params = []
            if executivo_id:
                q += " AND cli.vendas_central_comm = %s"
                params.append(executivo_id)
            q += " ORDER BY CASE sa.status WHEN 'pendente' THEN 1 WHEN 'em_andamento' THEN 2 ELSE 3 END, sa.data_atividade DESC NULLS LAST LIMIT 500"
            cur.execute(q, params)
            rows = cur.fetchall()
        for a in rows:
            if a.get('data_atividade'):
                a['data_atividade'] = a['data_atividade'].isoformat()
            if a.get('data_prazo'):
                a['data_prazo'] = a['data_prazo'].isoformat()
        return jsonify({'success': True, 'atividades': rows})
    except Exception as e:
        current_app.logger.error(f"Erro api_atividades_consolidadas: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/api/objetivos-consolidadas')
@login_required
def api_objetivos_consolidadas():
    executivo_id = request.args.get('executivo_id', type=int)
    conn = get_db()
    try:
        with conn.cursor() as cur:
            has_prazo = _check_objetivos_columns(cur)
            base = """
                SELECT o.id, o.cliente_id, o.texto, o.conquistado, o.data_conquista,
                       o.executivo_id, o.created_at,
                       cli.nome_fantasia AS cliente_nome,
                       ex.nome_completo AS executivo_nome
            """
            if has_prazo:
                base += ", o.data_prazo "
            else:
                base += ", NULL::date AS data_prazo "
            base += """
                FROM sales_objetivos_cliente o
                JOIN tbl_cliente cli ON cli.id_cliente = o.cliente_id
                LEFT JOIN tbl_contato_cliente ex ON ex.id_contato_cliente = o.executivo_id
                WHERE COALESCE(cli.status, true) = true
            """
            params = []
            if executivo_id:
                base += " AND cli.vendas_central_comm = %s"
                params.append(executivo_id)
            base += " ORDER BY o.conquistado ASC, o.created_at DESC LIMIT 500"
            cur.execute(base, params)
            rows = cur.fetchall()
        for o in rows:
            if o.get('data_conquista'):
                o['data_conquista'] = o['data_conquista'].isoformat()
            if o.get('data_prazo'):
                o['data_prazo'] = o['data_prazo'].isoformat()
            if o.get('created_at'):
                o['created_at'] = o['created_at'].isoformat()
        return jsonify({'success': True, 'objetivos': rows})
    except Exception as e:
        current_app.logger.error(f"Erro api_objetivos_consolidadas: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500
