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

# Decide se um passo precisa rodar: sempre na primeira vez, com FORCE=1 ou quando
# algum caminho listado mudou desde a revisão gravada em STATE_FILE.
#   should_run STATE_FILE FORCE caminho...
should_run() {
    local state_file="$1" force="$2" last
    shift 2
    [ "$force" = "1" ] && return 0
    [ -s "$state_file" ] || return 0
    last="$(head -n 1 "$state_file")"
    git cat-file -e "${last}^{commit}" 2>/dev/null || return 0
    git diff --quiet "$last" "$(git rev-parse HEAD)" -- "$@" || return 0
    return 1
}

# Grava a revisão atual como a última em que o passo rodou com sucesso.
record_state() {
    mkdir -p "$(dirname "$1")"
    printf '%s\n' "$(git rev-parse HEAD)" > "${1}.tmp"
    mv "${1}.tmp" "$1"
}

echo ""
echo "========================================"
echo "  Deploy AIcentral v2"
echo "========================================"
echo "  Log detalhado: $DEPLOY_LOG"
echo ""

# Parada do serviço (chamada mais abaixo) (a parada acontece em stop_service_for_deploy)
# Parar o serviço só depois de código, build e dependências estarem prontos:
# o site continua no ar durante a parte lenta do deploy.
stop_service_for_deploy() {
    [ "$SERVICE_STOPPED" = "1" ] && return 0
    echo ""
    echo "[parada] Parando servico (codigo, build e dependencias prontos)..."
    sudo systemctl stop "$APP_SERVICE" 2>/dev/null || true
    SERVICE_STOPPED=1
    SERVICE_STOPPED_AT=$SECONDS
    sleep 2

    # Garantir que nenhum worker órfão ficou vivo. O stop explícito acima evita que
    # o Restart=always do systemd recrie o processo durante esta limpeza.
    # O [g] impede que o padrão case com a própria linha de comando do sudo/pkill
    # (antes o sudo era morto junto e deixava o terminal desalinhado).
    sudo pkill -9 -f "[g]unicorn.*run:app" 2>/dev/null || true
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
}

# Build do frontend. Não depende do Python, então roda antes da parada do serviço
# quando o requirements.txt muda (ver passo 2); no passo 4 ele só repete se faltou.
frontend_build_step() {
    FRONTEND_STATE_FILE="${FRONTEND_STATE_FILE:-logs/.last-frontend-build-revision}"
    if should_run "$FRONTEND_STATE_FILE" "${FORCE_FRONTEND_BUILD:-0}" \
           frontend aicentralv2/templates aicentralv2/static/cadu_workspace \
           aicentralv2/static/cadu_studio aicentralv2/static/css package.json \
           package-lock.json build_frontend.sh postcss.config.js \
           tailwind.config.js tailwind.artifact.config.js \
           tailwind.conversations.config.js tailwind.studio.config.js \
           vite.auth.config.mjs vite.conversations.config.mjs \
           vite.reports.config.mjs vite.planner.config.mjs \
           vite.studio-editor.config.mjs vite.studio-audio.config.mjs vite.studio-ui.config.mjs \
       || [ ! -f "aicentralv2/static/css/tailwind/output.css" ]; then
        if [ -x "./build_frontend_fast.sh" ]; then
            FRONTEND_BUILD_SCRIPT="./build_frontend_fast.sh"
        elif [ -x "./build_frontend.sh" ]; then
            FRONTEND_BUILD_SCRIPT="./build_frontend.sh"
        else
            echo "  > ERRO: build frontend indisponivel — output.css nao sera gerado"
            exit 1
        fi
        # A saída completa (Tailwind, Vite, npm) vai só para o log; na tela fica um
        # ponto por etapa concluída, para o deploy não parecer travado.
        echo "  > Compilando com $FRONTEND_BUILD_SCRIPT (pode levar alguns minutos)..."
        FRONTEND_STARTED=$SECONDS
        bash "$FRONTEND_BUILD_SCRIPT" >> "$DEPLOY_LOG" 2>&1 &
        FRONTEND_PID=$!
        while kill -0 "$FRONTEND_PID" 2>/dev/null; do
            printf '.'
            sleep 2
        done
        echo ""
        if ! wait "$FRONTEND_PID"; then
            echo "  > ERRO no build do frontend — últimas linhas do log:"
            tail -n 40 "$DEPLOY_LOG" 2>/dev/null || true
            exit 1
        fi
        echo "  > Build concluído em $((SECONDS - FRONTEND_STARTED))s"
        record_state "$FRONTEND_STATE_FILE"
        echo "  > OK (frontend compilado para $(git rev-parse HEAD))"
    else
        echo "  > Frontend sem alteracoes (ou ja compilado nesta revisao); pulando build."
    fi
}

# 1. Atualizar codigo
echo ""
echo "[1/9] Atualizando codigo..."
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
    backup_name="${generated_file//\//__}"
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

# Gerados por build: os versionados que o .gitignore também cobre vêm do Git, então
# um bundle novo ignorado não exige editar este script. Os versionados e não
# ignorados (committed bundles) ficam nesta lista curta.
VERSIONED_BUILD_OUTPUTS=(
    "aicentralv2/static/cadu_planner/react/app.css"
    "aicentralv2/static/cadu_planner/react/app.js"
    "aicentralv2/static/cadu_studio/ui/navbar.css"
    "aicentralv2/static/cadu_studio/ui/navbar.js"
)
while IFS= read -r generated_file; do
    restore_generated_file "$generated_file"
done < <({ git ls-files -ci --exclude-standard -- aicentralv2/static; printf '%s\n' "${VERSIONED_BUILD_OUTPUTS[@]}"; } | sort -u)
git pull origin main >> "$DEPLOY_LOG" 2>&1
# Renormalizar line endings apos pull
git checkout -- . 2>/dev/null || true
echo "  > OK"

# Ordem: código → dependências → schema → build → parada curta → workers → início.
# O schema vem antes do build: um worker do gunicorn reciclado durante o build já
# carrega o código novo e encontra as colunas novas, e o serviço só cai no fim.
# 2. Atualizar dependencias
echo ""
echo "[2/9] Atualizando dependencias..."
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
    # Compila o frontend com o site ainda no ar: a parada só cobre pip e migrações.
    echo "  > Compilando o frontend antes de parar o servico..."
    frontend_build_step
    # Bibliotecas não podem ser trocadas sob workers em execução.
    stop_service_for_deploy
    "$VENV_PIP" install --upgrade pip --quiet 2>&1
    cleanup_pip_orphans "$VENV_PIP"
    "$VENV_PIP" install -r requirements.txt --upgrade --quiet 2>&1
    cleanup_pip_orphans "$VENV_PIP"
    printf '%s\n' "$REQUIREMENTS_HASH" > "$REQUIREMENTS_STATE_FILE"
else
    echo "  > requirements.txt sem alteracoes; pulando instalacao Python."
fi
echo "  > OK"

# 3. Atualizar schema e dados idempotentes
echo ""
echo "[3/9] Atualizando schemas e dados..."
MIGRATION_STATE_FILE="${MIGRATION_STATE_FILE:-logs/.last-migrations-revision}"
if should_run "$MIGRATION_STATE_FILE" "${FORCE_MIGRATIONS:-0}" \
       migrations deploy.sh scripts/seed_creative_formats.py \
       scripts/seed_creative_viewer_profiles.py scripts/import_centralcomm_interactives.py; then
    echo "  > Migrações em andamento (detalhes em $DEPLOY_LOG)..."
    # A lista e a ordem dos passos ficam em migrations/ORDER.txt.
    if ! "$VENV_PYTHON" migrations/run_deploy_migrations.py >> "$DEPLOY_LOG" 2>&1; then
        echo ""
        echo "  > ERRO no bloco de migrações — últimas linhas do log:"
        tail -n 40 "$DEPLOY_LOG" 2>/dev/null || true
        if [ "$SERVICE_STOPPED" = "1" ]; then
            echo "  > Tentando subir $APP_SERVICE após falha..."
            sudo systemctl start "$APP_SERVICE" 2>/dev/null || true
            SERVICE_STOPPED=0
        fi
        exit 1
    fi
    record_state "$MIGRATION_STATE_FILE"
    echo "  > OK (migrações executadas para $(git rev-parse HEAD))"
else
    echo "  > Nenhuma migração alterada desde a última execução; pulando bloco de migrações."
fi

# 4. Build frontend (artefatos gerados somente quando a camada visual mudou)
echo ""
echo "[4/9] Build frontend (Tailwind)..."
frontend_build_step

stop_service_for_deploy

# Diretorios e dependencias do sistema
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
echo "[5/9] Limpando cache..."
if [ "${CLEAN_PYTHON_CACHE:-0}" = "1" ]; then
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
else
    echo "  > Cache preservado (use CLEAN_PYTHON_CACHE=1 para limpar manualmente)."
fi
echo "  > OK"

# 6. Recarregar systemd (o unit principal e gerenciado no servidor)
echo ""
echo "[6/9] Recarregando systemd..."
sudo systemctl daemon-reload
echo "  > OK"

# 7. Nginx — limite de upload (413)
echo ""
echo "[7/9] Configurando nginx (client_max_body_size 256M)..."
bash deploy/configure_nginx_upload.sh >> "$DEPLOY_LOG" 2>&1
echo "  > OK"

# O catálogo pode ser montado fora do Git em qualquer momento. Mantemos esta
# importação independente do marcador de migrations para não ignorar um novo
# catálogo depois de um deploy que não alterou o schema.
INTERACTIVES_SOURCE="${CENTRALCOMM_INTERACTIVES_SOURCE:-/var/www/aicentralv2/data/html-slides-pt}"
if [ -f "$INTERACTIVES_SOURCE/creative-format-overview.html" ]; then
    "$VENV_PYTHON" scripts/import_centralcomm_interactives.py --source "$INTERACTIVES_SOURCE" >> "$DEPLOY_LOG" 2>&1
else
    echo "Catálogo CentralComm ausente; importação de interativos ignorada: $INTERACTIVES_SOURCE" >> "$DEPLOY_LOG"
fi

# Workers: instaladores só rodam quando deploy/ ou as dependências de mídia
# mudaram. O worker de mídia executa código da aplicação, então é reiniciado
# em todo deploy para não ficar com a versão anterior.
WORKERS_STATE_FILE="${WORKERS_STATE_FILE:-logs/.last-workers-revision}"
if should_run "$WORKERS_STATE_FILE" "${FORCE_WORKERS:-0}" deploy requirements.txt requirements-media.txt; then
    MEDIA_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_media_worker.sh >> "$DEPLOY_LOG" 2>&1
    ONBOARDING_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_onboarding_followup_timer.sh >> "$DEPLOY_LOG" 2>&1
    LINK_ICON_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_link_icon_worker.sh >> "$DEPLOY_LOG" 2>&1
    # These consumers depend on the migrations above. Keep their installation in
    # the normal Git deploy so new queue entries cannot accumulate unnoticed.
    RESOURCE_REGISTRY_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_resource_registry_worker.sh >> "$DEPLOY_LOG" 2>&1
    CONVERSATION_MEMORY_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_conversation_memory_worker.sh >> "$DEPLOY_LOG" 2>&1
    # Verificação diária de ads.txt dos portais do Planner (depende da migração add_cadu_planner_portal_programmatic).
    PLANNER_MONITOR_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_planner_portal_ads_timer.sh >> "$DEPLOY_LOG" 2>&1
    # Radares ativos do Planner: o comando só age com CADU_RADAR_ENABLED e a migração add_cadu_radar_v2 aplicada.
    RADAR_WATCH_PYTHON="$(pwd)/$VENV_PYTHON" bash deploy/install_radar_watch_timer.sh >> "$DEPLOY_LOG" 2>&1
    record_state "$WORKERS_STATE_FILE"
else
    echo "  > Workers sem alteracoes; reiniciando apenas o worker de midia."
    sudo systemctl restart cadu-media-worker >> "$DEPLOY_LOG" 2>&1
fi

# 8. Iniciar servico
echo ""
echo "[8/9] Iniciando servico..."
sudo systemctl start "$APP_SERVICE"
sleep 3

if sudo systemctl is-active --quiet "$APP_SERVICE"; then
    SERVICE_STOPPED=0
    trap - ERR
    echo "  > Servico ativo! (fora do ar por $((SECONDS - SERVICE_STOPPED_AT))s)"
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

# 9. Health check
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
