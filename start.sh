#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# PandaProbe — Self-host management script
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE_FILE="docker-compose.yml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Colors & formatting ──────────────────────────────────────────────────────

BOLD='\033[1m'
DIM='\033[2m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
RESET='\033[0m'

banner() {
  echo ""
  echo -e "${BOLD}${CYAN}"
  echo "  ╔═══════════════════════════════════════╗"
  echo "  ║          🐼  PandaProbe               ║"
  echo "  ║     Agent Engineering Platform        ║"
  echo "  ╚═══════════════════════════════════════╝"
  echo -e "${RESET}"
}

info()    { echo -e "  ${CYAN}▸${RESET} $1"; }
success() { echo -e "  ${GREEN}✓${RESET} $1"; }
warn()    { echo -e "  ${YELLOW}!${RESET} $1"; }
error()   { echo -e "  ${RED}✗${RESET} $1"; }

# ── Pre-flight checks ────────────────────────────────────────────────────────

check_docker() {
  if ! command -v docker &> /dev/null; then
    error "Docker is not installed. Please install Docker first:"
    echo "       https://docs.docker.com/get-docker/"
    exit 1
  fi

  if ! docker info &> /dev/null; then
    error "Docker daemon is not running. Please start Docker and try again."
    exit 1
  fi
}

# ── Environment setup ────────────────────────────────────────────────────────

setup_env() {
  local changed=false

  if [ ! -f backend/.env.development ]; then
    cp backend/.env.example backend/.env.development
    success "Created ${BOLD}backend/.env.development${RESET} from template"
    changed=true
  fi

  if [ ! -f frontend/.env.development ]; then
    cp frontend/.env.example frontend/.env.development
    success "Created ${BOLD}frontend/.env.development${RESET} from template"
    changed=true
  fi

  if [ "$changed" = true ]; then
    echo ""
    info "Default config is ready to go (auth disabled, localhost API)."
    info "Edit the .env.development files to add LLM keys or enable auth."
    echo ""
  fi
}

# ── Service health reporting ──────────────────────────────────────────────────

SERVICES=(postgres redis app worker beat frontend)

print_service_status() {
  echo ""
  echo -e "  ${BOLD}Services${RESET}"
  echo -e "  ${DIM}─────────────────────────────────────────${RESET}"

  local all_ok=true
  for svc in "${SERVICES[@]}"; do
    local state
    state=$(docker compose -f "$COMPOSE_FILE" ps --format '{{.State}}' "$svc" 2>/dev/null || echo "missing")

    local health=""
    health=$(docker compose -f "$COMPOSE_FILE" ps --format '{{.Health}}' "$svc" 2>/dev/null || echo "")

    local label
    case "$svc" in
      postgres) label="PostgreSQL" ;;
      redis)    label="Redis" ;;
      app)      label="Backend API" ;;
      worker)   label="Celery Worker" ;;
      beat)     label="Celery Beat" ;;
      frontend) label="Dashboard" ;;
      *)        label="$svc" ;;
    esac

    if [ "$state" = "running" ]; then
      if [ "$health" = "healthy" ]; then
        echo -e "    ${GREEN}●${RESET}  ${label}"
      elif [ "$health" = "starting" ]; then
        echo -e "    ${YELLOW}●${RESET}  ${label}  ${DIM}(starting …)${RESET}"
      else
        echo -e "    ${GREEN}●${RESET}  ${label}"
      fi
    else
      echo -e "    ${RED}●${RESET}  ${label}  ${DIM}(${state:-not running})${RESET}"
      all_ok=false
    fi
  done

  echo ""

  if [ "$all_ok" = false ]; then
    warn "Some services are not running. Check logs with: ${CYAN}./start.sh logs${RESET}"
    echo ""
  fi
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_up() {
  banner
  check_docker
  setup_env

  info "Pulling latest images …"
  docker compose -f "$COMPOSE_FILE" pull

  info "Starting all services …"
  docker compose -f "$COMPOSE_FILE" up -d

  info "Waiting for services to become healthy …"
  sleep 3

  print_service_status

  echo -e "  ${BOLD}Dashboard${RESET}       http://localhost:3000"
  echo -e "  ${BOLD}API reference${RESET}   http://localhost:8000/scalar"
  echo -e "  ${BOLD}API health${RESET}      http://localhost:8000/health"
  echo ""
  echo -e "  ${DIM}Useful commands:${RESET}"
  echo -e "    ${CYAN}./start.sh status${RESET}    Show service health"
  echo -e "    ${CYAN}./start.sh logs${RESET}      Tail all service logs"
  echo -e "    ${CYAN}./start.sh restart${RESET}   Restart all services"
  echo -e "    ${CYAN}./start.sh stop${RESET}      Stop all services"
  echo ""
}

cmd_stop() {
  banner
  info "Stopping all services …"
  docker compose -f "$COMPOSE_FILE" down
  success "All services stopped."
  echo ""
}

cmd_restart() {
  banner
  info "Restarting all services …"
  docker compose -f "$COMPOSE_FILE" restart

  info "Waiting for services to become healthy …"
  sleep 3

  print_service_status

  echo -e "  ${BOLD}Dashboard${RESET}       http://localhost:3000"
  echo -e "  ${BOLD}API reference${RESET}   http://localhost:8000/scalar"
  echo ""
}

cmd_status() {
  banner
  print_service_status
}

cmd_logs() {
  local service="${1:-}"
  if [ -n "$service" ]; then
    docker compose -f "$COMPOSE_FILE" logs -f "$service"
  else
    docker compose -f "$COMPOSE_FILE" logs -f
  fi
}

cmd_upgrade() {
  banner
  info "Pulling latest images …"
  docker compose -f "$COMPOSE_FILE" pull

  info "Recreating containers with new images …"
  docker compose -f "$COMPOSE_FILE" up -d --remove-orphans

  info "Waiting for services to become healthy …"
  sleep 3

  print_service_status

  success "Upgrade complete!"
  echo ""
  echo -e "  ${BOLD}Dashboard${RESET}       http://localhost:3000"
  echo -e "  ${BOLD}API reference${RESET}   http://localhost:8000/scalar"
  echo ""
}

cmd_reset() {
  banner
  warn "This will stop all services and ${BOLD}delete all data${RESET} (database, Redis)."
  echo ""
  read -rp "  Are you sure? (y/N) " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    info "Stopping services and removing volumes …"
    docker compose -f "$COMPOSE_FILE" down -v
    success "All services stopped and data removed."
  else
    info "Cancelled."
  fi
  echo ""
}

cmd_help() {
  banner
  echo -e "  ${BOLD}Usage:${RESET}  ./start.sh <command>"
  echo ""
  echo -e "  ${BOLD}Commands:${RESET}"
  echo ""
  echo -e "    ${CYAN}up${RESET}              Start all services (pulls images on first run)"
  echo -e "    ${CYAN}stop${RESET}            Stop all services"
  echo -e "    ${CYAN}restart${RESET}         Restart all services"
  echo -e "    ${CYAN}status${RESET}          Show running containers and their health"
  echo -e "    ${CYAN}logs${RESET} [service]  Tail logs (all services, or specify one)"
  echo -e "    ${CYAN}upgrade${RESET}         Pull latest images and restart"
  echo -e "    ${CYAN}reset${RESET}           Stop services and ${RED}delete all data${RESET}"
  echo -e "    ${CYAN}help${RESET}            Show this help message"
  echo ""
  echo -e "  ${BOLD}Services:${RESET}"
  echo -e "    ${DIM}postgres${RESET}    PostgreSQL 16 database          ${DIM}:5432${RESET}"
  echo -e "    ${DIM}redis${RESET}       Redis 7 (broker + cache)        ${DIM}:6379${RESET}"
  echo -e "    ${DIM}app${RESET}         FastAPI backend server          ${DIM}:8000${RESET}"
  echo -e "    ${DIM}worker${RESET}      Celery background worker"
  echo -e "    ${DIM}beat${RESET}        Celery Beat scheduler"
  echo -e "    ${DIM}frontend${RESET}    Next.js dashboard               ${DIM}:3000${RESET}"
  echo ""
  echo -e "  ${BOLD}Examples:${RESET}"
  echo -e "    ${DIM}./start.sh up${RESET}              # First-time setup + start"
  echo -e "    ${DIM}./start.sh logs app${RESET}        # Tail only backend logs"
  echo -e "    ${DIM}./start.sh logs frontend${RESET}   # Tail only frontend logs"
  echo -e "    ${DIM}./start.sh upgrade${RESET}         # Update to latest version"
  echo ""
}

# ── Main ─────────────────────────────────────────────────────────────────────

case "${1:-}" in
  up)       cmd_up ;;
  stop)     cmd_stop ;;
  restart)  cmd_restart ;;
  status)   cmd_status ;;
  logs)     cmd_logs "${2:-}" ;;
  upgrade)  cmd_upgrade ;;
  reset)    cmd_reset ;;
  help|-h|--help) cmd_help ;;
  *)
    if [ -z "${1:-}" ]; then
      cmd_up
    else
      error "Unknown command: $1"
      cmd_help
      exit 1
    fi
    ;;
esac
