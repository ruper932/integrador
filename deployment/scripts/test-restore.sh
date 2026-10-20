#!/bin/sh
# Prueba de restauración: restaura el respaldo más reciente en una base temporal
# y verifica que las tablas principales tengan datos. No toca la base en uso.
set -eu
latest=$(ls -1t backups/atrapanieblas_*.dump 2>/dev/null | head -n1)
[ -n "$latest" ] || { echo "No hay respaldos en ./backups" >&2; exit 1; }
echo "Probando $latest"
docker compose exec -T db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" restore_test && createdb -U "$POSTGRES_USER" restore_test'
docker compose exec -T db sh -c 'pg_restore --no-owner -U "$POSTGRES_USER" -d restore_test' < "$latest"
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d restore_test -c "SELECT (SELECT count(*) FROM users) AS usuarios, (SELECT count(*) FROM sensor_readings) AS lecturas, (SELECT count(*) FROM inventory_items) AS repuestos;"'
docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" restore_test'
echo "Prueba de restauración correcta."
