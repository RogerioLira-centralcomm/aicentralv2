"""Qualificação de primeiro acesso e contato comercial posterior."""
import logging

from flask import current_app, render_template

from aicentralv2.services.brevo_service import get_brevo_service

logger = logging.getLogger(__name__)


def _internal_recipients(executivo=None):
    """Keep the commercial owner and the internal Cadu owner in the loop."""
    configured = str(current_app.config.get('ONBOARDING_INTERNAL_EMAILS') or '').split(',')
    recipients = [email.strip().lower() for email in configured if '@' in email.strip()]
    executive_email = str((executivo or {}).get('email') or '').strip().lower()
    if executive_email and executive_email not in recipients:
        recipients.insert(0, executive_email)
    return list(dict.fromkeys(recipients))


def obter_executivo_comercial():
    """Resolve Demetrius Decottignies, with the legacy name fallback."""
    from aicentralv2 import db

    return db.obter_executivo_demetrius()


DUPLICATE_EMAIL_MESSAGE = 'Este e-mail já possui uma conta. Entre ou recupere sua senha.'


def _criar_cliente_e_contato(db, *, nome, email, senha, tipo_id, executivo_id):
    """Cria cliente e contato numa única transação (A1).

    Um lock consultivo por e-mail serializa cadastros simultâneos do mesmo
    endereço (abas, Google + formulário) sem exigir índice único novo; a
    duplicidade é conferida de novo dentro do lock. Qualquer falha desfaz tudo.
    """
    conn = db.get_db()
    senha_hash = db.gerar_senha_hash(senha) if senha else None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ('cadu-signup:' + email,))
            cursor.execute("SELECT 1 FROM tbl_contato_cliente WHERE lower(email) = %s LIMIT 1", (email,))
            if cursor.fetchone():
                raise ValueError(DUPLICATE_EMAIL_MESSAGE)
            cursor.execute('''
                INSERT INTO tbl_cliente (razao_social, nome_fantasia, pessoa, status, id_tipo_cliente,
                                         vendas_central_comm, classificacao_cliente)
                VALUES (%s, %s, 'J', TRUE, %s, %s, 'Prospecção')
                RETURNING id_cliente
            ''', (nome, nome, tipo_id, executivo_id))
            client_id = cursor.fetchone()['id_cliente']
            cursor.execute('''
                INSERT INTO tbl_contato_cliente (nome_completo, email, senha, pk_id_tbl_cliente,
                                                 status, cohorts, user_type)
                VALUES (%s, %s, %s, %s, TRUE, 1, 'admin')
                RETURNING id_contato_cliente
            ''', (nome, email, senha_hash, client_id))
            contact_id = cursor.fetchone()['id_contato_cliente']
            _conceder_plano_free_e_boas_vindas(cursor, client_id)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.warning('Cadastro público de %s desfeito', email, exc_info=True)
        raise
    return client_id, contact_id


def _existe(cursor, sql, params=()):
    cursor.execute(sql, params)
    row = cursor.fetchone()
    return bool(row and next(iter(row.values()), None))


def _conceder_plano_free_e_boas_vindas(cursor, client_id):
    """A2: plano Free + lote de boas-vindas, no mesmo cursor/transação do cadastro.

    O trigger ``trg_grant_cadu_launch_credit`` (add_cadu_launch_credit.sql)
    concederia 100k ao inserir um plano ativo. Para não somar 100k aos tokens de
    boas-vindas, gravamos antes o direito ``cadu_launch_100k`` com 0 tokens: o
    trigger encontra o conflito e não concede nada. Tolerante a esquemas sem a
    tabela de direitos, sem a coluna ``source`` ou sem a definição ``free``.
    """
    from aicentralv2.cadu_billing_catalog import FREE_PLAN, welcome_tokens

    has_entitlements = _existe(cursor, "SELECT to_regclass('cadu_credit_entitlements') IS NOT NULL AS ok")
    if has_entitlements:
        cursor.execute("""INSERT INTO cadu_credit_entitlements
                            (id_cliente, entitlement_key, tokens_amount, status)
                          VALUES (%s, 'cadu_launch_100k', 0, 'replaced_by_welcome')
                          ON CONFLICT (id_cliente, entitlement_key) DO NOTHING""", (client_id,))

    tokens = welcome_tokens()
    if tokens:
        entitlement_id = None
        grant = True
        if has_entitlements:
            cursor.execute("""INSERT INTO cadu_credit_entitlements
                                (id_cliente, entitlement_key, tokens_amount, status)
                              VALUES (%s, 'cadu_welcome', %s, 'granted')
                              ON CONFLICT (id_cliente, entitlement_key) DO NOTHING
                              RETURNING id""", (client_id, tokens))
            row = cursor.fetchone()
            entitlement_id = row['id'] if row else None
            grant = entitlement_id is not None
        if grant:
            has_source = _existe(cursor, """SELECT EXISTS (SELECT 1 FROM information_schema.columns
                                             WHERE table_name = 'cadu_credits_extras'
                                               AND column_name = 'source') AS ok""")
            source_col, source_val = (', source', ", 'welcome'") if has_source else ('', '')
            cursor.execute(f"""INSERT INTO cadu_credits_extras
                                 (id_cliente, tokens_amount, tokens_used, purchase_date, expiration_date,
                                  purchased_at, expires_at, status{source_col})
                               VALUES (%s, %s, 0, NOW(), NULL, NOW(), NULL, 'active'{source_val})
                               RETURNING id""", (client_id, tokens))
            lot_id = cursor.fetchone()['id']
            if entitlement_id:
                cursor.execute("UPDATE cadu_credit_entitlements SET credit_lot_id = %s WHERE id = %s",
                               (lot_id, entitlement_id))

    cursor.execute("""SELECT id FROM cadu_plan_definitions
                       WHERE is_active AND (lower(plan_type) = %s OR lower(plan_name) = %s)
                    ORDER BY id LIMIT 1""", (FREE_PLAN['slug'], FREE_PLAN['slug']))
    definition = cursor.fetchone()
    if not definition:
        logger.warning('Definição de plano "free" ausente; cliente %s criado sem plano', client_id)
        return
    cursor.execute("""SELECT 1 FROM cadu_client_plans WHERE id_cliente = %s AND plan_status = 'active' LIMIT 1""",
                   (client_id,))
    if cursor.fetchone():
        return
    cursor.execute("""INSERT INTO cadu_client_plans
                        (id_cliente, id_plan_definition, tokens_monthly_limit, image_credits_monthly,
                         features, plan_status, plan_start_date, plan_end_date, valid_from, valid_until)
                      VALUES (%s, %s, %s, 0, '{}'::jsonb, 'active', NOW(), NULL, NOW(), NULL)""",
                   (client_id, definition['id'], FREE_PLAN['tokens_monthly']))


def provisionar_conta_publica(*, nome, email, senha=None):
    """Create one CRM client/contact pair for a new public Cadu account."""
    from aicentralv2 import db

    email = str(email or '').strip().lower()
    nome = ' '.join(str(nome or '').split())[:180]
    from aicentralv2.auth import is_reserved_org_name
    # O nome vira nome_fantasia do cliente, que decide is_centralcomm na sessão.
    if is_reserved_org_name(nome):
        raise ValueError('Este nome não pode ser usado no cadastro. Informe seu nome completo.')
    if db.obter_contato_por_email(email):
        raise ValueError(DUPLICATE_EMAIL_MESSAGE)
    executivo = obter_executivo_comercial()
    if not executivo or not executivo.get('id_contato_cliente'):
        raise ValueError('Não foi possível associar o executivo comercial agora.')
    tipos = db.obter_tipos_cliente() or []
    tipo = next(
        (item for item in tipos if 'prospec' in str(item.get('display') or '').lower()),
        tipos[0] if tipos else None,
    )
    if not tipo or not tipo.get('id_tipo_cliente'):
        raise ValueError('Não foi possível preparar o tipo de conta agora.')
    client_id, contact_id = _criar_cliente_e_contato(db, nome=nome, email=email, senha=senha,
                                                    tipo_id=tipo['id_tipo_cliente'],
                                                    executivo_id=executivo['id_contato_cliente'])
    user = db.obter_contato_por_id(contact_id) or {
        'id_contato_cliente': contact_id,
        'nome_completo': nome,
        'email': email,
        'pk_id_tbl_cliente': client_id,
        'user_type': 'admin',
    }
    user['pk_id_tbl_cliente'] = client_id
    return user, executivo


def enviar_notificacao_cadastro(*, usuario, executivo, auth_method='form'):
    """Notify the commercial owner and Apolo immediately after account creation."""
    recipients = _internal_recipients(executivo)
    if not recipients:
        logger.warning('Cadastro criado sem destinatários internos configurados.')
        return {'success': False, 'error': 'Destinatários internos não configurados'}
    html = render_template(
        'emails/internos/novo-cadastro-cadu.html',
        usuario=usuario,
        auth_method='Google' if auth_method == 'google' else 'formulário',
    )
    return get_brevo_service().enviar_email(
        to_email=recipients,
        to_name='Equipe comercial Cadu',
        subject=f'Novo cadastro no Cadu · {usuario.get("nome_completo") or usuario.get("email")}',
        html_content=html,
    )


def enviar_notificacao_demetrius(*, usuario, onboarding, executivo):
    recipients = _internal_recipients(executivo)
    if not recipients:
        logger.warning('Onboarding concluído sem e-mail configurado para Demétrius.')
        return {'success': False, 'error': 'Destinatários internos não configurados'}
    perfil = 'Agência' if onboarding['perfil'] == 'agencia' else 'Cliente final'
    html = render_template('emails/internos/onboarding-concluido.html', usuario=usuario,
                           onboarding=onboarding, perfil=perfil)
    return get_brevo_service().enviar_email(
        to_email=recipients, to_name='Equipe comercial Cadu',
        subject=f'Novo onboarding: {usuario["nome_completo"]} ({perfil})', html_content=html,
    )


def enviar_email_onboarding_usuario(*, usuario, organization_name, brand_name, project_name,
                                    perfil=None):
    """Confirm the Workspace base after the first brand/project is created."""
    from aicentralv2.services.brevo_service import get_brevo_product_service, product_email_brand

    brand = product_email_brand('workspace')
    return get_brevo_product_service('workspace').enviar_email_com_template(
        template_name='workspace-onboarding-concluido.html',
        template_folder='emails/externos',
        to_email=usuario.get('email'),
        to_name=usuario.get('nome_completo') or 'pessoa do time',
        subject='Sua primeira base está pronta no Cadu Workspace',
        params={
            'PRIMEIRO_NOME': (usuario.get('nome_completo') or 'pessoa do time').split()[0],
            'EMPRESA': organization_name or 'sua organização',
            'MARCA': brand_name or 'sua marca',
            'PROJETO': project_name or 'seu projeto',
            'PERFIL': perfil or 'cliente_final',
            'WORKSPACE_URL': current_app.config.get('WORKSPACE_URL', 'https://workspace.centralcomm.media'),
            'BRAND': brand,
            # `welcome.png` is part of the published Workspace email set;
            # keep onboarding on an asset that is available in production.
            'ILLUSTRATION_URL': brand['illustrations_url'] + 'welcome.png',
        },
    )


def processar_followups_onboarding(limit=50):
    """Envia apenas itens persistidos e vencidos; seguro para execução recorrente."""
    from aicentralv2 import db

    enviados = falhas = 0
    for item in db.obter_followups_onboarding_vencidos(limit=limit):
        reply_email = item.get('executivo_email') or current_app.config.get('DEMETRIUS_EMAIL')
        if not reply_email:
            db.registrar_resultado_followup_onboarding(item['id'], success=False,
                                                       error='E-mail do Demétrius não configurado')
            falhas += 1
            continue
        perfil = 'agência' if item['perfil'] == 'agencia' else 'cliente final'
        html = render_template('emails/externos/onboarding-demetrius.html', usuario=item,
                               perfil=perfil, demetrius_nome=item.get('executivo_nome') or
                               current_app.config.get('DEMETRIUS_NAME'))
        result = get_brevo_service().enviar_email(
            to_email=item['email'], to_name=item['nome_completo'],
            subject='Posso ajudar você a começar no Cadu?', html_content=html,
            reply_to={'email': reply_email,
                      'name': item.get('executivo_nome') or current_app.config.get('DEMETRIUS_NAME')},
        )
        db.registrar_resultado_followup_onboarding(item['id'], success=result.get('success', False),
                                                   error=result.get('error'))
        enviados += int(bool(result.get('success')))
        falhas += int(not result.get('success'))
    return {'enviados': enviados, 'falhas': falhas}
