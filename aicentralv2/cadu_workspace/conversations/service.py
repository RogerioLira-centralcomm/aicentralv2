"""Dify chat using the existing PHP conversation and message tables."""
import json
from uuid import UUID, uuid4

from flask import abort, session, current_app

from ...cadu_family import context, dify, repository
from ...cadu_family.catalog import PROFILES
from .guardrails import validate_message, validate_files, history_context, require_available_intent
from .orchestration import choose_mode
from .provider_events import ProviderEvents
from . import catalog_tools, result_cards
from . import recovery


def modes(user_id):
    return repository.rows('''SELECT s.slug AS id, s.title, s.default_prompt,
                                    COALESCE(p.prompt, s.default_prompt) AS prompt,
                                    (p.prompt IS NOT NULL) AS customized,
                                    (s.slug = COALESCE(a.skill_slug, 'ideias')) AS active
                               FROM cadu_chat_skills s
                          LEFT JOIN cadu_chat_skill_user_prompts p
                                 ON p.skill_slug = s.slug AND p.id_contato_cliente = %s
                          LEFT JOIN cadu_chat_user_skill_active a
                                 ON a.id_contato_cliente = %s
                              WHERE s.is_active = TRUE ORDER BY s.sort_order, s.id''', (user_id, user_id))


def valid_mode(user_id, slug):
    return next((item for item in modes(user_id) if item['id'] == slug), None)


def set_active_mode(user_id, slug):
    if not isinstance(slug, str) or not valid_mode(user_id, slug):
        abort(400, description='Modo de contexto inválido.')
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_chat_user_skill_active (id_contato_cliente, skill_slug, updated_at)
                           VALUES (%s, %s, NOW())
                           ON CONFLICT (id_contato_cliente)
                           DO UPDATE SET skill_slug = EXCLUDED.skill_slug, updated_at = NOW()''', (user_id, slug))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return modes(user_id)


def update_mode_prompt(user_id, slug, prompt):
    if not isinstance(prompt, str):
        abort(400, description='Informe as instruções deste modo.')
    prompt = prompt.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not 1 <= len(prompt) <= 3000:
        abort(400, description='As instruções devem ter entre 1 e 3.000 caracteres.')
    if not valid_mode(user_id, slug):
        abort(400, description='Modo de contexto inválido.')
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''INSERT INTO cadu_chat_skill_user_prompts (id_contato_cliente, skill_slug, prompt, updated_at)
                           VALUES (%s, %s, %s, NOW())
                           ON CONFLICT (id_contato_cliente, skill_slug)
                           DO UPDATE SET prompt = EXCLUDED.prompt, updated_at = NOW()''', (user_id, slug, prompt))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return modes(user_id)


def reset_mode_prompt(user_id, slug):
    if not valid_mode(user_id, slug):
        abort(400, description='Modo de contexto inválido.')
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            cur.execute('''DELETE FROM cadu_chat_skill_user_prompts
                            WHERE id_contato_cliente = %s AND skill_slug = %s''', (user_id, slug))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return modes(user_id)


def lock_organization_generation(cur, organization_id):
    """Serialize admission until provider accounting for the previous run ends.

    This prevents concurrent requests spending the same observed balance.
    It is not a per-response token cap or a replacement for usage reconciliation.
    Stale runs fail closed until reconciled; never expire an active run blindly.
    """
    cur.execute('SELECT id_cliente FROM tbl_cliente WHERE id_cliente = %s FOR UPDATE', (organization_id,))
    cur.execute('''SELECT r.id FROM cadu_family_chat_runs r
                     JOIN cadu_family_conversation_context c ON c.conversation_id = r.conversation_id
                    WHERE c.organization_id = %s AND r.status = 'running' LIMIT 1''', (organization_id,))
    if cur.fetchone():
        abort(409, description='Há uma geração em andamento nesta organização. Aguarde sua conclusão antes de enviar outra.')


def project_knowledge_context(project_ref, brand_ref, client_id, query):
    """Build a small, attributable context packet for an authorized project.

    The Dify input remains a string for compatibility, but every record is
    scoped by the selected client.  Indexed excerpts are optional so older
    databases keep the existing project-only behavior.
    """
    if not isinstance(project_ref, str) or not project_ref.startswith('ci:'):
        return ''
    project_id = project_ref[3:]
    try:
        projects = repository.rows('''SELECT nome, descricao, instrucoes, publico, posicionamento, tom_de_voz
                                        FROM cadu_ci_projetos WHERE id = %s AND id_cliente = %s''',
                                   (project_id, client_id))
    except Exception:
        return ''
    if not projects:
        return ''
    packet = {'projeto': projects[0]}
    if isinstance(brand_ref, str) and brand_ref.startswith('studio:'):
        try:
            brands = repository.rows('''SELECT name, sector, brand_profile
                                           FROM cx_clients
                                          WHERE id = %s AND crm_client_id = %s''',
                                     (brand_ref[7:], client_id))
            if brands:
                brand = brands[0]
                if isinstance(brand.get('brand_profile'), str):
                    try:
                        brand['brand_profile'] = json.loads(brand['brand_profile'])
                    except (TypeError, ValueError):
                        brand['brand_profile'] = {}
                packet['marca'] = brand
        except Exception:
            pass
    terms = ' '.join(str(query or '').split())[:400]
    if terms:
        try:
            sources = repository.rows('''SELECT titulo, LEFT(conteudo, 1000) AS trecho
                                          FROM cadu_ci_chunks
                                         WHERE projeto_id = %s AND id_cliente = %s
                                           AND to_tsvector('portuguese', conteudo) @@ plainto_tsquery('portuguese', %s)
                                      ORDER BY ordem ASC LIMIT 4''', (project_id, client_id, terms))
            packet['fontes_verificadas'] = [
                {'fonte': row.get('titulo') or 'Fonte sem título', 'trecho': row.get('trecho') or ''}
                for row in sources
            ]
        except Exception:
            # Indexing is additive. A missing legacy chunks table must never
            # suppress the explicitly saved project context.
            packet['fontes_verificadas'] = []
    return json.dumps(packet, ensure_ascii=False, default=str)[:24000]


def project_sources(project_context):
    """Return cited sources without confusing private project and global Base Cadu."""
    try:
        packet = json.loads(project_context or '{}')
    except (TypeError, ValueError):
        return []
    # Older conversations stored project fields at the root. New packets make
    # the boundary explicit, but retaining this fallback keeps their history
    # readable after the upgrade.
    private_context = packet.get('contexto_projeto_privado', packet)
    values = private_context.get('fontes_verificadas') or [] if isinstance(private_context, dict) else []
    sources = []
    for value in values[:4]:
        if not isinstance(value, dict):
            continue
        title = str(value.get('fonte') or 'Fonte sem título').strip()[:250]
        excerpt = str(value.get('trecho') or '').strip()[:1000]
        sources.append({'title': title or 'Fonte sem título', 'excerpt': excerpt})
    for value in (packet.get('base_cadu_global_publicada') or [])[:4]:
        if not isinstance(value, dict):
            continue
        title = str(value.get('fonte') or 'Documento institucional').strip()[:250]
        excerpt = str(value.get('trecho') or '').strip()[:1000]
        sources.append({'title': 'Base Cadu — ' + (title or 'Documento institucional'), 'excerpt': excerpt})
    return sources


def contextual_packet(project_context, query):
    """Keep private Workspace RAG and published institutional RAG separate.

    Dify currently declares one string variable named ``projeto_context``.
    Until its app schema gains a second variable, this explicit envelope keeps
    backward compatibility while preventing the global Base Cadu from being
    mistaken for private project material.
    """
    try:
        from ...cadu_skills import knowledge
        entries = knowledge.context(query)
    except Exception:
        entries = []
    try:
        private_context = json.loads(project_context) if project_context else {}
    except (TypeError, ValueError):
        private_context = {'contexto_legacy': str(project_context or '')[:4000]}
    packet = {
        'contexto_projeto_privado': private_context,
        'base_cadu_global_publicada': entries,
    }
    return json.dumps(packet, ensure_ascii=False)[:24000]


def prepare(data, selected):
    dify.settings()  # Fail before storing a turn if the provider is not configured.
    user = context.identity()
    query = validate_message(data.get('message'))
    require_available_intent(query)
    if data.get('profile') not in PROFILES:
        abort(400, description='Informe uma mensagem de até 20.000 caracteres e uma solução válida.')
    try:
        run_id = str(UUID(str(data.get('request_id'))))
    except (ValueError, TypeError):
        abort(400, description='Identificador de envio inválido.')
    profile = data['profile']
    existing = data.get('conversation_id')
    conversation_id = str(existing or uuid4())
    # People no longer choose a mode. The server selects a controlled prompt
    # posture from the installed skills based on the request itself.
    chosen, routing = choose_mode(modes(user['id']), query)
    if chosen is None:
        abort(503, description='As especializações do Cadu estão sendo configuradas.')
    inventory = {item['ref']: item for item in context.inventory(selected['client_id'])}
    # Existing threads retain their bound context even when opened in another product.
    saved_context = (repository.conversation_context(user, selected['client_id'], conversation_id) if existing else None) or session.get('family_context') or {}
    if saved_context.get('profile') in PROFILES:
        profile = saved_context['profile']
    project_ref = saved_context.get('project_ref')
    brand_ref = saved_context.get('brand_ref')
    for ref in (project_ref, brand_ref):
        if ref and ref not in inventory:
            abort(409, description='O contexto mudou. Selecione o projeto e a marca novamente.')
    upload_ids = validate_files(data.get('files'))
    uploads = repository.rows('''SELECT id, provider_id, kind, name FROM cadu_family_chat_uploads
                                 WHERE id::text = ANY(%s) AND user_id = %s AND client_id = %s''',
                              ([str(value) for value in upload_ids], user['id'], selected['client_id'])) if upload_ids else []
    if len(uploads) != len(set(str(value) for value in upload_ids)):
        abort(403, description='Um arquivo não pertence a este cliente ou usuário.')
    project_context = contextual_packet(
        project_knowledge_context(project_ref, brand_ref, selected['client_id'], query), query)
    old = repository.conversation_messages(user['id'], selected['client_id'], conversation_id) if existing else []
    history = history_context(old or [])
    conn = repository.get_db()
    try:
        with conn.cursor() as cur:
            request_hash = recovery.fingerprint(data)
            previous = recovery.existing_run(cur, run_id, user, selected['client_id'], request_hash)
            if previous:
                conn.rollback()  # Release the advisory lock; no writes on replay.
                return previous
            lock_organization_generation(cur, user['organization_id'])
            current_plan = repository.plan(user['organization_id'])
            cur.execute('''SELECT COALESCE(SUM(quantidade), 0) AS used FROM cadu_token_usage
                           WHERE id_cliente = %s AND created_at >= DATE_TRUNC('month', NOW())''', (user['organization_id'],))
            if cur.fetchone()['used'] >= int(current_plan.get('tokens_monthly_limit') or 0):
                abort(409, description='O limite de tokens foi atingido. Confira o plano no Workspace.')
            cur.execute('SELECT id FROM cadu_family_chat_runs WHERE id = %s', (run_id,))
            if cur.fetchone():
                abort(409, description='Este envio já foi recebido. Atualize o histórico antes de tentar novamente.')
            if existing:
                cur.execute('''SELECT id, dify_conversation_id, total_mensagens FROM cadu_conversations
                               WHERE id = %s AND id_contato_cliente = %s AND id_cliente = %s FOR UPDATE''',
                            (conversation_id, user['id'], selected['client_id']))
                conversation = cur.fetchone()
                if not conversation:
                    abort(404)
                cur.execute('SELECT id FROM cadu_family_chat_runs WHERE conversation_id = %s AND status = \'running\'', (conversation_id,))
                if cur.fetchone():
                    abort(409, description='Aguarde a resposta atual ou interrompa a geração.')
            else:
                cur.execute('''INSERT INTO cadu_conversations
                        (id, id_cliente, id_contato_cliente, titulo, status, total_mensagens, projeto_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, 'ativa', 0, %s, NOW(), NOW())''',
                        (conversation_id, selected['client_id'], user['id'], query[:120],
                         project_ref[3:] if project_ref and project_ref.startswith('ci:') else None))
                conversation = {'dify_conversation_id': None, 'total_mensagens': 0}
            cur.execute('''INSERT INTO cadu_family_conversation_context
                    (conversation_id, user_id, organization_id, client_id, profile, project_ref, brand_ref)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING''',
                    (conversation_id, user['id'], user['organization_id'], selected['client_id'], profile, project_ref, brand_ref))
            cur.execute('SELECT * FROM cadu_family_conversation_context WHERE conversation_id = %s', (conversation_id,))
            bound = cur.fetchone()
            if (bound['user_id'], bound['organization_id'], bound['client_id'], bound['profile'], bound['project_ref'], bound['brand_ref']) != (
                    user['id'], user['organization_id'], selected['client_id'], profile, project_ref, brand_ref):
                abort(409, description='Esta conversa pertence a outro perfil ou contexto. Abra uma nova conversa.')
            cur.execute('''INSERT INTO cadu_family_chat_runs (id, conversation_id, user_id, client_id, status, request_hash)
                           VALUES (%s, %s, %s, %s, 'running', %s)''', (run_id, conversation_id, user['id'], selected['client_id'], request_hash))
            cur.execute('''INSERT INTO cadu_conversation_messages (id, conversation_id, role, content, files, created_at)
                           VALUES (%s, %s, 'user', %s, %s::jsonb, NOW())''',
                        (str(uuid4()), conversation_id, query, json.dumps([{'id': str(row['id']), 'name': row['name']} for row in uploads])))
            run = build_run(run_id, conversation_id, user, selected, chosen, profile,
                            project_context, conversation, query, uploads, existing, history, routing)
            run['routing'] = routing
            if current_app.config.get('CADU_CHAT_WORKER_ENABLED', False):
                from .jobs import enqueue
                enqueue(cur, run)
                run['queued'] = True
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return run


def build_run(run_id, conversation_id, user, selected, chosen, profile,
              project_context, conversation, query, uploads, existing, history, routing=None):
    """Build provider input before committing admission (and an optional job)."""
    route = routing if isinstance(routing, dict) else {}
    # Keep the Dify schema stable while making the input machine-readable.  The
    # prompt can now use one compact contract instead of re-parsing a long
    # server-concatenated instruction string on every turn.
    skill_context = json.dumps({
        'versao': '2.0',
        'agente': 'Cadu',
        'perfil': {'id': profile, 'descricao': PROFILES[profile]},
        'orquestracao': {
            'especializacao': str(chosen['id'])[:100],
            'solucao': str(route.get('solution') or 'conversa')[:80],
            'complexidade': str(route.get('complexity') or 'baixa')[:32],
        },
        'diretrizes_especificas': str(chosen.get('prompt') or '')[:6000],
        'fronteiras_de_contexto': {
            'projeto_context': 'JSON com contexto_projeto_privado e base_cadu_global_publicada.',
            'prioridade': 'Use o contexto privado para decisões do projeto; trate a base global como institucional.',
            'privacidade': 'Nunca revele dados privados que não sejam necessários para responder ao pedido atual.',
        },
    }, ensure_ascii=False, separators=(',', ':'))
    files_context = json.dumps({
        'versao': '2.0',
        'arquivos_anexados': [
            {'nome': str(item.get('name') or '')[:240], 'tipo': str(item.get('kind') or '')[:80]}
            for item in uploads[:3]
        ],
        'orientacao': 'Use somente o conteúdo dos arquivos anexados que for pertinente ao pedido.',
    }, ensure_ascii=False, separators=(',', ':'))
    inputs = {'nome_usuario': user['name'], 'nome_cliente': selected['client_name'], 'profile': profile,
              'skill_id': 'orquestrador', 'skill_context': skill_context,
              'files_context': files_context, 'projeto_context': project_context,
              'is_first_message': 'true' if not conversation['total_mensagens'] else 'false',
              'saudacao_permitida': 'sim' if query.lower().strip('!.? ') in ('oi', 'olá', 'bom dia', 'boa tarde', 'boa noite') and not conversation['total_mensagens'] else 'nao',
              'turn_index': str(int(conversation['total_mensagens'] or 0) // 2 + 1)}
    payload = {'query': query, 'user': 'user-' + str(user['id']), 'inputs': inputs, 'response_mode': 'streaming',
               'files': [{'type': row['kind'], 'transfer_method': 'local_file', 'upload_file_id': row['provider_id']} for row in uploads]}
    if conversation['dify_conversation_id']:
        payload['conversation_id'] = conversation['dify_conversation_id']
    elif existing:
        if history:
            payload['query'] = '[Histórico da conversa]\n' + history + '\n[Mensagem atual]\n' + query
    return {'run_id': run_id, 'conversation_id': conversation_id, 'payload': payload,
            'organization_id': user['organization_id'], 'client_id': selected['client_id'],
            'user_id': user['id'], 'profile': profile,
            'project_sources': project_sources(project_context)}


def stream(run):
    answer, state, provider_id, usage, task_id = '', 'failed', None, {}, None
    provider = ProviderEvents()
    def event(kind, **values):
        return 'data: ' + json.dumps({'event': kind, **values}, ensure_ascii=False) + '\n\n'
    try:
        yield event('start', conversation_id=run['conversation_id'], run_id=run['run_id'])
        for data in dify.events(run['payload']):
            provider_id = data.get('conversation_id') or provider_id
            if data.get('task_id') and data['task_id'] != task_id:
                task_id = data['task_id']
                conn = repository.get_db()
                with conn.cursor() as cur:
                    cur.execute('UPDATE cadu_family_chat_runs SET task_id = %s WHERE id = %s', (data['task_id'], run['run_id']))
                conn.commit()
            projected = provider.feed(data)
            card = catalog_tools.project(data, run.get('profile'), run.get('client_id'), run.get('user_id'))
            if card:
                projected.append(card)
            result = result_cards.project(data, run.get('profile'), run.get('client_id'), run.get('user_id'))
            if result:
                projected.append(result)
            answer, usage = provider.answer, provider.usage
            state = 'completed' if provider.completed else 'failed'
            for item in projected:
                yield event(item['event'], **{key: value for key, value in item.items() if key != 'event'})
        if state != 'completed':
            raise dify.DifyUnavailable('A geração terminou antes da confirmação do Dify.')
        if answer and run.get('project_sources'):
            yield event('sources', sources=run['project_sources'])
    except GeneratorExit:
        state = 'stopped'
        if task_id:
            try:
                dify.stop(task_id, run['payload']['user'])
            except Exception:
                pass  # Persist the partial response even if the provider is unreachable.
        raise
    except Exception:
        state = 'failed'
        yield event('error', message='A geração foi interrompida. Consulte o histórico antes de enviar novamente.')
    finally:
        conn = repository.get_db()
        try:
            with conn.cursor() as cur:
                message_id = str(uuid4())
                prompt_tokens = max(0, int(usage.get('prompt_tokens') or 0))
                completion_tokens = max(0, int(usage.get('completion_tokens') or 0))
                cur.execute('''INSERT INTO cadu_conversation_messages
                       (id, conversation_id, role, content, tokens_entrada, tokens_saida, metadata, created_at)
                       VALUES (%s, %s, 'assistant', %s, %s, %s, %s::jsonb, NOW())''',
                       (message_id, run['conversation_id'], answer,
                        prompt_tokens, completion_tokens, json.dumps({'status': state,
                         'project_sources': run.get('project_sources', []) if state == 'completed' else []})))
                for kind, quantity in (('entrada', prompt_tokens), ('saida', completion_tokens)):
                    if quantity:
                        cur.execute('''INSERT INTO cadu_token_usage
                            (conversation_id, message_id, id_cliente, id_contato_cliente, tipo, quantidade, modelo)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                            (run['conversation_id'], message_id, run['organization_id'], run['user_id'], kind, quantity, 'dify'))
                cur.execute('''UPDATE cadu_conversations SET dify_conversation_id = COALESCE(dify_conversation_id, %s),
                        total_tokens_entrada = COALESCE(total_tokens_entrada, 0) + %s,
                        total_tokens_saida = COALESCE(total_tokens_saida, 0) + %s,
                        total_mensagens = (SELECT COUNT(*) FROM cadu_conversation_messages WHERE conversation_id = %s),
                        updated_at = NOW() WHERE id = %s''', (provider_id, prompt_tokens, completion_tokens, run['conversation_id'], run['conversation_id']))
                cur.execute('UPDATE cadu_family_chat_runs SET status = %s, finished_at = NOW() WHERE id = %s', (state, run['run_id']))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    yield event('done', conversation_id=run['conversation_id'], status=state)
