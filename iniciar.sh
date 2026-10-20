#!/usr/bin/env bash
# Levanta el sistema completo en modo local (desarrollo / pruebas):
#   - API FastAPI en http://127.0.0.1:8000  (documentación en /docs)
#   - Frontend React en http://localhost:5173 (abrir esta dirección en el navegador)
# Requisitos: PostgreSQL en ejecución, Python 3.12+ y Node 22+.
# Uso: ./iniciar.sh        (Ctrl+C detiene ambos servicios)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
LOGS="$ROOT/logs"
API_PORT=8000
WEB_PORT=5173

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

port_in_use() { ss -ltn "sport = :$1" 2>/dev/null | grep -q LISTEN; }

# --- Verificaciones -----------------------------------------------------------
command -v python3 >/dev/null || fail "No se encontró python3."
command -v npm >/dev/null || fail "No se encontró npm (Node.js)."
[ -f "$BACKEND/.env" ] || fail "Falta backend/.env. Copie backend/.env.example y complete los valores."
if command -v pg_isready >/dev/null && ! pg_isready -q; then
  fail "PostgreSQL no está en ejecución (inícielo con: sudo systemctl start postgresql)."
fi
port_in_use "$API_PORT" && fail "El puerto $API_PORT ya está en uso. Detenga el proceso que lo ocupa."
port_in_use "$WEB_PORT" && fail "El puerto $WEB_PORT ya está en uso. Detenga el proceso que lo ocupa."
mkdir -p "$LOGS"

# --- Backend ------------------------------------------------------------------
if [ ! -x "$BACKEND/.venv/bin/python" ]; then
  info "Creando entorno de Python e instalando dependencias…"
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install -q -e "$BACKEND[dev]"
fi

cd "$BACKEND"
info "Aplicando migraciones de la base de datos…"
.venv/bin/alembic upgrade head >"$LOGS/migraciones.log" 2>&1 || fail "Fallaron las migraciones (ver logs/migraciones.log)."

info "Verificando el usuario administrador…"
.venv/bin/python -m app.cli ensure-admin --username admin

# --- Frontend -----------------------------------------------------------------
if [ ! -d "$FRONTEND/node_modules" ]; then
  info "Instalando dependencias del frontend…"
  (cd "$FRONTEND" && npm install --silent)
fi

# --- Arranque -----------------------------------------------------------------
PIDS=()
cleanup() {
  echo
  info "Deteniendo servicios…"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  wait 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 0' INT TERM

info "Iniciando API en el puerto $API_PORT…"
(cd "$BACKEND" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$API_PORT") >"$LOGS/api.log" 2>&1 &
PIDS+=($!)

info "Iniciando frontend en el puerto $WEB_PORT…"
(cd "$FRONTEND" && exec node_modules/.bin/vite --port "$WEB_PORT" --strictPort) >"$LOGS/frontend.log" 2>&1 &
PIDS+=($!)

for _ in $(seq 1 60); do
  if curl -sf "http://localhost:$WEB_PORT/api/v1/health/db" >/dev/null 2>&1; then
    cat <<EOF

  Sistema listo.
  Abra en su navegador:  http://localhost:$WEB_PORT
  Documentación API:     http://127.0.0.1:$API_PORT/docs
  Registros:             $LOGS/
  Presione Ctrl+C para detener.

EOF
    wait -n "${PIDS[@]}" || true
    fail "Un servicio se detuvo inesperadamente (ver logs/api.log y logs/frontend.log)."
  fi
  sleep 1
done
fail "Los servicios no respondieron a tiempo (ver logs/api.log y logs/frontend.log)."
