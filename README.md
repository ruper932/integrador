# Sistema de monitoreo de atrapanieblas

Sistema web local de monitoreo de agua captada mediante atrapanieblas, con IoT y predicción
de volumen basada en machine learning.

Caso de estudio: Centro de Educación Alternativa “Ildefonso de las Muñecas”, Titicachi, Chuma, La Paz, Bolivia.

Funciona en la red local institucional, sin depender de Internet. El alcance y las reglas del
proyecto están en [AGENTS.md](AGENTS.md); el avance, en [tareas.md](tareas.md); la arquitectura,
en [docs/arquitectura.md](docs/arquitectura.md); las decisiones técnicas, en [docs/decisiones.md](docs/decisiones.md).

## Estructura

```text
backend/     API FastAPI (presentación → negocio → datos), Alembic, pruebas pytest
frontend/    React + TypeScript + Vite + Tailwind + shadcn/ui
firmware/    ESP32 (PlatformIO + Arduino)
deployment/  Nginx y scripts de respaldo/restauración
notebooks/   Simulación del flujo de ML con datos sintéticos (modelo de producción pendiente)
docs/        Documentación
compose.yaml Despliegue local con Docker Compose
```

## Inicio rápido (modo local)

```bash
./iniciar.sh
```

Aplica las migraciones, crea el usuario `admin` con una contraseña temporal si no existe ningún
administrador (la muestra una sola vez), inicia la API y el frontend y queda en ejecución hasta
presionar Ctrl+C. Luego abra **http://localhost:5173**. Registros en `logs/`.

Para cargar datos de demostración (usuarios de cada rol, estaciones, 30 días de lecturas
simuladas, inventario y mantenimientos):

```bash
cd backend && .venv/bin/python -m app.cli seed-demo
```

## Desarrollo

### Backend

Requisitos: Python 3.12+ y PostgreSQL.

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env            # completar DATABASE_URL, TEST_DATABASE_URL y SECRET_KEY
.venv/bin/alembic upgrade head
.venv/bin/python -m app.cli create-admin --username admin --full-name "Administrador"
.venv/bin/uvicorn app.main:app --reload
```

Documentación de la API: <http://localhost:8000/docs>.

```bash
.venv/bin/pytest        # pruebas (usa TEST_DATABASE_URL; la base de pruebas se reconstruye)
.venv/bin/ruff check .  # lint
```

### Frontend

Requisitos: Node 22+.

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (redirige /api a localhost:8000)
npm test           # Vitest + Testing Library
npm run build
```

Pruebas E2E (con la API en ejecución y un usuario de prueba):

```bash
CHROMIUM_PATH=/usr/bin/chromium E2E_USERNAME=... E2E_PASSWORD=... npm run test:e2e
```

### Firmware

Ver [firmware/README.md](firmware/README.md).

## Despliegue en el servidor local

```bash
cp .env.example .env     # completar POSTGRES_PASSWORD y SECRET_KEY
docker compose up -d --build
docker compose exec api python -m app.cli create-admin --username admin
```

- Solo Nginx publica el puerto 80. La API y PostgreSQL no son accesibles desde los equipos de usuarios.
- Los servicios usan `restart: unless-stopped` y vuelven a iniciar tras un reinicio del servidor
  (con Docker habilitado al arranque).
- El servicio `backup` genera un respaldo diario en `./backups` (fuera del contenedor de la base)
  y conserva 30 días.
- Probar la restauración periódicamente: `deployment/scripts/test-restore.sh`.
- Restaurar: `deployment/scripts/restore.sh backups/<archivo>.dump`.

## Flujo de una estación nueva

1. Administrador: registrar atrapanieblas/tanque en **Dispositivos** y luego el dispositivo; copiar la API key.
2. Agregar los sensores con los códigos que usa el firmware (`temp`, `hum`, `vol`, `nivel`…).
3. Cargar la configuración en el ESP32 por puerto serie y reiniciarlo.
4. Verificar en el **Dashboard** la última comunicación y las lecturas.
