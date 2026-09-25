#!/bin/bash

# Auto-fix: remove \r (Windows line endings) e re-executa se necessario
if grep -qP '\r' "$0" 2>/dev/null; then
    sed -i 's/\r$//' "$0"
    exec bash "$0" "$@"
fi

# Script de Deploy - AIcentral v2
set -e
set -o pipefail
SERVICE_STOPPED=0
mkdir -p logs
DEPLOY_LOG="logs/deploy-$(date +%Y%m%d-%H%M%S).log"
: > "$DEPLOY_LOG"
# O servidor de produção atende a aplicação em :8001 pelo gunicorn.service.
# Não iniciar aicentralv2.service em paralelo: ele disputa a mesma porta.
APP_SERVICE="gunicorn.service"

restore_service_on_error() {
    local exit_code=$?
    trap - ERR
    if [ "$SERVICE_STOPPED" = "1" ]; then
        echo ""
        echo "  > Falha no deploy; tentando restaurar o serviço..."
        sudo systemctl start "$APP_SERVICE" 2>/dev/null || true
    fi
    echo "  > Detalhes: $DEPLOY_LOG"
    tail -n 40 "$DEPLOY_LOG" 2>/dev/null || true
    exit "$exit_code"
}
trap restore_service_on_error ERR
export SYSTEMD_PAGER=""
export PAGER="cat"
export SYSTEMD_LESS=""
export TERM="${TERM:-xterm}"

echo ""
echo "========================================"
echo "  Deploy AIcentral v2"
echo "========================================"
echo "  Log detalhado: $DEPLOY_LOG"
echo ""

# 1. Parar servico ANTES de tudo
echo "[1/7] Parando servico..."
sudo systemctl stop "$APP_SERVICE" 2>/dev/null || true
SERVICE_STOPPED=1
sleep 2

# Garantir que nenhum worker órfão ficou vivo. O stop explícito acima evita que
# o Restart=always do systemd recrie o processo durante esta limpeza.
sudo pkill -9 -f "gunicorn.*run:app" 2>/dev/null || true
sleep 1

# Verificar que a porta 8001 esta livre
if sudo ss -tlnp 2>/dev/null | grep -q ':8001'; then
    echo "  > Porta 8001 ainda ocupada, matando processo..."
    sudo fuser -k 8001/tcp 2>/dev/null || true
    sleep 2
fi

# Compatibilidade com versões anteriores do service, que criavam esse pidfile.
# A unidade atual não usa mais PID file: o systemd é a única fonte de estado.
sudo rm -f /var/www/aicentralv2/gunicorn.pid
echo "  > OK"

# 2. Atualizar codigo
echo ""
echo "[2/7] Atualizando codigo..."
# Compatibilidade de transição: a primeira atualização após o commit que
# remove node_modules do Git precisa descartar alterações antigas para que a
# remoção dos arquivos rastreados não bloqueie o pull. Depois do primeiro
# pull bem-sucedido, git ls-files não encontra mais esse diretório.
if git ls-files --error-unmatch node_modules >/dev/null 2>&1; then
    if git status --porcelain -- node_modules 2>/dev/null | grep -q .; then
        echo "  > Limpando node_modules ainda rastreado no checkout antigo..."
        git checkout -- node_modules 2>/dev/null || \
            git restore -- node_modules 2>/dev/null || true
    fi
fi

# Artefatos gerados no servidor podem ficar diferentes do commit e bloquear o
# pull. Guardamos uma cópia para auditoria e restauramos a versão do Git; os
# builds abaixo recriam os artefatos a partir do código atualizado.
restore_generated_file() {
    local generated_file="$1"
    local backup_dir="logs/deploy-backups"
    local backup_name
    local backup_file

    if git diff --quiet -- "$generated_file"; then
        return 0
    fi

    mkdir -p "$backup_dir"
    backup_name="$(basename "$generated_file")"
    backup_file="$backup_dir/${backup_name}.$(date +%Y%m%d-%H%M%S)"
    if [ -f "$generated_file" ]; then
        cp "$generated_file" "$backup_file"
    else
        git diff -- "$generated_file" > "$backup_file.patch"
        backup_file="$backup_file.patch"
    fi
    echo "  > Artefato gerado salvo em $backup_file; restaurando versao do Git..."
    git restore --source=HEAD --worktree -- "$generated_file" 2>/dev/null || \
        git checkout -- "$generated_file"
}

restore_generated_file "aicentralv2/static/css/video-studio.css"
restore_generated_file "aicentralv2/static/cadu_auth/app.css"
restore_generated_file "aicentralv2/static/cadu_studio/editor/react/app.css"
restore_generated_file "aicentralv2/static/cadu_studio/editor/react/app.js"
restore_generated_file "aicentralv2/static/cadu_workspace/conversations/react/app.css"
restore_generated_file "aicentralv2/static/cadu_workspace/conversations/react/app.js"
git pull origin main >> "$DEPLOY_LOG" 2>&1
# Renormalizar line endings apos pull
git checkout -- . 2>/dev/null || true
echo "  > OK"

# 2b. Build frontend (artefatos gerados somente quando a camada visual mudou)
echo ""
echo "[2b/8] Build frontend (Tailwind)..."
FRONTEND_STATE_FILE="${FRONTEND_STATE_FILE:-logs/.last-frontend-build-revision}"
FRONTEND_REVISION="$(git rev-parse HEAD)"
RUN_FRONTEND_BUILD=1
if [ "${FORCE_FRONTEND_BUILD:-0}" != "1" ] && [ -s "$FRONTEND_STATE_FILE" ]; then
    LAST_FRONTEND_REVISION="$(head -n 1 "$FRONTEND_STATE_FILE")"
    if git cat-file -e "${LAST_FRONTEND_REVISION}^{commit}" 2>/dev/null && \
       git diff --quiet "$LAST_FRONTEND_REVISION" "$FRONTEND_REVISION" -- \
           frontend aicentralv2/templates aicentralv2/static/cadu_workspace \
           aicentralv2/static/cadu_studio aicentralv2/static/css package.json \
           package-lock.json build_frontend.sh postcss.config.js \
           tailwind.config.js vite.auth.config.mjs vite.conversations.config.mjs \
           vite.studio-editor.config.mjs && \
       [ -f "aicentralv2/static/css/tailwind/output.css" ] && \
       [ -f "aicentralv2/static/css/tailwind/output-legacy.css" ]; then
        RUN_FRONTEND_BUILD=0
    fi
fi

if [ "$RUN_FRONTEND_BUILD" = "1" ] && [ -x "./build_frontend.sh" ]; then
    # Keep the detailed log while streaming progress to the terminal. Without
    # this, npm ci/Vite can run for several minutes and the deploy appears
    # frozen at [2b/8].
    bash ./build_frontend.sh 2>&1 | tee -a "$DEPLOY_LOG"
    mkdir -p "$(dirname "$FRONTEND_STATE_FILE")"
    printf '%s\n' "$FRONTEND_REVISION" > "${FRONTEND_STATE_FILE}.tmp"
    mv "${FRONTEND_STATE_FILE}.tmp" "$FRONTEND_STATE_FILE"
    echo "  > OK (frontend compilado para $FRONTEND_REVISION)"
elif [ "$RUN_FRONTEND_BUILD" = "1" ] && command -v npm >/dev/null 2>&1 && [ -f package.json ]; then
    npm install --no-audit --no-fund >> "$DEPLOY_LOG" 2>&1
    npm run build >> "$DEPLOY_LOG" 2>&1
    mkdir -p "$(dirname "$FRONTEND_STATE_FILE")"
    printf '%s\n' "$FRONTEND_REVISION" > "${FRONTEND_STATE_FILE}.tmp"
    mv "${FRONTEND_STATE_FILE}.tmp" "$FRONTEND_STATE_FILE"
    echo "  > OK (frontend compilado para $FRONTEND_REVISION)"
elif [ "$RUN_FRONTEND_BUILD" = "0" ]; then
    echo "  > Frontend sem alteracoes; pulando build."
else
    echo "  > ERRO: build frontend indisponivel — output.css nao sera gerado"
    exit 1
fi

# 3. Atualizar dependencias
echo ""
echo "[3/7] Atualizando dependencias..."
VENV_PIP="venv/bin/pip"
[ ! -f "$VENV_PIP" ] && VENV_PIP="venv_new/bin/pip"
VENV_PYTHON="$(dirname "$VENV_PIP")/python"
[ ! -x "$VENV_PYTHON" ] && {
    echo "  > ERRO: Python do ambiente virtual não encontrado em $VENV_PYTHON"
    exit 1
}

# Pastas ~pacote em site-packages = uninstall do pip interrompido (ex.: ~vidia-cusparselt-cu13)
cleanup_pip_orphans() {
    local venv_pip="$1"
    local venv_dir sp orphan removed=0
    venv_dir="$(dirname "$(dirname "$venv_pip")")"

    for sp in "$venv_dir"/lib/python*/site-packages; do
        [ -d "$sp" ] || continue
        for orphan in "$sp"/~*; do
            [ -e "$orphan" ] || continue
            echo "  > Removendo distribuicao pip invalida: $(basename "$orphan")"
            rm -rf "$orphan"
            removed=$((removed + 1))
        done
    done

    if [ "$removed" -gt 0 ]; then
        echo "  > $removed pasta(s) orfa(s) do pip removida(s)"
    fi
}

cleanup_pip_orphans "$VENV_PIP"
VENV_NAME="$(basename "$(dirname "$VENV_PIP")")"
REQUIREMENTS_STATE_FILE="${REQUIREMENTS_STATE_FILE:-logs/.requirements-${VENV_NAME}.sha256}"
if command -v sha256sum >/dev/null 2>&1; then
    REQUIREMENTS_HASH="$(sha256sum requirements.txt | awk '{print $1}')"
else
    REQUIREMENTS_HASH="$(shasum -a 256 requirements.txt | awk '{print $1}')"
fi
if [ ! -f "$REQUIREMENTS_STATE_FILE" ] || [ "$(cat "$REQUIREMENTS_STATE_FILE")" != "$REQUIREMENTS_HASH" ]; then
    echo "  > requirements.txt mudou; atualizando ambiente Python..."
    "$VENV_PIP" install --upgrade pip --quiet 2>&1
    cleanup_pip_orphans "$VENV_PIP"
    "$VENV_PIP" install -r requirements.txt --upgrade --quiet 2>&1
    cleanup_pip_orphans "$VENV_PIP"
    printf '%s\n' "$REQUIREMENTS_HASH" > "$REQUIREMENTS_STATE_FILE"
else
    echo "  > requirements.txt sem alteracoes; pulando instalacao Python."
fi
echo "  > OK"

# 4. Criar diretorios e dependencias do sistema
mkdir -p aicentralv2/static/uploads/audiencias aicentralv2/static/uploads/cotacoes \
    aicentralv2/static/media/whatsapp/outbound logs
chmod 755 aicentralv2/static/uploads/audiencias aicentralv2/static/uploads/cotacoes \
    aicentralv2/static/media/whatsapp aicentralv2/static/media/whatsapp/outbound logs

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo ""
    echo "  > ffmpeg nao encontrado — instalando (necessario para audio WhatsApp)..."
    sudo apt-get update -qq && sudo apt-get install -y ffmpeg >/dev/null 2>&1 || \
        echo "  > AVISO: instale ffmpeg manualmente (sudo apt install ffmpeg)"
fi

# 5. Limpar cache Python
echo ""
echo "[4/7] Limpando cache..."
if [ "${CLEAN_PYTHON_CACHE:-0}" = "1" ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
else
    echo "  > Cache preservado (use CLEAN_PYTHON_CACHE=1 para limpar manualmente)."
fi
echo "  > OK"

# 6. Recarregar systemd (o unit principal e gerenciado no servidor)
echo ""
echo "[5/8] Recarregando systemd..."
sudo systemctl daemon-reload
echo "  > OK"

# 7. Nginx — limite de upload (413)
echo ""
echo "[6/8] Configurando nginx (client_max_body_size 256M)..."
bash deploy/configure_nginx_upload.sh >> "$DEPLOY_LOG" 2>&1
echo "  > OK"

# 8. Atualizar schema e dados idempotentes
echo ""
echo "[7/9] Atualizando schemas e dados..."
MIGRATION_STATE_FILE="${MIGRATION_STATE_FILE:-logs/.last-migrations-revision}"
MIGRATION_REVISION="$(git rev-parse HEAD)"
RUN_MIGRATIONS=1
if [ "${FORCE_MIGRATIONS:-0}" != "1" ] && [ -s "$MIGRATION_STATE_FILE" ]; then
    LAST_MIGRATION_REVISION="$(head -n 1 "$MIGRATION_STATE_FILE")"
    if git cat-file -e "${LAST_MIGRATION_REVISION}^{commit}" 2>/dev/null && \
       git diff --quiet "$LAST_MIGRATION_REVISION" "$MIGRATION_REVISION" -- \
           migrations deploy.sh scripts/seed_creative_formats.py \
           scripts/seed_creative_viewer_profiles.py scripts/import_centralcomm_interactives.py; then
        RUN_MIGRATIONS=0
    fi
fi

if [ "$RUN_MIGRATIONS" = "1" ]; then
{
"$VENV_PYTHON" migrations/run_add_tipo_comercial_to_cotacoes.py
"$VENV_PYTHON" migrations/run_add_cotacao_grupo_plano.py
"$VENV_PYTHON" migrations/run_add_cotacao_itens_especificos.py
"$VENV_PYTHON" migrations/run_fix_cx_clients_crm_index.py
"$VENV_PYTHON" migrations/run_create_creative_modeling.py
"$VENV_PYTHON" migrations/run_add_creative_campaign_flow.py
"$VENV_PYTHON" migrations/run_add_creative_house_client.py
"$VENV_PYTHON" migrations/run_add_creative_scene_productions.py
"$VENV_PYTHON" migrations/run_add_creative_client_intelligence.py
"$VENV_PYTHON" migrations/run_add_creative_client_brand_assets.py
"$VENV_PYTHON" migrations/run_add_creative_brand_lineage.py
"$VENV_PYTHON" migrations/run_add_workspace_brand_audit_history.py
"$VENV_PYTHON" migrations/run_add_workspace_brand_audit_jobs.py
"$VENV_PYTHON" migrations/run_add_workspace_brand_audit_evidence.py
"$VENV_PYTHON" migrations/run_add_workspace_brand_audit_versioning.py
"$VENV_PYTHON" migrations/run_add_workspace_brand_field_reliability.py
"$VENV_PYTHON" migrations/run_add_creative_format_studio.py
"$VENV_PYTHON" migrations/run_add_studio_sessions.py
"$VENV_PYTHON" migrations/run_add_cadu_studio_creation_history.py
"$VENV_PYTHON" migrations/run_add_creative_compose_library.py
"$VENV_PYTHON" migrations/run_add_creative_plate_kits.py
"$VENV_PYTHON" migrations/run_add_creative_concept_lab.py
"$VENV_PYTHON" scripts/seed_creative_formats.py
"$VENV_PYTHON" migrations/run_seed_creative_format_layouts.py
"$VENV_PYTHON" migrations/run_add_creative_viewer_profiles.py
"$VENV_PYTHON" scripts/seed_creative_viewer_profiles.py
"$VENV_PYTHON" migrations/run_add_creative_storyboards_and_catalogs.py
"$VENV_PYTHON" migrations/run_add_design_system_ads.py
"$VENV_PYTHON" migrations/run_add_design_system_ads_revision.py
"$VENV_PYTHON" migrations/run_convert_interactive_formats_to_image_carousels.py
"$VENV_PYTHON" migrations/run_add_google_calendar_meet.py
"$VENV_PYTHON" migrations/run_add_system_integration_credentials.py
"$VENV_PYTHON" migrations/run_sql_migration.py add_google_workspace_connections.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_google_workspace_sync_state.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_google_workspace_meet_artifacts.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_google_workspace_client_authorizations.sql
"$VENV_PYTHON" migrations/run_sql_migration.py drop_google_workspace_organization_id.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_slack_connector.sql
"$VENV_PYTHON" migrations/run_add_openrouter_integration_credential.py
"$VENV_PYTHON" migrations/run_add_openrouter_gpt_image_2.py
"$VENV_PYTHON" migrations/run_add_openai_integration_credential.py
"$VENV_PYTHON" migrations/run_add_firecrawl_integration_credential.py
"$VENV_PYTHON" migrations/run_add_dify_integration_credential.py
"$VENV_PYTHON" migrations/run_add_brevo_integration_credential.py
"$VENV_PYTHON" migrations/run_add_cx_place_documents.py
"$VENV_PYTHON" migrations/run_add_d4sign_assinaturas.py
"$VENV_PYTHON" migrations/run_add_google_login_credentials.py
# Run after the legacy provider migrations because some of them replace the
# integration CHECK constraint with an older provider list.
"$VENV_PYTHON" migrations/run_sql_migration.py add_typesafe_integration_credential.sql
"$VENV_PYTHON" migrations/run_add_cadu_sso_tickets.py
"$VENV_PYTHON" migrations/run_add_cadu_knowledge_documents.py
"$VENV_PYTHON" migrations/run_add_cadu_skills_marketplace.py
"$VENV_PYTHON" migrations/run_add_cadu_skills_management.py
"$VENV_PYTHON" migrations/run_add_cadu_agent_campaign_projects.py
"$VENV_PYTHON" migrations/run_add_cadu_project_custom_fields.py
"$VENV_PYTHON" migrations/run_add_cadu_chat_runtime.py
"$VENV_PYTHON" migrations/run_add_cadu_conversations_v2.py
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_agent_runtime_observability.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_mcp_operations.sql
"$VENV_PYTHON" migrations/run_add_cadu_mcp_contexts.py
"$VENV_PYTHON" migrations/run_add_cadu_user_memory.py
"$VENV_PYTHON" migrations/run_add_cadu_working_memory.py
"$VENV_PYTHON" migrations/run_sql_migration.py fix_cadu_work_memory_assistant_provenance.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_conversation_memory.sql
"$VENV_PYTHON" migrations/run_add_cadu_tool_token_ledger.py
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_credit_requests.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_credit_request_lot.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_plan_storage.sql
"$VENV_PYTHON" migrations/run_upgrade_cadu_tool_token_ledger_compat.py
# Avatar badge is an optional rollout. Do not make a partial checkout fail
# deployment before its migration runner is versioned with the feature.
if [ -f "migrations/run_add_cadu_avatar_badge.py" ]; then
    "$VENV_PYTHON" migrations/run_add_cadu_avatar_badge.py
fi
"$VENV_PYTHON" migrations/run_rename_percentual_to_fee_cliente.py
"$VENV_PYTHON" migrations/run_add_format_variant_revisions.py
"$VENV_PYTHON" migrations/run_sql_migration.py add_training_studio_import_palco.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_workspace_projects.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_workspace_project_links.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_project_file_classification.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_project_resource_registry.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_workspace_ingestion_and_dock.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_project_link_icon_metadata.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_resource_state.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_public_mcp.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_public_mcp_scopes.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_chat_plugin_catalog.sql
"$VENV_PYTHON" migrations/run_sql_migration.py activate_cadu_google_chat_plugins.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_daily_workflow_plugins.sql
"$VENV_PYTHON" migrations/run_sql_migration.py refine_cadu_daily_workflow_plugins.sql
"$VENV_PYTHON" migrations/run_sql_migration.py activate_cadu_daily_workflow_plugins.sql
"$VENV_PYTHON" migrations/run_add_cadu_public_mcp_oauth.py
"$VENV_PYTHON" migrations/run_add_cadu_public_mcp_modules.py
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_workspace_home_preferences.sql
# Planner: a tabela de planos é a base das migrações de documentos,
# alocações, revisões e compartilhamento. Aplique a cadeia completa nesta
# ordem para instalações novas e para servidores que ainda não receberam o
# primeiro rollout do produto.
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_planner_plans.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_planner_channel_allocations.sql
"$VENV_PYTHON" migrations/run_add_cadu_planner_client_flow.py
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_planner_review_history.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_planner_docs_compat.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_planner_link_test_runs.sql
"$VENV_PYTHON" migrations/run_add_connect_report_workspace.py
"$VENV_PYTHON" migrations/run_add_connect_report_sources.py
"$VENV_PYTHON" migrations/run_add_connect_report_imports.py
"$VENV_PYTHON" migrations/run_add_connect_report_reviews.py
"$VENV_PYTHON" migrations/run_add_connect_report_ai_runs.py
"$VENV_PYTHON" migrations/run_add_connect_report_public_links.py
"$VENV_PYTHON" migrations/run_sql_migration.py add_reports_operations_v1.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_planner_public_shares.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_interactive_creative_categories.sql
"$VENV_PYTHON" migrations/run_sql_migration.py add_cadu_user_onboardings.sql
} >> "$DEPLOY_LOG" 2>&1
    mkdir -p "$(dirname "$MIGRATION_STATE_FILE")"
    printf '%s\n' "$MIGRATION_REVISION" > "${MIGRATION_STATE_FILE}.tmp"
    mv "${MIGRATION_STATE_FILE}.tmp" "$MIGRATION_STATE_FILE"
    echo "  > OK (migrações executadas para $MIGRATION_REVISION)"
else
    echo "  > Nenhuma migração alterada desde $LAST_MIGRATION_REVISION; pulando bloco de migrações."
fi

# O catálogo pode ser montado fora do Git em qualquer momento. Mantemos esta
# importação independente do marcador de migrations para não ignorar um novo
# catálogo depois de um deploy que não alterou o schema.
INTERACTIVES_SOURCE="${CENTRALCOMM_INTERACTIVES_SOURCE:-/var/www/aicentralv2/data/html-slides-pt}"
if [ -f "$INTERACTIVES_SOURCE/creative-format-overview.html" ]; then
    "$VENV_PYTHON" scripts/import_centralcomm_interactives.py --source "$INTERACTIVES_SOURCE" >> "$DEPLOY_LOG" 2>&1
else
    echo "Catálogo CentralComm ausente; importação de interativos ignorada: $INTERACTIVES_SOURCE" >> "$DEPLOY_LOG"
fi

# Worker de mídia: dependências, modelo local e serviço supervisionado.
MEDIA_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_media_worker.sh >> "$DEPLOY_LOG" 2>&1
ONBOARDING_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_onboarding_followup_timer.sh >> "$DEPLOY_LOG" 2>&1
LINK_ICON_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_link_icon_worker.sh >> "$DEPLOY_LOG" 2>&1
# These consumers depend on the migrations above. Keep their installation in
# the normal Git deploy so new queue entries cannot accumulate unnoticed.
RESOURCE_REGISTRY_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_resource_registry_worker.sh >> "$DEPLOY_LOG" 2>&1
CONVERSATION_MEMORY_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_conversation_memory_worker.sh >> "$DEPLOY_LOG" 2>&1

# 9. Iniciar servico
echo ""
echo "[8/9] Iniciando servico..."
sudo systemctl start "$APP_SERVICE"
sleep 3

if sudo systemctl is-active --quiet "$APP_SERVICE"; then
    SERVICE_STOPPED=0
    trap - ERR
    echo "  > Servico ativo!"
else
    echo "  > ERRO ao iniciar servico"
    echo ""
    echo "=== Ultimas linhas de logs/error.log ==="
    tail -n 60 logs/error.log 2>/dev/null || echo "  (sem error.log)"
    echo ""
    echo "=== Teste manual de import ==="
    venv/bin/python -c "from run import app; print('import OK')" 2>&1 || true
    echo ""
    sudo journalctl -u "$APP_SERVICE" -n 30 --no-pager 2>&1 | cat
    exit 1
fi

echo "  > Validando APIs de formatos e visualizadores..."
"$VENV_PYTHON" scripts/verify_creative_viewer_apis.py >> "$DEPLOY_LOG" 2>&1

# 10. Health check
echo ""
echo "[9/9] Health check..."
sleep 2
HTTP_CODE=$(curl -s -m 10 -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "000" ]; then
    echo "  > Servidor nao respondeu (pode precisar de login)"
elif [ "$HTTP_CODE" -lt "400" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "302" ]; then
    echo "  > OK (HTTP $HTTP_CODE)"
else
    echo "  > Retornou HTTP $HTTP_CODE"
fi

echo ""
echo "========================================"
echo "  Deploy concluido com sucesso!"
echo "========================================"
echo ""

# Restaurar terminal
stty sane 2>/dev/null || true
