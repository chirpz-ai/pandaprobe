#!/bin/bash
set -e

# ── Colour helpers ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Colour
BOLD='\033[1m'

ok()   { echo -e "  ${GREEN}✔${NC} $1"; }
fail() { echo -e "  ${RED}✘${NC} $1"; }
info() { echo -e "  ${CYAN}ℹ${NC} $1"; }

# ── Banner ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║         Opentracer Service v0.1.0        ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BOLD}Environment:${NC} ${APP_ENV:-development}"
echo ""

# ── Load .env file if present ───────────────────────────────────────────────
if [ -f ".env.${APP_ENV}" ]; then
    info "Loading .env.${APP_ENV}"
    set -a
    # shellcheck source=/dev/null
    source ".env.${APP_ENV}"
    set +a
elif [ -f ".env" ]; then
    info "Loading .env"
    set -a
    source ".env"
    set +a
fi

# ── Dependency checks ──────────────────────────────────────────────────────
echo -e "\n${BOLD}Service connectivity:${NC}"

# PostgreSQL
if pg_isready -h "${POSTGRES_HOST:-localhost}" -p "${POSTGRES_PORT:-5432}" -U "${POSTGRES_USER:-postgres}" -q 2>/dev/null; then
    ok "PostgreSQL  → ${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432}/${POSTGRES_DB:-opentracer_db}"
else
    fail "PostgreSQL  → ${POSTGRES_HOST:-localhost}:${POSTGRES_PORT:-5432} (unreachable)"
fi

# Redis
if redis-cli -h "${REDIS_HOST:-localhost}" -p "${REDIS_PORT:-6379}" ping 2>/dev/null | grep -q PONG; then
    ok "Redis       → ${REDIS_HOST:-localhost}:${REDIS_PORT:-6379}"
else
    fail "Redis       → ${REDIS_HOST:-localhost}:${REDIS_PORT:-6379} (unreachable)"
fi

# ── Detect service role from CMD ────────────────────────────────────────────
echo ""
SERVICE_ROLE="unknown"
for arg in "$@"; do
    case "$arg" in
        *uvicorn*) SERVICE_ROLE="app" ;;
        *celery*)  SERVICE_ROLE="worker" ;;
    esac
done

case "$SERVICE_ROLE" in
    app)
        echo -e "${BOLD}Running database migrations…${NC}"
        if /app/.venv/bin/python -m alembic upgrade head 2>&1; then
            ok "Migrations applied"
        else
            fail "Migrations failed (see output above)"
        fi
        echo ""
        echo -e "${BOLD}Starting:${NC} ${GREEN}App (FastAPI)${NC} on port 8000"
        echo -e "  Swagger UI → http://localhost:8000/docs"
        ;;
    worker)
        echo -e "${BOLD}Starting:${NC} ${YELLOW}Worker (Celery)${NC}"
        ;;
    *)
        echo -e "${BOLD}Starting:${NC} $*"
        ;;
esac

echo ""
exec "$@"
