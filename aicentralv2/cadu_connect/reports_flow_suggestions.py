"""Bounded, audited page-role suggestions. Application remains deterministic."""
import hashlib
import json
import uuid
from flask import abort, session
from ..db import get_db
from .reports_v1 import _rows
from .reports_typesafe import suggest_flow_page_role, FLOW_PAGE_PROMPT_VERSION
from ..services.typesafe_service import TypeSafeError


def evidence_hash(page):
    evidence = {key:page.get(key) for key in ('id','title','path_prefix','form_count','evidence')}
    return hashlib.sha256(json.dumps(evidence,sort_keys=True,default=str).encode()).hexdigest()


def suggest(flow, page, selected, actor_id=None):
    digest = evidence_hash(page)
    scope = (selected['client_id'],)
    # This transaction lock protects both the cache lookup and daily reservation.
    _rows('SELECT pg_advisory_xact_lock(hashtext(%s),hashtext(%s))',
          (str(scope[0]),f'flow-suggestions'))
    cached = _rows("""SELECT id,result,base_revision FROM cadu_reports_flow_suggestions
        WHERE client_id=%s AND flow_id=%s AND page_id=%s
        AND base_revision=%s AND evidence_hash=%s AND status='ready'
        AND result->>'question_version'=%s AND created_at>NOW()-INTERVAL '15 minutes'
        ORDER BY created_at DESC LIMIT 1""",
        (*scope,flow['id'],page['id'],flow['draft_revision'],digest,FLOW_PAGE_PROMPT_VERSION))
    if cached:
        get_db().commit()
        item = cached[0]
        return {'suggestion_id':str(item['id']),'suggestion':item['result'],
                'base_revision':item['base_revision'],'page_id':str(page['id'])}
    count = _rows("""SELECT COUNT(*) AS total FROM cadu_reports_flow_suggestions
        WHERE client_id=%s AND created_at>NOW()-INTERVAL '24 hours'""",scope)[0]['total']
    if count >= 50:
        abort(429,description='Limite de 50 análises por cliente em 24 horas. A edição manual continua disponível.')
    pending = _rows("""SELECT id FROM cadu_reports_flow_suggestions WHERE client_id=%s
        AND status='pending' AND created_at>NOW()-INTERVAL '2 minutes' LIMIT 1""",scope)
    if pending:
        abort(409,description='Há uma análise em andamento para este cliente.')
    suggestion_id = str(uuid.uuid4())
    _rows("""INSERT INTO cadu_reports_flow_suggestions
        (id,flow_id,client_id,page_id,base_revision,evidence_hash,created_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (suggestion_id,flow['id'],*scope,page['id'],flow['draft_revision'],digest,actor_id if actor_id is not None else session['user_id']))
    get_db().commit()  # Never hold a DB lock during the network request.
    try:
        result = suggest_flow_page_role(page)
    except TypeSafeError:
        _rows("UPDATE cadu_reports_flow_suggestions SET status='failed' WHERE id=%s RETURNING id",(suggestion_id,))
        get_db().commit()
        raise
    _rows("""UPDATE cadu_reports_flow_suggestions SET status='ready',result=%s::jsonb
        WHERE id=%s RETURNING id""",(json.dumps(result),suggestion_id))
    get_db().commit()
    return {'suggestion_id':suggestion_id,'suggestion':result,
            'base_revision':flow['draft_revision'],'page_id':str(page['id'])}


def validate_application(suggestion_id, flow_id, page, selected, revision, choice):
    try:
        identifier = str(uuid.UUID(str(suggestion_id)))
    except ValueError:
        abort(400,description='Sugestão inválida.')
    items = _rows("""SELECT * FROM cadu_reports_flow_suggestions WHERE id=%s AND flow_id=%s
        AND client_id=%s AND page_id=%s AND status='ready'
        AND created_at>NOW()-INTERVAL '15 minutes' FOR UPDATE""",
        (identifier,flow_id,selected['client_id'],page['id']))
    if not items:
        abort(409,description='Sugestão indisponível ou expirada. Analise novamente.')
    item = items[0]
    if (item['base_revision'] != revision or item['evidence_hash'] != evidence_hash(page)
            or item['result'].get('role') != choice or choice == 'none'
            or item['result'].get('question_version') != FLOW_PAGE_PROMPT_VERSION):
        abort(409,description='O rascunho ou a evidência mudou. Analise novamente.')
    _rows("UPDATE cadu_reports_flow_suggestions SET status='applied',applied_at=NOW() WHERE id=%s RETURNING id",(identifier,))
    return item['result']
