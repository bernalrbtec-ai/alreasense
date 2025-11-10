#!/usr/bin/env bash
set -euo pipefail

log_info() {
  printf '%s %s\n' "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")]" "$1"
}

log_info "Iniciando rotinas de preparação do backend"

python fix_tenant_migration.py
python manage.py fix_evolution_table
python fix_complete_database.py
python manage.py migrate
python create_superuser.py
python ensure_plan_table.py
python seed_plans.py
python check_user_permissions.py

log_info "Inicializando consumer Redis do chat"
python manage.py start_chat_consumer &
CHAT_CONSUMER_PID=$!

terminate_processes() {
  log_info "Encerrando processos"
  if ps -p "${CHAT_CONSUMER_PID}" >/dev/null 2>&1; then
    kill -TERM "${CHAT_CONSUMER_PID}" >/dev/null 2>&1 || true
    wait "${CHAT_CONSUMER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${DAPHNE_PID:-}" ]] && ps -p "${DAPHNE_PID}" >/dev/null 2>&1; then
    kill -TERM "${DAPHNE_PID}" >/dev/null 2>&1 || true
    wait "${DAPHNE_PID}" >/dev/null 2>&1 || true
  fi
}

trap terminate_processes SIGINT SIGTERM

log_info "Subindo servidor ASGI com daphne"
daphne -b 0.0.0.0 -p 8000 alrea_sense.asgi:application &
DAPHNE_PID=$!

wait "${DAPHNE_PID}"
EXIT_CODE=$?

terminate_processes

exit "${EXIT_CODE}"

