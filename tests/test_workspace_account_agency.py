from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_account_journey_is_centered_on_the_agency_team():
    template = (ROOT / 'aicentralv2/templates/cadu_workspace/account_agency.html').read_text(encoding='utf-8')
    sidebar = (ROOT / 'aicentralv2/templates/cadu_workspace/_app_sidebar.html').read_text(encoding='utf-8')
    routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')

    for tab in ('>Perfil</a>', '>Equipe</a>', '>Plano</a>', '>Uso</a>', '>Faturamento</a>'):
        assert tab in template
    assert 'Organização</a>' not in template
    assert '>Perfil</span></a>' in sidebar
    assert '"organizacao": "equipe"' in routes
    assert 'cadu_workspace/account_agency.html' in routes
    assert 'requested_section != section' in routes


def test_account_team_keeps_php_backed_actions_and_confirmation_ui():
    template = (ROOT / 'aicentralv2/templates/cadu_workspace/account_agency.html').read_text(encoding='utf-8')
    script = (ROOT / 'aicentralv2/static/js/cadu-workspace-account-agency.js').read_text(encoding='utf-8')

    for endpoint in ('create_team_invite', 'update_team_member_role', 'update_team_member_status', 'resend_team_invite', 'cancel_team_invite', 'update_organization'):
        assert endpoint in template
    assert 'data-invite-dialog' in template
    assert 'data-details-dialog' in template
    assert 'data-team-sensitive' in template
    assert "document.querySelectorAll('[data-team-sensitive]')" in script
    assert 'protect(form' in script
    assert 'cloneNode' not in script


def test_account_profile_lists_transactional_email_sources():
    template = (ROOT / 'aicentralv2/templates/cadu_workspace/account_agency.html').read_text(encoding='utf-8')
    routes = (ROOT / 'aicentralv2/cadu_workspace/routes.py').read_text(encoding='utf-8')

    assert 'E-mails disparados por página' in template
    assert 'account.email_catalog' in template
    for subject in (
        'Você foi convidado',
        'Sua conta está pronta',
        'Redefina sua senha',
        'Senha alterada',
    ):
        assert subject in routes


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
