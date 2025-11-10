#!/usr/bin/env bash
set -euo pipefail

log_info() {
  printf '%s %s\n' "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")]" "$1"
}

export CHAT_DISABLE_ASGI_CONSUMERS=1

log_info "Iniciando rotinas de preparação do backend"

python fix_tenant_migration.py
python manage.py fix_evolution_table
python fix_complete_database.py
python manage.py migrate
python create_superuser.py
python ensure_plan_table.py
python seed_plans.py
python check_user_permissions.py

log_info "Inicializando consumer Redis crítico (send_message, mark_as_read)"
python manage.py start_chat_consumer --queues send_message mark_as_read &
CHAT_CONSUMER_CRITICAL_PID=$!

log_info "Inicializando consumer Redis de I/O (fetch_profile_pic, fetch_group_info)"
python manage.py start_chat_consumer --queues fetch_profile_pic fetch_group_info &
CHAT_CONSUMER_IO_PID=$!

terminate_processes() {
  log_info "Encerrando processos"
  if ps -p "${CHAT_CONSUMER_CRITICAL_PID}" >/dev/null 2>&1; then
    kill -TERM "${CHAT_CONSUMER_CRITICAL_PID}" >/dev/null 2>&1 || true
    wait "${CHAT_CONSUMER_CRITICAL_PID}" >/dev/null 2>&1 || true
  fi
  if ps -p "${CHAT_CONSUMER_IO_PID}" >/dev/null 2>&1; then
    kill -TERM "${CHAT_CONSUMER_IO_PID}" >/dev/null 2>&1 || true
    wait "${CHAT_CONSUMER_IO_PID}" >/dev/null 2>&1 || true
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

