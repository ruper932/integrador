# Arquitectura del sistema

Resumen de la arquitectura del sistema web de monitoreo de agua captada mediante atrapanieblas
(CEA “Ildefonso de las Muñecas”, Titicachi, Chuma, La Paz). El alcance y las reglas están en
[AGENTS.md](../AGENTS.md); el razonamiento detrás de cada decisión, en [decisiones.md](decisiones.md).

## 1. Visión general

El sistema funciona **en la red local de la institución, sin depender de Internet** ni de servicios
externos. Tiene cuatro piezas:

| Pieza | Tecnología | Función |
|-------|------------|---------|
| Estación IoT | ESP32 · PlatformIO · Arduino | Mide variables ambientales, volumen captado y nivel del tanque; envía lotes por HTTP/JSON. |
| API | Python · FastAPI · SQLAlchemy · Pydantic | Valida, almacena y expone los datos; aplica reglas de negocio, permisos y auditoría. |
| Interfaz web | React · TypeScript · Vite · Tailwind · shadcn/ui | Dashboard, históricos, reportes y administración. Solo consume la API REST. |
| Base de datos | PostgreSQL 16 | Única fuente de datos. Solo la API se conecta a ella. |

```text
   Equipos de la red local                         Servidor institucional (Docker Compose)
 ┌──────────────────────────┐                 ┌───────────────────────────────────────────────┐
 │ Navegador (React)        │── HTTP :80 ───▶ │  web: Nginx ── sirve el frontend compilado    │
 └──────────────────────────┘                 │      │  /api/*                                 │
 ┌──────────────────────────┐                 │      ▼                                        │
 │ ESP32 (estación IoT)     │── HTTP :80 ───▶ │  api: FastAPI (Uvicorn) ──▶ db: PostgreSQL    │
 │ buffer local en LittleFS │  /api/v1/iot/…  │                                    ▲          │
 └──────────────────────────┘                 │  backup: pg_dump diario → ./backups (fuera)   │
                                              └───────────────────────────────────────────────┘
                                                 red interna: solo Nginx publica un puerto
```

## 2. Despliegue

Definido en [compose.yaml](../compose.yaml):

- **web** (Nginx): único punto de entrada. Sirve el frontend y redirige `/api` y `/docs` a la API.
  Añade cabeceras de seguridad (CSP, `X-Frame-Options`, `nosniff`). Configuración en
  [deployment/nginx/default.conf](../deployment/nginx/default.conf).
- **api** (FastAPI): no publica puertos. Lee la configuración de variables de entorno (`.env`,
  fuera del control de versiones; los nombres están en `.env.example`).
- **db** (PostgreSQL): no publica puertos; datos en un volumen persistente.
- **backup**: respaldo diario con `pg_dump` en `./backups`, fuera del contenedor de la base, con
  retención de 30 días. Scripts de restauración y de prueba de restauración en
  [deployment/scripts/](../deployment/scripts/).

Todos los servicios usan `restart: unless-stopped` y vuelven a iniciar tras un reinicio del
servidor. Para desarrollo, `./iniciar.sh` levanta la API y el frontend (Vite) sin Docker.

## 3. Backend: monolito modular en tres capas

Una sola aplicación FastAPI, organizada internamente por capas. Cada capa solo conoce a la
inferior; no existe una cuarta capa.

```text
PRESENTACIÓN      app/presentation/api/       Routers: rutas, permiso requerido, conversión a esquemas
                  app/presentation/schemas/   Esquemas Pydantic: validación de entrada y salida
        │
        ▼
LÓGICA DE NEGOCIO app/business/services/      Servicios: reglas, transacciones, auditoría, avisos
                  app/business/rules/         Reglas puras (validación de mediciones, contraseñas, estadística)
                  app/business/ml/            Servicio de predicción (pendiente, ver §9)
        │
        ▼
ACCESO A DATOS    app/data/repositories/      Repositorios: todas las consultas SQLAlchemy
                  app/data/models/            Modelos ORM y restricciones CHECK
                  alembic/                    Migraciones del esquema

TRANSVERSAL       app/core/                   Configuración, errores, permisos, seguridad, reloj
```

**Reglas que se cumplen en todo el código**

- Los routers no contienen lógica de negocio ni ejecutan SQL: validan con Pydantic, verifican el
  permiso y delegan en un servicio.
- Los servicios reciben un `RequestContext` (usuario, IP) que usan para autorizar y auditar.
- Cada operación de escritura es **una transacción**: si una regla falla, no queda nada a medias.
  Por ejemplo, un mantenimiento sin stock suficiente no deja registros parciales.
- Los repositorios encapsulan las consultas; los servicios nunca construyen SQL.
- Las reglas críticas se refuerzan también en la base con restricciones `CHECK`. Por ejemplo, una
  lectura `valida` siempre tiene valor y una `sin_dato` siempre es `NULL`.
- Los errores salen con un formato JSON uniforme (`{"error": {"code", "message", "details"}}`).

**Ejemplo de flujo: aceptar un reporte de incidencia**

```text
POST /api/v1/incidents/{id}/accept
  presentation/api/incidents.py   exige el permiso «incidencias.atender» (401/403 si no)
  business/services/incident_service.py
        bloquea la fila del reporte (dos técnicos no pueden aceptar el mismo)
        crea el mantenimiento en estado «aceptado»
        avisa a quien reportó · registra «incidencia.aceptar» en auditoría · commit
  data/repositories/incidents.py, inventory.py   consultas y bloqueo SELECT … FOR UPDATE
```

### Módulos

| Módulo | Router | Servicio principal | Tablas principales |
|--------|--------|--------------------|--------------------|
| Autenticación y sesiones | `auth.py` | `auth_service` | `users`, `user_sessions` |
| Usuarios, roles y auditoría | `users.py`, `admin.py` | `user_service`, `audit_service` | `users`, `user_profiles`, `user_degrees`, `roles`, `permissions`, `audit_logs` |
| Recuperación de cuenta | `auth.py`, `admin.py` | `recovery_service` | `account_recovery_requests` |
| Infraestructura | `infrastructure.py` | `device_service`, `infrastructure_service`, `fog_collector_service` | `locations`, `fog_collectors`, `tanks`, `greenhouses`, `devices`, `device_credentials`, `device_locations`, `sensors`, `sensor_types` |
| Recepción IoT | `measurements.py` | `ingestion_service` | `measurement_batches`, `sensor_readings` |
| Dashboard e históricos | `measurements.py` | `measurement_service` | `sensor_readings` |
| Análisis estadístico | `analysis.py` | `analysis_service` | lecturas, mantenimientos, incidencias |
| Inventario | `inventory.py` | `inventory_service`, `inventory_period_service` | `inventory_items`, `inventory_movements`, `inventory_periods`, `inventory_counts`, … |
| Mantenimiento | `inventory.py` | `maintenance_service` | `maintenance_records`, `maintenance_items` |
| Reportes de incidencia | `incidents.py` | `incident_service`, `auto_incident_service`, `notification_service` | `incident_reports`, `notifications` |
| Reubicación de atrapanieblas | `relocations.py` | `relocation_service` | `fog_collector_relocations` |
| Reportes y exportación | `reports.py` | `report_service`, `report_catalog`, `report_renderers` | consultas de todos los módulos |

## 4. Datos

- **PostgreSQL** es la única fuente de verdad. El esquema solo cambia mediante migraciones de
  **Alembic**. Las migraciones no son destructivas: un `downgrade` que perdería datos se niega a
  ejecutarse.
- **Nada histórico se elimina físicamente.** Usuarios, dispositivos, sensores y repuestos se
  desactivan; los movimientos de inventario y las lecturas se conservan.
- **Mediciones**: cada lectura guarda la fecha de medición (del ESP32) y la de recepción (del
  servidor), la unidad y su calidad: `valida`, `sin_dato`, `fuera_de_rango`, `unidad_invalida` o
  `invalida`. Una variable no medida se guarda como `NULL`, nunca como `0`. El volumen es
  **incremental** (litros desde la lectura anterior): se suma por periodo y nunca se acumula dos veces.
- **Identificadores**: enteros para las entidades; UUID para `batch_id` y `message_id` de las
  mediciones, lo que permite descartar duplicados.
- **Zona horaria**: todo se guarda en UTC con zona; los agrupamientos por día, semana o mes usan
  la hora de Bolivia (`America/La_Paz`).

Tablas agrupadas por área:

```text
Seguridad        users · user_profiles · user_degrees · user_sessions · roles · permissions
                 audit_logs · account_recovery_requests
Catálogos        academic_levels · institutions · positions
Infraestructura  locations · fog_collectors · tanks · greenhouses
IoT              devices · device_credentials · device_locations · sensors · sensor_types
                 sensor_calibrations · measurement_batches · sensor_readings
Inventario       inventory_categories · inventory_items · inventory_item_compatibility
                 inventory_movement_types · inventory_movements · inventory_periods
                 inventory_counts · inventory_period_balances
Mantenimiento    maintenance_records · maintenance_items
Incidencias      incident_reports · notifications
Reubicaciones    fog_collector_relocations
ML (pendiente)   ml_models · predictions
```

## 5. Frontend

- **React + TypeScript estricto**, compilado con Vite y servido como archivos estáticos por Nginx.
  Funciona sin Internet: las fuentes son del sistema y la documentación Swagger se sirve localmente.
- **Organización por funcionalidad** en `src/features/<módulo>/` (página, formularios y hooks de
  datos), con componentes compartidos en `src/components/` (incluidos los de shadcn/ui) y
  utilidades en `src/lib/`.
- **Datos**: TanStack Query sobre Axios; el frontend nunca accede a la base. Formularios con React
  Hook Form y Zod; gráficos con Recharts.
- **Permisos**: la interfaz oculta lo que el rol no puede usar, pero la autorización real está
  siempre en el backend.
- **Filtros y reportes**: cada módulo muestra sus filtros en la vista principal
  (`features/reports/FilterToolbar.tsx`). Los mismos filtros actualizan el listado y se envían a la
  exportación. Los reportes (CSV, Excel con openpyxl, PDF con ReportLab) **se generan en el
  backend**; el frontend solo los solicita y descarga.
- **Diseño**: paleta pastel definida con tokens CSS en `src/index.css` (modo claro y oscuro, con
  contraste verificado). Las reglas están en [DESIGN.md](../DESIGN.md).

## 6. Estación IoT (firmware ESP32)

Detalle en [firmware/README.md](../firmware/README.md).

```text
sensores ──▶ lectura con message_id (UUID) ──▶ /pending.jsonl en LittleFS ──▶ lote de hasta 50
                                                         ▲                       │ POST HTTP/JSON
                                                         │ solo se borra         ▼
                                                         └──── tras HTTP 200 ◀── API: valida y guarda
```

- **Identidad propia por estación**: código del dispositivo y API key, enviados en las cabeceras
  `X-Device-Id` y `X-Device-Key`. La key se guarda en la memoria NVS (nunca en el código fuente).
  En el servidor solo se guarda su HMAC; se muestra una sola vez y puede rotarse.
- **Sin conexión**: las lecturas se conservan en la memoria flash y se reenvían al volver la red.
  El servidor descarta los `message_id` repetidos, así que reenviar es seguro.
- **Validación en el servidor**: estructura, unidad, rango físico, fecha (con zona, no futura),
  dispositivo activo y sensor asociado. Una lectura inválida se guarda marcada como tal, nunca
  como válida.
- La estación avisa por LED y consola la pérdida de comunicación; el dashboard muestra la última
  comunicación y advierte los datos desactualizados.

## 7. Seguridad

- **Autenticación**: usuario y contraseña; contraseñas con `scrypt` y sal aleatoria. Sesión con
  token aleatorio en cookie `HttpOnly` y `SameSite=Strict`; en la base solo queda su HMAC, con
  expiración y revocación al cerrar sesión o cambiar la contraseña. Tras 5 intentos fallidos la
  cuenta se bloquea 15 minutos.
- **Autorización (RBAC)**: cada endpoint declara el permiso que exige. Responde 401 sin sesión y
  403 sin permiso.
- **Roles**: `administrador`, `director`, `docente` y `mantenimiento`. Los permisos se asignan por
  rol y se pueden ajustar desde el panel.
- **Recuperación de cuenta** sin canales externos: la solicitud queda pendiente; el administrador
  verifica la identidad en persona, aprueba o rechaza, y da una contraseña temporal que debe
  cambiarse al ingresar. La aprobación invalida las sesiones del usuario. Las solicitudes tienen
  límite por usuario y por IP, y la respuesta no revela si el usuario existe.
- **Auditoría** de las operaciones relevantes (quién, qué, cuándo, desde qué IP), sin registrar
  contraseñas, tokens ni credenciales.
- **Red**: PostgreSQL y la API no son accesibles desde los equipos de usuarios; solo Nginx.

## 8. Procesos que involucran varios roles

| Proceso | Recorrido |
|---------|-----------|
| Reporte de incidencia | docente reporta → mantenimiento acepta, inicia y finaliza (con salida de repuestos) → director y administrador supervisan. El docente recibe un aviso en cada etapa. |
| Incidencia automática | el sistema detecta una estación activa sin comunicación o un sensor con lecturas anómalas → abre un reporte que sigue el flujo anterior, sin duplicados. La revisión corre dentro de la API cada 15 min, sin colas ni cron. |
| Reubicación de atrapanieblas | docente solicita (motivo y lugar sugerido) → mantenimiento acepta, inicia el traslado y finaliza con la nueva ubicación (el atrapanieblas y sus estaciones se trasladan con historial) o la rechaza antes de iniciar → director y administrador supervisan. Una sola solicitud en curso por atrapanieblas. |
| Mantenimiento con repuestos | mantenimiento registra el trabajo → se genera la salida de inventario en la misma transacción; si falta stock, no se registra nada. |
| Recuperación de cuenta | usuario solicita → administrador verifica y aprueba o rechaza → usuario cambia la contraseña temporal. |
| Periodo de inventario | administrador abre el periodo → registra el conteo físico → cierra con ajustes y saldos valorizados. |

Los avisos son internos (campana en la interfaz); no se usa correo, SMS ni aplicaciones externas.
Los procesos propuestos y aún no implementados (reposición de repuestos, calibración de sensores,
mantenimiento preventivo y activación controlada del modelo) están en [tareas.md](../tareas.md).

## 9. Machine learning (pendiente)

Diseño previsto, todavía sin implementar en producción:

- **Un único modelo** para predecir el volumen captado, encapsulado en un servicio de predicción
  en `app/business/ml/`.
- **Entrenamiento separado de la API** (notebooks y scripts con pandas y scikit-learn), con
  validación temporal y métricas registradas.
- El artefacto versionado se guarda con joblib en `backend/artifacts/`, que el contenedor monta
  en solo lectura.
- Cada predicción registrará fecha, variables, resultado, versión del modelo y estado (tablas
  `ml_models` y `predictions`), y se podrá comparar con el volumen real.
- Antes de implementarlo hay que confirmar el horizonte de predicción y las variables, y reunir
  datos reales. El flujo ya se probó con datos sintéticos; ver [simulacion_ml.md](simulacion_ml.md).

## 10. Calidad

- **Backend**: pruebas con pytest y HTTPX contra una base PostgreSQL de pruebas, que se reconstruye
  con las migraciones en cada ejecución. Lint y formato con Ruff.
- **Frontend**: pruebas con Vitest y React Testing Library, E2E con Playwright, chequeo de tipos
  con `tsc` y lint con oxlint.
- **Fuera de alcance por diseño**: no se usan MQTT, Redis, Celery ni otros intermediarios, ni
  servicios en la nube, aplicación móvil, control automático de riego ni 2FA por canales externos.
