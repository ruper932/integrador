#!/bin/sh
# Restaura un respaldo en la base del despliegue Docker.
# Uso: deployment/scripts/restore.sh backups/atrapanieblas_YYYYMMDD_HHMMSS.dump
# ATENCIÓN: reemplaza el contenido actual de la base de datos. Detiene la API durante la restauración.
set -eu
dump="${1:?Indique el archivo de respaldo}"
[ -f "$dump" ] || { echo "No existe $dump" >&2; exit 1; }
printf "Se reemplazará la base de datos actual con %s. Escriba RESTAURAR para continuar: " "$dump"
read -r answer
[ "$answer" = "RESTAURAR" ] || { echo "Cancelado."; exit 1; }
docker compose stop api
docker compose exec -T db sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$dump"
docker compose start api
echo "Restauración completada."
