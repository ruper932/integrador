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

Para conectar estaciones ESP32 reales (o abrir el sistema desde otras computadoras), use
`./iniciar_red.sh`: publica la API en `http://<IP del equipo>:8000` y precarga esa dirección para la
primera instalación de las estaciones. El acceso USB del navegador solo funciona en `http://localhost:5173`
(o por HTTPS).

Para cargar datos de demostración (usuarios de cada rol, estaciones, 30 días de lecturas
simuladas, inventario y mantenimientos):

```bash
cd backend && .venv/bin/python -m app.cli seed-demo
```

Sobre una base que ya tiene la demostración, el mismo comando completa las lecturas simuladas desde la
última hasta ahora (útil para que el modelo provisional tenga datos recientes). Son datos simulados: no
deben usarse para entrenar el modelo real.

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
sh deployment/scripts/generar-certificado.sh 192.168.1.10   # IP del servidor en la red local
docker compose up -d --build
docker compose exec api python -m app.cli create-admin --username admin
```

- Solo Nginx publica puertos: **443** (sistema web por HTTPS, con el certificado propio que genera
  `generar-certificado.sh`, sin Internet) y **80** (solo para las estaciones ESP32; un navegador que entra
  por `http://` pasa a `https://`). La API y PostgreSQL no son accesibles desde los equipos de usuarios.
- La primera vez, cada equipo debe aceptar el certificado (o instalar `deployment/certs/servidor.crt` como
  confiable). HTTPS es necesario para la primera instalación del ESP32 desde el navegador.
- Los servicios usan `restart: unless-stopped` y vuelven a iniciar tras un reinicio del servidor
  (con Docker habilitado al arranque).
- El servicio `backup` genera un respaldo diario en `./backups` (fuera del contenedor de la base)
  y conserva 30 días.
- Probar la restauración periódicamente: `deployment/scripts/test-restore.sh`.
- Restaurar: `deployment/scripts/restore.sh backups/<archivo>.dump`.
- Dé al servidor una **IP fija** (o una reserva en el router): las estaciones envían a una dirección fija.
- Datos que la primera instalación precarga en cada estación (en `.env`): `STATION_WIFI_SSID`,
  `STATION_WIFI_PASSWORD` (solo se envía al ESP32, nunca se muestra), `STATION_API_URL` y
  `STATION_NTP_SERVER` (servidor de hora de la red local; sin hora el ESP32 no registra lecturas).

## Conexión de las estaciones

Una estación se considera **sin conexión** cuando pasan 3 intervalos de envío más 60 s sin comunicarse
(con envío cada 30 s, 2,5 minutos), con `DEVICE_STALE_MINUTES` como tope. La regla es única
(`backend/app/business/rules/connection.py`) y la usan Monitoreo, Dispositivos, el resumen del menú
lateral, el Dashboard, Atrapanieblas y los reportes, que se refrescan cada 30 s.

## Reportes

Cada módulo tiene filtros, un panel **Resumen y gráficos** y exportación. Excel y PDF incluyen el mismo
resumen y los mismos gráficos que la pantalla (gráficos nativos de Excel y vectoriales en PDF, con
encabezado institucional y numeración de páginas); el CSV lleva solo los datos. El análisis estadístico
también se exporta.

## Flujo de una estación nueva

1. Administrador: registrar atrapanieblas/tanque en **Dispositivos** y luego el dispositivo.
2. Agregar los sensores con los códigos que usa el firmware (`temp`, `hum`, `pres`, `vol`, `nivel`…).
3. En **Firmware de estaciones → Primera instalación por USB** (Chromium, Chrome o Edge, por `https://` o
   `http://localhost`): conectar el ESP32, revisar los datos precargados (versión, estación, red Wi-Fi,
   dirección de envío y servidor de hora) y pulsar **Conectar e instalar**. Se escribe el firmware y se
   carga su configuración con una API key nueva que no se muestra en pantalla. Para un ESP32 que ya tiene
   el firmware, **Solo configurar** carga únicamente la configuración (p. ej. si cambió la IP del servidor).
   En Brave, active antes `brave://flags/#brave-web-serial`.
   (Alternativa sin navegador: `pio run -t upload` y la configuración por consola serie, ver `firmware/README.md`.)
4. Verificar en **Monitoreo** o **Dispositivos** que la estación figure «En línea». En la consola serie,
   el comando `sensores` muestra si responden el sensor I²C (BME280/BMP280) y el DHT, para revisar el cableado.
