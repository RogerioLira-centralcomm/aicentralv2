from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_account_journey_is_centered_on_the_agency_team():
    template = (ROOT / 'aicentralv2/templates/cadu_workspace/account_react.html').read_text(encoding='utf-8')
    component = (ROOT / 'frontend/cadu-design-system/components/WorkspaceAccount.jsx').read_text(encoding='utf-8')
    routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')

    for tab in ("perfil: 'Perfil'", "equipe: 'Equipe'", "planos: 'Plano'", "uso: 'Uso'", "creditos: 'Créditos'", "faturamento: 'Faturamento'"):
        assert tab in component
    assert 'WorkspaceContextSidebar' in component
    assert "'accountMode': True" in template
    assert '"organizacao": "agencia"' in routes
    assert 'cadu_workspace/account_react.html' in routes
    assert "'uso': '/uso'" in routes
    assert "'creditos': '/creditos'" in routes


def test_account_team_keeps_php_backed_actions_and_confirmation_ui():
    component = (ROOT / 'frontend/cadu-design-system/components/WorkspaceAccount.jsx').read_text(encoding='utf-8')

    for endpoint in ('endpoints.invite', 'endpoints.updateOrganization', 'endpoints.memberBase', 'endpoints.inviteBase'):
        assert endpoint in component
    for action in ('/papel', '/status', '/reenviar', '/cancelar'):
        assert action in component
    assert 'window.confirm' in component


def test_account_profile_is_identity_only_and_keeps_emails_out_of_the_page():
    component = (ROOT / 'frontend/cadu-design-system/components/WorkspaceAccount.jsx').read_text(encoding='utf-8')
    routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')

    # Transactional e-mail lists are operations data, not part of a person's profile,
    # and recipient addresses must not travel in the page bootstrap.
    assert 'E-mails disparados por página' not in component
    assert 'email_catalog' not in component and 'email_events' not in component
    assert '"email_events"' not in routes
    # Account sections live in their own sidebar beside the closed Workspace rail.
    assert 'EntityNavigator label="Conta"' in component
    assert 'cadu-ds-account-tabs' not in component


def test_workspace_invite_names_the_team_and_uses_the_real_role():
    invite = (ROOT / 'aicentralv2/templates/emails/externos/convite-usuario.html').read_text(encoding='utf-8')
    workspace_routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')
    email_service = (ROOT / 'aicentralv2/email_service.py').read_text(encoding='utf-8')

    assert 'Seu convite para {{ empresa }}.' in invite
    assert 'role_label|default' in invite
    assert "role_label='Administrador' if role == 'admin' else 'Membro'" in workspace_routes
    assert "role_label='Membro'" in email_service


def test_workspace_email_delivery_uses_canonical_links_and_history():
    email_service = (ROOT / 'aicentralv2/email_service.py').read_text(encoding='utf-8')
    routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')
    password_changed = (ROOT / 'aicentralv2/templates/emails/externos/senha-alterada.html').read_text(encoding='utf-8')

    assert "product_url('cadu'" in email_service
    assert '_record_workspace_email_event' in email_service
    assert 'cadu_workspace_email_events' in routes
    assert 'Proteger minha conta' in password_changed


def test_workspace_email_history_accepts_brevo_lifecycle_events():
    routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')
    schema = (ROOT / 'migrations/upgrade_cadu_workspace_email_events_webhooks.sql').read_text(encoding='utf-8')

    assert 'workspace_brevo_email_event' in routes
    assert 'X-Brevo-Webhook-Token' in routes
    assert "'opened': 'opened'" in routes
    assert "'click': 'clicked'" in routes
    assert 'last_event_at' in schema
