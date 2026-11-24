# Registro de tareas

Lista de tareas realizadas sobre el proyecto, en orden cronológico. Se actualiza a medida que avanza el trabajo.

## 2026-10-14

### Entorno y estructura
- [x] Estructura de carpetas según `AGENTS.md` (`backend/`, `frontend/`, `firmware/`, `notebooks/`, `deployment/`, `docs/`).
- [x] Entorno virtual de Python en `backend/.venv` con las dependencias del stack.
- [x] Bases PostgreSQL locales `atrapanieblas_db` (desarrollo) y `atrapanieblas_test` (pruebas) con rol propio `atrapanieblas`.
- [x] `backend/.env` (no versionado, permisos 600) y `backend/.env.example` sin valores reales.

### Fase 1 — Configuración base del backend y base de datos
- [x] Configuración centralizada con `pydantic-settings` (`app/core/config.py`).
- [x] Errores de aplicación con formato JSON consistente (`app/core/errors.py`).
- [x] Conexión SQLAlchemy y convención de nombres de restricciones (`app/data/database.py`).
- [x] Modelos de todas las tablas del modelo de datos mínimo (excepto ML, ver pendientes).
- [x] Alembic configurado; migración `esquema inicial` y migración `datos de referencia` (roles, permisos, tipos de sensor, categorías y tipos de movimiento de inventario).
- [x] Endpoints `GET /api/v1/health` y `GET /api/v1/health/db`.

### Fase 2 — Autenticación, usuarios, roles y auditoría
- [x] Contraseñas con hash scrypt y sal aleatoria (biblioteca estándar, sin dependencias nuevas).
- [x] Sesiones con token aleatorio en cookie `HttpOnly` + `SameSite=Strict`, almacenado como HMAC-SHA256 y con expiración.
- [x] Login, logout (revoca la sesión), `GET /auth/me`, cambio de contraseña (cierra las demás sesiones).
- [x] Bloqueo temporal tras 5 intentos fallidos; mensaje genérico que no revela si el usuario existe.
- [x] Cambio obligatorio de contraseña temporal antes de usar el sistema.
- [x] RBAC en backend: 18 permisos, roles `administrador`, `director_docente`, `observador` y rol complementario `mantenimiento` (el 2026-10-15 se renombraron a `director` y `docente`; ver «Reportes de incidencia»).
- [x] CRUD de usuarios (desactivación lógica), restablecimiento de contraseña por el administrador, protección del último administrador.
- [x] Gestión de roles y permisos (el rol administrador no puede perder permisos).
- [x] Auditoría de operaciones relevantes, sin contraseñas ni credenciales; `GET /admin/audit-logs`.
- [x] CLI para crear el primer administrador: `python -m app.cli create-admin --username admin`.

### Fase 3 — Recuperación de cuenta mediante el administrador
- [x] Solicitud pública que responde igual exista o no el usuario.
- [x] Límite por IP (429) y límite silencioso por usuario.
- [x] Aprobación solo con confirmación explícita de verificación presencial de identidad; contraseña temporal o definida por el administrador.
- [x] La aprobación invalida las sesiones activas y obliga a cambiar la contraseña; rechazo con motivo; registro en auditoría.

### Fase 4 — Dispositivos, sensores y ubicaciones
- [x] CRUD con desactivación lógica de ubicaciones, atrapanieblas, tanques e invernaderos.
- [x] Dispositivos ESP32 con identidad única y API key propia (se muestra una sola vez, se guarda como HMAC), rotación de credencial.
- [x] Historial de ubicaciones del dispositivo (`device_locations`).
- [x] Sensores asociados a dispositivo y tipo; un sensor de volumen exige atrapanieblas y uno de nivel exige tanque.
- [x] 8 tipos de sensor con unidad y rango físico; el volumen captado se define como **incremental** (litros desde la lectura anterior).

### Fase 5 — Recepción y validación de mediciones IoT
- [x] `POST /api/v1/iot/measurements/batch` autenticado con `X-Device-Id` / `X-Device-Key`.
- [x] Dispositivo inactivo → 403; sensor no asociado o inactivo → lectura rechazada.
- [x] Fechas con zona horaria obligatoria; fechas futuras rechazadas; fecha de recepción registrada por el servidor.
- [x] Calidad de lectura: `valida`, `sin_dato` (valor `null`), `fuera_de_rango`, `unidad_invalida`, `invalida`. Restricciones CHECK en la base impiden guardar una lectura inválida como válida.
- [x] Idempotencia por `batch_id` y por `message_id` (sin duplicados, reenvío seguro).

### Fase 6 — Dashboard e históricos
- [x] `GET /api/v1/measurements` con filtros por dispositivo, sensor, tipo, atrapanieblas, calidad y fechas.
- [x] `GET /api/v1/dashboard/summary`: última comunicación, advertencia de datos desactualizados, últimos valores, volumen de hoy / 7 días / mes.
- [x] `GET /api/v1/dashboard/series`: agregación por hora/día/semana/mes en hora de Bolivia (suma para variables incrementales, promedio para instantáneas).

### Fase 7 — Inventario de repuestos IoT
- [x] Categorías (9 sugeridas precargadas), repuestos con unidad, stock actual, stock mínimo, estado y ubicación de almacenamiento.
- [x] Compatibilidad con dispositivos y sensores; filtro de repuestos compatibles.
- [x] Entradas y salidas con bloqueo de fila; no se permite salida mayor al stock; cada movimiento registra fecha, usuario, tipo, cantidad, motivo y stock antes/después.
- [x] Alertas de stock bajo; reportes de stock y movimientos en JSON y CSV.
- [x] Repuestos se desactivan, no se eliminan.

### Fase 8 — Mantenimiento y vinculación con inventario
- [x] Registro de mantenimiento con dispositivo/sensor, fecha, responsable, tipo, descripción, estado final y repuestos usados.
- [x] Cada repuesto usado genera una salida `salida_mantenimiento` vinculada; todo se revierte si falta stock.
- [x] Un reemplazo exige repuestos; el sensor debe pertenecer al dispositivo; no se aceptan fechas futuras.

### Calidad del backend
- [x] Pruebas con pytest sobre PostgreSQL real (las migraciones se aplican en cada ejecución): autenticación, RBAC, recuperación, IoT, dashboard, inventario, mantenimiento, reglas y reportes.
- [x] Ruff sin observaciones.
- [x] Cualquier error revierte la transacción completa (sin cambios parciales).

### Frontend (React + TypeScript estricto + Vite + Tailwind + shadcn/ui)
- [x] Cliente Axios con cookie de sesión (el token nunca llega a JavaScript); TanStack Query; React Router.
- [x] Inicio de sesión, solicitud de recuperación de cuenta, cambio obligatorio de contraseña temporal.
- [x] Menú según los permisos del usuario (el backend sigue validando cada permiso).
- [x] Dashboard: volumen de hoy / 7 días / mes, aviso de datos desactualizados, estado de estaciones, últimos valores, gráfico por variable y periodo (Recharts, una serie y un eje, sin animación).
- [x] Históricos con filtros y paginación; Dispositivos y sensores (API key mostrada una sola vez, rotación); Inventario (alta, movimientos, alertas, CSV); Mantenimiento con repuestos; Usuarios; Recuperación de cuentas; Auditoría; Reportes.
- [x] Formularios con React Hook Form + Zod.
- [x] Pruebas: Vitest + Testing Library (5) y Playwright E2E (2, con el Chromium del sistema).
- [x] Prueba de humo real: API + Vite + datos simulados de una semana; capturas revisadas (se corrigió un fallo de barras invisibles y una columna cortada).

### Fase 12 — Reportes y exportaciones
- [x] `GET /api/v1/reports/export` en CSV, Excel (openpyxl) y PDF (ReportLab), generados en el backend.
- [x] Reportes: volumen captado, variable ambiental agregada, histórico de mediciones, mantenimientos, movimientos y stock de inventario; filtros por fechas, dispositivo, atrapanieblas, variable e intervalo.
- [x] Valores no medidos quedan vacíos (no 0); la exportación se registra en auditoría; requiere `reportes.generar`.

### Firmware ESP32 (PlatformIO + Arduino)
- [x] Credenciales cargadas por puerto serie y guardadas en NVS (no están en el código fuente).
- [x] Cola persistente en LittleFS; envío por lotes con `message_id` UUID; solo se elimina lo confirmado por el servidor.
- [x] Volumen incremental por pulsos; sensores ausentes enviados como `null`; hora por NTP local y fechas en UTC.
- [x] Aviso de pérdida de comunicación (LED y consola serie).
- [x] Compila sin advertencias (`pio run`: RAM 15 %, flash 78 %).

### Fase 13 — Despliegue local
- [x] `compose.yaml`: PostgreSQL (sin puerto publicado), API, Nginx (único puerto publicado) y servicio de respaldo diario en `./backups`, todos con `restart: unless-stopped`.
- [x] Dockerfiles de backend (usuario sin privilegios, aplica migraciones al iniciar) y frontend (build + Nginx).
- [x] Nginx con cabeceras de seguridad, proxy `/api` y `/docs`, rutas SPA.
- [x] Scripts `restore.sh` (con confirmación) y `test-restore.sh` (restaura en una base temporal).
- [x] Swagger UI (`/docs`) servido con archivos locales: funciona sin Internet.
- [x] Las imágenes Docker se construyen correctamente. **No se levantaron los contenedores** (paso detenido por el usuario).

### Documentación
- [x] `README.md` (desarrollo, despliegue, alta de estaciones), `firmware/README.md`, `docs/decisiones.md`, `.gitignore`, `.env.example` raíz.

## 2026-10-15

### Simulación del modelo de ML (datos sintéticos — el modelo de producción sigue pendiente)
- [x] Entorno separado `notebooks/.venv` con pandas, NumPy, scikit-learn y joblib (`notebooks/requirements.txt`).
- [x] Generador de 2 años de lecturas horarias sintéticas, con estacionalidad, episodios de niebla, régimen húmedo de varios días y lecturas faltantes como `null`.
- [x] Preparación diaria con horizonte **supuesto** D+1, sin variables futuras; los días con poca cobertura no se usan como objetivo.
- [x] Entrenamiento de `HistGradientBoostingRegressor` con `TimeSeriesSplit` y prueba en el último 30 % del periodo.
- [x] Métricas (MAE, RMSE, R²) frente a dos referencias: persistencia y media de 7 días.
- [x] Artefacto versionado `sim-0.1.0` con metadatos; inferencia que devuelve `datos_insuficientes` cuando corresponde; CSV de comparación real vs. estimado.
- [x] Resultado: el modelo supera a la persistencia, pero **no** a la media de 7 días (MAE 14,7 frente a 14,1 L/día). Informe en `docs/simulacion_ml.md`.

### Script de arranque
- [x] `iniciar.sh`: verifica PostgreSQL y puertos, instala dependencias si faltan, aplica migraciones, crea el administrador inicial y levanta la API (8000) y el frontend (5173). Ctrl+C detiene ambos.
- [x] Comando `python -m app.cli ensure-admin`: crea `admin` con contraseña temporal (cambio obligatorio en el primer inicio) solo si no existe ningún administrador activo.
- [x] Administrador inicial creado en la base de desarrollo `atrapanieblas_db`.

### Usuarios: base de datos normalizada
- [x] Datos personales separados de las credenciales (`user_profiles`, 1:1): nombres, apellido paterno, apellido materno, CI con complemento y expedido, correo institucional, correo personal, celular y dirección.
- [x] Información laboral: cargo en el CEA (catálogo) y formación académica con varios títulos (`user_degrees`): nivel, título, institución de egreso y año de egreso.
- [x] Catálogos precargados: 10 niveles académicos, 12 instituciones (orientadas a La Paz) y 5 cargos; el administrador puede agregar instituciones.
- [x] Validaciones: CI numérico y único (con complemento), celular boliviano (8 dígitos, 6/7), correos, al menos un apellido, año de egreso no futuro; normalización de mayúsculas y espacios.
- [x] Migración Alembic sin pérdida de datos: el nombre existente pasó al perfil antes de eliminar `users.full_name`; `downgrade` probado.
- [x] La API conserva `full_name` como dato derivado (compatibilidad); búsqueda por nombre, apellido o CI.
- [x] Formulario de usuario por secciones (cuenta, datos personales, información laboral, títulos) para crear y editar; aviso de "perfil incompleto".

### Inventario periódico y reportes completos
- [x] Periodos de inventario (sin superposición), conteo físico, cierre con ajustes automáticos por sobrantes y faltantes, saldos congelados y bloqueo de movimientos en periodos cerrados.
- [x] Fecha efectiva y costo unitario (Bs) en los movimientos; valorización por costo promedio ponderado con arrastre del valor entre periodos.
- [x] Reportes nuevos: resumen valorizado del periodo, planilla y acta de conteo (con líneas de firma), kardex por repuesto y consumo por mantenimiento; los movimientos incluyen fecha efectiva y costo.
- [x] Pantalla de inventario con pestaña "Periodos y conteo físico" y nuevas opciones en Reportes.
- [x] Pruebas: 99 en backend (incluye perfiles, periodos, valorización y reportes) y 7 en frontend.

### Perfil del usuario autenticado
- [x] Botón **Mi perfil** en la barra lateral (también visible en celulares, junto con "Salir").
- [x] Página `/perfil`: datos personales, formación académica y datos de la cuenta (usuario, roles, estado, último acceso).
- [x] Edición de los propios datos con las mismas validaciones que el panel de administración: `PUT /api/v1/auth/me/profile`.
- [x] El usuario no puede cambiar su usuario, roles, estado ni cargo (los asigna el administrador); auditoría `perfil.actualizar_propio` sin datos personales.
- [x] Cambio de contraseña desde el perfil (componente compartido con la pantalla de contraseña temporal); cierra las sesiones en otros equipos.
- [x] Pruebas: 105 en backend y 10 en frontend; flujo revisado en navegador (escritorio y celular).

### Rediseño UX/UI con la plantilla ATINA
- [x] Paleta de la plantilla (`plantilla-atina.html`) como tokens de tema para shadcn/ui y Tailwind: claro y oscuro, con tonos semánticos de éxito, advertencia y peligro.
- [x] Modo oscuro con selector (se recuerda en el navegador) y sin destello al cargar.
- [x] Layout nuevo: barra lateral agrupada (Principal, Operaciones, Administración), plegable en escritorio y desplegable en celular; contadores de stock bajo y recuperaciones pendientes; estado real del servidor local; migas de pan; menú de usuario (perfil, contraseña, tema, cerrar sesión); enlace "Saltar al contenido".
- [x] Resumen general al estilo de la plantilla con datos reales: indicadores con icono, gráfico con total del periodo, estado de estaciones, aviso de stock bajo y tabla filtrable de últimas mediciones.
- [x] Acceso rediseñado (panel de marca + formulario), contraseña con mostrar/ocultar y aviso de Bloq Mayús; tras iniciar sesión se vuelve a la página solicitada.
- [x] Componentes comunes: encabezado con antetítulo, avisos con icono (no solo color), estados vacíos, insignias de estado, paginación con rango, botón "Copiar" para contraseñas temporales y API keys.
- [x] Colores fijos reemplazados por tonos del tema en todas las pantallas; campos y selectores con la misma altura.
- [x] Verificado en navegador (claro, oscuro, menú plegado y celular); 10 pruebas de frontend y 2 E2E.

### Datos de demostración
- [x] Comando `python -m app.cli seed-demo` (se niega en producción y si ya hay datos de demostración); carga todo mediante los servicios, con validaciones y auditoría.
- [x] Base de desarrollo cargada: 6 usuarios con perfil completo y títulos (2 director/docente, 2 observadores, 2 de mantenimiento), 3 ubicaciones, 2 atrapanieblas, 2 tanques, 2 invernaderos, 3 estaciones ESP32 (una en mantenimiento), 16 sensores, calibraciones, 11 520 lecturas simuladas de 30 días (con casos sin dato y fuera de rango), 14 repuestos con costos, 3 periodos (2 cerrados con conteo y ajustes, 1 abierto), 5 mantenimientos (con consumo de repuestos) y 3 solicitudes de recuperación.
- [x] Quien no tiene acceso al dashboard entra directamente a su primera sección permitida.
- [x] Prueba automática del comando (107 pruebas en backend).

### Diagramas UML (draw.io)
- [x] 17 diagramas en `docs/diagramas/uml_atina.drawio` (editable en draw.io Desktop), con PDF y PNG por página: arquitectura, despliegue, casos de uso y, por módulo, clases, secuencias, actividades y estados basados en el código actual.
- [x] El diagrama de predicción queda marcado como propuesta pendiente.

### Paleta pastel y tonos cálidos
- [x] Modo claro: fondo crema, tarjetas marfil, bordes cálidos y estados en tonos pastel.
- [x] Modo oscuro: grises cálidos (café y carbón) con acentos menta y ámbar suaves.
- [x] Panel del inicio de sesión, velo del menú móvil, favicon y color de la barra del navegador adaptados.
- [x] Contraste de texto verificado (≥ 4,5:1) en ambos modos; revisado en navegador.

### Casos de uso por módulo (draw.io)
- [x] 7 diagramas de casos de uso detallados, uno por módulo, en `docs/diagramas/casos_de_uso_modulos.drawio` (con PDF y PNG), basados en los permisos y reglas implementados; el módulo de predicción queda marcado como pendiente.

### Reportes de incidencia y flujo de mantenimiento
- [x] Roles: `observador` pasa a **`docente`** y `director_docente` pasa a **`director`** (migración que renombra, sin perder asignaciones); `mantenimiento` es ahora el rol del personal de mantenimiento.
- [x] Permisos nuevos: `incidencias.reportar` (docente, director), `incidencias.atender` (mantenimiento) e `incidencias.supervisar` (director, administrador).
- [x] El docente reporta una situación (título, descripción, prioridad, lugar y, opcionalmente, dispositivo y sensor).
- [x] El personal de mantenimiento recibe un aviso; acepta el reporte, lo que crea el mantenimiento en estado **aceptado**, luego lo pasa a **en progreso** y lo **finaliza** registrando el trabajo y los repuestos (salida de inventario; si falta stock no se finaliza).
- [x] Solo el personal asignado avanza el mantenimiento; dos técnicos no pueden aceptar el mismo reporte (bloqueo de fila).
- [x] El docente ve el estado y el nombre del personal asignado, y recibe un aviso en cada etapa; administrador y director ven todos los reportes con su seguimiento.
- [x] Avisos internos (campana en la barra superior, sin servicios externos) y contador de reportes por atender en el menú.
- [x] Pantalla «Reportes de incidencia» (por atender, asignados a mí, todos, mis reportes) con línea de tiempo; la pantalla de mantenimiento muestra el estado y enlaza al reporte.
- [x] Auditoría: `incidencia.reportar`, `incidencia.aceptar`, `incidencia.iniciar`, `incidencia.finalizar`.
- [x] Migración Alembic `ab5f416fb049` (probada en ambos sentidos; el downgrade se niega si hay reportes, para no perder datos).
- [x] 8 pruebas de backend (115 en total) y 2 de frontend (12 en total); flujo completo probado en el navegador con los tres roles.
- [x] Datos de demostración: 5 reportes, uno en cada etapa (cargados también en la base de desarrollo).

### Validaciones de edad en el registro de usuarios
- [x] Fecha de nacimiento en el perfil (obligatoria): mayor de 18 años, no futura, no más de 100 años.
- [x] Año de egreso coherente con la edad según el nivel del título (edad mínima de egreso por nivel en el catálogo `academic_levels`); también se revalida al cambiar la fecha de nacimiento.
- [x] Validación en el backend (regla de negocio) y en el formulario (edad calculada y «Desde AAAA» en cada título); se aplica al crear, al editar y en «Mi perfil».
- [x] Migración `4eca9300bd5f` (probada en ambos sentidos; el downgrade se niega si ya hay fechas registradas).
- [x] Fechas de nacimiento coherentes para los usuarios de demostración (también en la base de desarrollo).
- [x] 7 pruebas de backend (122 en total) y 5 de frontend (17 en total).

### Reportes con filtros por módulo
- [x] Catálogo de reportes por módulo con el permiso y los filtros de cada uno (`GET /api/v1/reports/catalog`); filtros obligatorios marcados.
- [x] Monitoreo IoT: volumen, variable y mediciones con dispositivo, atrapanieblas, variable, calidad de la lectura y agrupación; nuevo reporte «Estado de las estaciones» (estado del dispositivo, atrapanieblas, última comunicación).
- [x] Inventario: stock por categoría, estado del repuesto, solo stock bajo e incluir desactivados; movimientos por categoría, repuesto y tipo; resumen y conteo del periodo por categoría; consumo por dispositivo, categoría y repuesto.
- [x] Mantenimiento: por dispositivo, tipo, estado final, responsable y origen (reporte de incidencia o registro directo).
- [x] Nuevo reporte de incidencias: estado, prioridad, dispositivo, quién reportó y quién atendió, con tiempos de atención.
- [x] Nuevos reportes de usuarios (rol, cargo, estado de la cuenta) y de auditoría (acción o módulo, usuario, periodo), solo para el administrador.
- [x] Pantalla de reportes agrupada por módulo, con atajos de periodo (7 y 30 días, este mes, mes anterior, gestión), contador de filtros aplicados y «Limpiar filtros».
- [x] El encabezado de cada archivo describe los filtros aplicados; la auditoría registra los filtros usados.
- [x] PDF con ancho de columnas según el contenido.
- [x] 10 pruebas de backend (132 en total) y 2 de frontend (19 en total); probado en el navegador como directora.

### Estética según DESIGN.md
- [x] Paleta crema / espresso / ámbar, sombras cálidas, radios de 8 px y 4 px, Inter Variable (local) con pesos 492 y 584 e interlineado ≤ 1,25, todo mediante los tokens de `index.css`.
- [x] Botón principal ámbar con sombra del documento; botón secundario con borde espresso; enlaces espresso con subrayado ámbar.
- [x] Portada del inicio de sesión, favicon, color de la barra del navegador y encabezados de los reportes Excel/PDF con la nueva paleta.
- [x] Modo oscuro adaptado a la misma paleta; contraste de texto verificado; revisado en el navegador.

### Exportación por módulo y análisis estadístico
- [x] Se eliminó el módulo «Reportes»: cada módulo exporta sus reportes (Excel, PDF, CSV) con sus filtros desde su propia pantalla.
- [x] Inventario: los dos botones CSV fijos se reemplazaron por la exportación con filtros (6 reportes).
- [x] Nuevo módulo «Análisis estadístico»: captación, variables ambientales, correlaciones con la captación, calidad de datos, incidencias, mantenimientos e inventario, con filtros de periodo, atrapanieblas y dispositivo.
- [x] 4 pruebas de backend (136 en total); probado en el navegador como directora.

### Análisis estadístico: más gráficos e interactividad
- [x] Captación diaria con vista de barras, línea o acumulado, media móvil de 7 días (opcional) y línea de la media.
- [x] Histograma de la captación diaria, barras divergentes de correlación (clic para seleccionar) y diagrama de dispersión con recta de tendencia y selector de variable.
- [x] Barras horizontales para captación por atrapanieblas, calidad de las lecturas, incidencias (estado y prioridad) y mantenimientos (tipo y estado final).
- [x] Información al pasar el cursor en todos los gráficos y opción «Ver tabla» en cada uno.
- [x] Colores validados para daltonismo en claro y oscuro; 3 pruebas de frontend (cálculos) y 1 de backend.

### Módulo de atrapanieblas (integrado con IoT)
- [x] Pantalla «Atrapanieblas» con plano de ubicación offline (norte, escala, selección), resumen y una ficha por atrapanieblas.
- [x] Ficha: ubicación y coordenadas, altitud, malla, orientación, instalación, estado derivado de sus estaciones IoT, captación de 7 días con minigráfico, rendimiento L/m²·día, nivel del tanque, incidencias abiertas y último mantenimiento.
- [x] Edición de datos técnicos y coordenadas para el administrador; exportación de reportes desde la pantalla.
- [x] Migración `dd5c474a8961` (columna opcional `orientation`); 1 prueba de backend (137 en total).

### Nueva estética según DESIGN.md («Visual»)
- [x] Paleta crema / negro / oliva-salvia con carbón para la acción principal y amarillo solo decorativo; diseño plano sin sombras.
- [x] Fraunces (titulares e indicadores) e IBM Plex Mono (interfaz), locales; radios de 3 px y 8 px.
- [x] Encabezados con la marca editorial negra y amarilla; ítem activo del menú con trazo amarillo; portada del inicio de sesión en carbón.
- [x] Colores de gráficos revalidados (oliva / ocre); favicon, barra del navegador y reportes Excel/PDF actualizados; modo oscuro adaptado.

## 2026-10-20

### Estilo pastel sobrio y diferenciación visual
- [x] Paleta pastel (azul, menta, durazno, lavanda, rosa) con contraste verificado en modo claro y oscuro; tipografía sans del sistema; `DESIGN.md` actualizado con las reglas vigentes.
- [x] Tarjetas de indicadores con color de acento, encabezados de tarjeta con fondo suave, tablas con filas alternas y un color por gráfico (en el dashboard, según la variable).

### Incidencias automáticas (proceso: sistema → mantenimiento → director/administrador)
- [x] El sistema abre un reporte de incidencia cuando una estación **activa** no se comunica hace `AUTO_INCIDENT_OFFLINE_HOURS` (6 h, prioridad alta) o un sensor activo acumula `AUTO_INCIDENT_ANOMALY_THRESHOLD` lecturas rechazadas en `AUTO_INCIDENT_ANOMALY_WINDOW_HOURS` (10 en 24 h, prioridad media).
- [x] El reporte sigue el flujo normal (aceptar → iniciar → finalizar con repuestos). Avisos al personal de mantenimiento y a los supervisores; auditoría `incidencia.reportar_automatica` sin usuario.
- [x] Sin duplicados: no se abre otro de la misma causa mientras haya uno sin finalizar, ni dentro de la ventana tras finalizarlo. Bloqueo consultivo de PostgreSQL para varios procesos de la API.
- [x] Revisión periódica dentro de la API cada `AUTO_INCIDENTS_INTERVAL_MINUTES` (15 min; sin cron ni colas) y a demanda con `python -m app.cli check-incidents`.
- [x] Migración `7b3e9c1d2a40`: `incident_reports.source` (`usuario`/`sistema`), `auto_cause` y autor opcional solo para reportes del sistema (restricción CHECK); el downgrade se niega si hay reportes automáticos. Probada en ambos sentidos.
- [x] Frontend: insignia «Automática» y «Detectado por el sistema» en la lista, el detalle y la línea de tiempo; exportación con autor «Sistema (detección automática)».
- [x] 4 pruebas de backend (141 en total) y 1 de frontend (23 en total).

### Filtros en la vista principal y exportación directa
- [x] Cada módulo muestra sus filtros en la propia pantalla (componente `FilterToolbar`): el listado se actualiza con ellos y «Exportar» descarga el reporte elegido con esos filtros y el formato indicado (Excel, PDF o CSV), sin ventana intermedia. Los filtros propios de un reporte (agrupación, periodo de inventario, repuesto del kardex…) aparecen junto al botón al elegirlo; si falta uno obligatorio, el botón queda deshabilitado con aviso.
- [x] Dashboard: el botón exporta lo que muestra el gráfico (variable, periodo y agrupación). Incidencias: los filtros respetan cada vista (p. ej. «Mis reportes» siempre son los propios).
- [x] Backend: los listados aceptan los filtros de su reporte — incidencias (prioridad, dispositivo, fechas, autor, responsable), mantenimiento (estado final, responsable, origen), usuarios (rol, cargo), dispositivos (atrapanieblas) y repuestos (estado, solo stock bajo, incluir desactivados).
- [x] 5 pruebas de backend (146 en total) y 1 de frontend (24 en total); verificado en el navegador (filtro de stock bajo → CSV con el mismo repuesto).

### Reubicación de atrapanieblas (proceso: docente → mantenimiento → director/administrador)
- [x] Un docente solicita mover un atrapanieblas (motivo: espacio insuficiente, interferencia con otras actividades, obstrucción de la niebla u otro), con descripción y un lugar sugerido opcional (ubicación registrada o lugar aún no registrado). Se guarda la ubicación de origen.
- [x] Mantenimiento acepta → inicia el traslado → finaliza indicando la nueva ubicación y, si cambia, la orientación de la malla; el atrapanieblas y sus estaciones IoT pasan a esa ubicación con historial (`device_locations`). Antes de iniciar puede rechazarla con un motivo. Avisos internos al solicitante en cada etapa y auditoría `reubicacion.*`.
- [x] Reglas: una sola solicitud en curso por atrapanieblas (índice único parcial), el atrapanieblas debe estar activo y el destino debe ser una ubicación activa distinta de la actual. Mientras hay una solicitud en curso, la edición directa no puede cambiar la ubicación ni desactivar el atrapanieblas.
- [x] Permisos `reubicaciones.solicitar` (docente, director, administrador), `reubicaciones.atender` (mantenimiento, administrador) y `reubicaciones.supervisar` (director, administrador). Migración `c41f2a7d9e10` probada en ambos sentidos.
- [x] Frontend: pantalla «Reubicaciones» con pestañas por rol, contador en el menú, enlace desde la ficha del atrapanieblas y desde la campana de avisos.

### Validación de formularios y datos dependientes
- [x] Formularios de atrapanieblas, dispositivo, sensor, edición del atrapanieblas, periodo de inventario y movimientos con validación previa al envío, con las mismas reglas que el backend.
- [x] Datos que dependen de otro formulario: la estación toma por defecto la ubicación de su atrapanieblas; el sensor usa el atrapanieblas de su dispositivo y solo ofrece tanques de ese atrapanieblas; el volumen captado exige atrapanieblas y el nivel exige tanque; el código de sensor no se repite en el dispositivo; una salida o un repuesto de mantenimiento no supera el stock (y no se repite); la fecha final del periodo no es anterior a la inicial; las coordenadas van juntas; sin fechas futuras.
- [x] Backend: las referencias (ubicación, atrapanieblas, tanque) deben existir y estar activas; sensor y tanque deben corresponder al atrapanieblas del dispositivo; latitud y longitud juntas; fecha de instalación no futura.
- [x] 16 pruebas de backend (162 en total) y 5 de frontend (29 en total); flujo verificado en el navegador sobre la base de pruebas.
- [x] Datos de demostración: `seed-demo` agrega 3 reubicaciones (rechazada, finalizada y pendiente) y, sobre una base ya cargada, completa las lecturas simuladas hasta la hora actual en vez de fallar.

### Alertas de incidencia según prioridad
- [x] **Alta**: aviso en pantalla que bloquea toda la interfaz (sin cerrar con Escape ni clic fuera) hasta que el usuario pulsa «Revisar alerta», que la marca como revisada y abre el reporte. Cada usuario avisado la revisa por su cuenta; deja de bloquear si alguien acepta el reporte. Auditoría `incidencia.revisar_alerta`.
- [x] **Media**: recordatorio en la pantalla «Reportes de incidencia» y en el detalle de la alerta mientras siga abierta; se puede posponer 15 min y vuelve a aparecer.
- [x] Solo reciben alertas los usuarios avisados del reporte (mantenimiento; supervisores en las detectadas por el sistema). Sin migración: la revisión usa los avisos existentes.
- [x] API: `GET /api/v1/incidents/alerts` y `POST /api/v1/incidents/{id}/review`.
- [x] 2 pruebas de backend y 1 de frontend.

## 2026-11-12

### Revisión de la rama `reubicacion-atrapanieblas`
- [x] Trabajo sin confirmar de la rama (reubicaciones, validación de formularios, alertas por prioridad) verificado: 164 pruebas de backend y 30 de frontend en verde, sin errores de lint ni de tipos.

### Estación meteorológica DHT11 + BME280
- [x] Firmware 0.2.0: BME280 (temperatura, humedad y presión; I²C en GPIO 27/26, dirección 0x76) como fuente principal y DHT11 (GPIO 25) como respaldo de temperatura y humedad; un sensor sin lectura se envía como `null`.
- [x] Detecta un BMP280 vendido como BME280 (sin humedad) y en ese caso toma la humedad del DHT11; reintenta conectar el BME280 si deja de responder.
- [x] Pines del pluviómetro (GPIO 32) y del sensor de nivel (GPIO 18/19) reasignados para respetar el cableado del prototipo; tipo de DHT configurable (`-DDHT_TYPE=DHT22`).
- [x] Bibliotecas con versión fija (ArduinoJson 7.2.1, BME280 3.0.0, DHT sensor library 1.4.7). Compila: 1 MB de 1,25 MB.
- [x] El sketch de prueba en banco se conservó en `firmware/pruebas/prueba_sensores.cpp`, fuera de la compilación.
- [x] Documento de conexiones: `docs/conexiones_sensores_esp32.md` (pines, esquema, divisor de tensión, abrigo ventilado, verificación al encender).

### Módulo de carga de firmware (actualización OTA por la red local)
- [x] Pantalla «Firmware de estaciones» (permiso `firmware.gestionar`: administrador y mantenimiento): cargar el `firmware.bin`, ver las versiones cargadas y asignar una versión por estación con su estado (al día, pendiente de instalar, sin asignar).
- [x] El servidor valida el archivo: imagen de aplicación ESP32 (byte 0xE9 y chip ESP32), tamaño máximo de una ranura OTA (1,25 MB) y versión leída de la marca `ATINA-FW:<versión>;` compilada en el firmware (no se escribe a mano); no admite versiones repetidas.
- [x] La imagen se guarda en PostgreSQL (entra en los respaldos) con SHA-256 y MD5; las versiones no se eliminan y permiten volver atrás.
- [x] El ESP32 consulta `GET /api/v1/iot/firmware` con su credencial al arrancar y como máximo cada hora; recibe 304 si ya ejecuta la versión asignada o 200 con la imagen y la cabecera `x-MD5`, que verifica antes de instalar.
- [x] Auditoría: `firmware.cargar`, `firmware.asignar` y `firmware.descargar`. Migración `106d673f7a40` probada en ambos sentidos (el downgrade se niega si hay versiones cargadas).
- [x] 4 pruebas de backend (168 en total) y 1 de frontend (31 en total). Verificado de punta a punta: carga del `firmware.bin` real desde el navegador como técnico de mantenimiento, asignación y descarga simulada del ESP32 (imagen idéntica y MD5 correcto; 304 con la versión ya instalada).

### Módulo provisional: estimación de volumen con el modelo de ML y datos en vivo
- [x] Pantalla «Estimación de volumen» (menú Principal), visible para **cualquier rol**, con la marca «Provisional» y el aviso de que el modelo (`sim-0.1.0`) se entrenó con datos simulados y no sirve aún para planificar el riego.
- [x] Para cada estación **conectada** (activa y con comunicación en los últimos 30 min) estima el volumen de hoy con los datos del día de ayer completo; muestra junto a la estimación la referencia simple (media de 7 días), lo captado hoy hasta el momento y las variables usadas. Sin estaciones conectadas: «Sin datos disponibles». Sin datos suficientes: lo informa y no muestra un número.
- [x] Marca interna `PROVISIONAL` en `backend/app/business/ml/prediction_service.py`; endpoint `GET /api/v1/ml/provisional` (no ocupa las rutas `/predictions` reservadas para el modelo de producción). Las estimaciones no se guardan.
- [x] El cálculo de variables y las reglas de inferencia se movieron de `notebooks/simulacion` a `backend/app/business/ml/` (`features.py`, `inference.py`) y la simulación los importa: entrenamiento y API usan el mismo código. Reentrenada con métricas idénticas.
- [x] Corrección: «horas con humedad ≥ 95 %» y «horas con niebla ≥ 40 %» quedan vacías (no 0) en un día sin lecturas de esa variable (p. ej. una estación DHT11 + BME280 sin sensor de niebla).
- [x] El volumen se lleva a la escala de la malla de entrenamiento (40 m²) y la estimación vuelve a la malla de cada atrapanieblas.
- [x] Artefacto cargado desde `backend/artifacts/` (ruta configurable `ML_ARTIFACT_PATH`); si falta o fue entrenado con otra versión de scikit-learn, el módulo lo informa. Dependencias del backend: scikit-learn 1.9.1 (fija, igual que el entrenamiento), pandas y joblib.
- [x] 4 pruebas de backend (172 en total) y 2 de frontend (33 en total). Verificado con el artefacto real sobre la base de pruebas con datos de demostración: estación conectada con estimación de 13,3 L, vista como docente.

### Primera carga del firmware y arranque en red
- [x] Firmware 0.2.0 grabado por USB en el ESP32 (ESP32-D0WDQ6, `/dev/ttyUSB0`) con verificación; arranca y espera la configuración por consola serie.
- [x] `iniciar_red.sh`: igual que `iniciar.sh` (sin cambios) pero con la API y el frontend accesibles desde la red local, para que las estaciones ESP32 envíen datos; muestra la IP del equipo y la `api_url` para el ESP32. Verificado desde la IP de red: API 200, lote sin credencial 401, frontend 200.

### Panel de estaciones en línea / sin conexión
- [x] Indicador en el menú lateral, visible en todas las pantallas: «Estaciones: N en línea · M sin conexión» (contraído: icono con punto rojo si alguna está sin conexión). Al pulsarlo abre un panel con cada estación, su estado (en línea, sin conexión, en mantenimiento) y su último envío; se actualiza cada 30 s. Usa la misma consulta del resumen general (sin endpoint nuevo).

### Pruebas unitarias de funciones críticas (informe)
- [x] `backend/tests/test_unitarias_criticas.py`: 30 casos en patrón Arrange-Act-Assert, sin base de datos, para las 5 funciones más críticas: `InventoryService.apply_movement` (stock; repositorios con `unittest.mock`), `assess_value` (lecturas IoT, null ≠ 0), `hash_password`/`verify_password`, `firmware_version` (OTA) y `predict` (ML, datos insuficientes). Suite completa: 202 aprobadas.
- [x] Informe: sección 5.4.2.2 «Pruebas unitarias» en `docs/Documentos/informe_software.docx` (tablas AAA, código de cada función y de sus pruebas, capturas de ejecución), PDF completo y `pruebas_unitarias.pdf` con solo la sección. Índice general, de figuras y de tablas regenerados con las páginas del PDF.

### Informe final según el índice nuevo (`INDICE DE PROYECTO INTEGRADOR II.xlsx`)
- [x] Editado con WordCraft (respaldo: `informe final (respaldo antes de correcciones).docx/.pdf`). Agregados: definición de machine learning y del modelo adoptado (1.9, 1.9.17), sensores y hardware del prototipo (1.8.1.1–1.8.1.3, 1.8.3.1–1.8.3.2), 2.4 Justificación legal, objetivo general, 5.3.1.1 Paquetes, 5.3.1.4 Colaboración, 5.3.1.8 Mapa navegacional, 5.3.1.9.1–3 (estilo, cambios, middleware), 5.4 Desarrollo del Aporte Ingenieril (prototipo, sistema web, modelo, seguridad, pruebas con pruebas unitarias), V. Glosario, Anexo 1 (encuesta) y Anexo 4 (Ishikawa y árbol de problemas).
- [x] Bibliografía: ediciones más recientes de los libros, «s. f.» → 2026, fuentes nuevas (Géron 2025, datasheets, normativa boliviana, Cronbach, Wilcoxon). Diagramas nuevos en `docs/diagramas/complementos_informe.drawio` (generador: `generar_complementos.py`).
- [ ] Aplicar la encuesta del Anexo 1 y completar la tabulación, las gráficas y su interpretación.
- [ ] Revisar contenido heredado que no corresponde al alcance: Anexo 3 (diccionario con riego, actuadores, MCP), tabla de caja negra (2FA, invernaderos, riego, alertas, umbrales, tickets), 1.2.3 (MCP), 2.1/2.3/3.3.1 (BME680, caudalímetro, biblioteca), y los PERT del Anexo 2 que se salen del margen.

### Monitoreo en vivo e intervalo de muestreo
- [x] Página **Monitoreo en vivo** (`/monitoreo`, permiso `dashboard.consultar`): medidores semicirculares por variable (valor actual, mínimo y máximo de la ventana, banda de niebla ≥ 95 % en la humedad), tendencia, antigüedad de la lectura en segundos, estado En vivo / Retrasada / Sin conexión y un gráfico por variable con promedio y cortes donde faltan lecturas. Ventanas de 15 min, 1 h y 6 h; se actualiza al ritmo del muestreo.
- [x] Intervalo de muestreo por estación (`devices.sample_interval_s`: 5 «tiempo real», 30 o 60 s; migración `5b1e9c3d2a47`). Se cambia con `PUT /devices/{id}` (permiso `infraestructura.gestionar`, auditado) y viaja en la respuesta de cada lote. Endpoint `GET /dashboard/live`.
- [x] Firmware 0.3.0: aplica el intervalo recibido y lo guarda en NVS; `sample_s` por serie acepta 5–3600 s.
- [ ] Instalar el firmware 0.3.0 en la estación (OTA desde «Firmware de estaciones» o USB). La placa de banco necesita compilarse con `-DDHT_TYPE=DHT22`.
- [ ] Con «Tiempo real» se guardan 12 lecturas por minuto de cada variable (~52 000 filas/día por estación con 3 variables): usarlo para observar eventos, no de forma permanente, o definir una política de retención.

### Revisión de seguridad del inicio de sesión
- [x] Verificado: el token de sesión viaja solo en una cookie HttpOnly + SameSite=Strict (path `/api`), nunca en el cuerpo, otras cabeceras, almacenamiento del navegador ni auditoría; en la base se guarda su HMAC. Mismo mensaje para usuario inexistente, contraseña incorrecta, cuenta bloqueada o inactiva.
- [x] Corregido: la cuenta bloqueada respondía sin calcular el hash (el tiempo delataba el bloqueo); límite de 20 intentos fallidos por equipo (IP) cada 15 min → 429; el frontend cierra la sesión local ante cualquier 401 (sesión vencida o revocada) y borra los datos en memoria; el formulario valida los mismos largos máximos que la API; Nginx aplica las cabeceras de seguridad también en `/assets` y `/api` (antes se perdían) y marca la API como `no-store`.
- [ ] Servir el sistema por HTTPS en la red local (certificado de una CA interna) y activar `COOKIE_SECURE=true`: hoy la contraseña y la cookie viajan sin cifrar por el Wi-Fi.

### Revisión de validaciones y reglas de negocio por módulo
- [x] Verificado: la ingesta IoT valida unidad, rango, NaN/infinito, fecha futura, sensor asociado y activo, dispositivo activo y duplicados; el inventario no permite salidas mayores al stock, traza cada movimiento y bloquea periodos cerrados; mantenimiento valida el sensor del dispositivo y descuenta los repuestos; usuarios no deja el sistema sin administradores ni permite autodesactivarse; la recuperación exige verificar la identidad; las reubicaciones bloquean el cambio directo de ubicación.
- [x] Corregido: los filtros de fecha de todas las consultas exigen zona horaria (series, análisis y exportación de reportes daban 500; el resto la interpretaba de forma ambigua); nombres y apellidos deben tener al menos una letra («   » daba 500, «--» se guardaba), también en el formulario; la unidad de un repuesto con movimientos ya no se puede cambiar; finalizar una incidencia sin indicar el dispositivo conserva el sensor reportado; un atrapanieblas nuevo solo admite orientaciones cardinales (N…NO), igual que la reubicación. Pruebas en `tests/test_validaciones_modulos.py`.
- [x] Decidido e implementado: el estado final del mantenimiento cambia el del componente atendido (sensor, o dispositivo si no se indicó sensor): «fuera de servicio» → `mantenimiento` (no acepta lecturas), «reemplazado» → `inactivo` (lo reactiva el administrador al instalar la unidad nueva), «operativo» devuelve a `activo` uno que estaba en mantenimiento. Queda en auditoría.
- [x] Decidido: `/ml/provisional` sigue abierto a cualquier usuario autenticado por ahora (el permiso `predicciones.consultar` se usará con el modelo de producción).
- [ ] Menor: un mantenimiento acepta fechas muy antiguas (p. ej. 1990); enviar `null` en un campo obligatorio de una edición responde con el mensaje genérico «Los datos no cumplen las restricciones del sistema».

### Flujos de proceso más intuitivos (incidencias y reubicaciones)
- [x] Recuadro «Siguiente paso» arriba del detalle: dice a quién le toca, qué ocurrirá y tiene los botones ahí mismo (antes las acciones quedaban al final del diálogo y no se decía quién debía actuar). Lógica en `frontend/src/lib/flow.ts` con pruebas.
- [x] En las listas, la marca «Su turno: aceptar / iniciar / finalizar» en los casos que esperan una acción de quien mira.
- [x] Atajo «Aceptar e iniciar ahora» para quien atiende un reporte estando ya en el lugar; los formularios de finalizar y rechazar se abren bajo el recuadro y se pueden cancelar.
- [x] El formulario de mantenimiento explica qué le pasará al sensor o dispositivo según el estado final elegido.

### Revisión visual: pastel suave y lectura cómoda
- [x] Auditoría medida: contraste de todos los pares de color del tema (texto ≥ 4,5:1 en claro y oscuro), tamaños de letra, opacidad sobre texto, mayúsculas sostenidas y colores fijos en componentes.
- [x] Gráficos con ~25 % menos de saturación (azul, durazno, lavanda, verde y rosa), validados con contraste ≥ 3:1 y separación para daltonismo; real vs. estimado sigue en azul/durazno.
- [x] Texto pequeño de 12 a 13 px en toda la interfaz, ejes de gráficos de 11 a 12 px, descripciones limitadas a ~70 caracteres por línea, sin texto atenuado con opacidad en avisos.
- [x] Botones secundarios con borde gris azulado en lugar de casi negro (filas de inventario, atajos de fecha); marca del menú activo con contraste ≥ 3:1.
- [x] Filtros plegables: en celular empiezan plegados para que la lista quede a la vista.
- [x] `DESIGN.md` actualizado con estas reglas.

### Confirmaciones en modales (sin `confirm()` del navegador)
- [x] Componente `ConfirmDialog` (título, consecuencias, «Cancelar» y la acción con su nombre real; no se cierra mientras procesa).
- [x] Usuarios: «Restablecer clave» y «Desactivar» en modal; la contraseña temporal (también la de un usuario nuevo) se muestra dentro del modal con botón copiar.
- [x] Recuperación de cuentas: «Resolver» abre un modal (verificar identidad, aprobar o rechazar) y muestra ahí la contraseña temporal.
- [x] Dispositivos: «Nueva API key» y «Desactivar» en modal; la API key nueva o de un dispositivo nuevo, dentro del modal.
- [x] Inventario: «Desactivar» repuesto y «Cerrar periodo» en modal; el cierre avisa antes de intentarlo si falta contar repuestos, si el periodo no terminó o si hay conteos sin guardar (mismas reglas del backend).
- [x] Revisión visual de los modales en el navegador (restablecer clave, API key, desactivar repuesto).
- [x] Al hacer capturas, la API de prueba usó la base de desarrollo: quedaron revisadas las alertas altas #8, #9 y #13 de `rmamani`, 7 inicios de sesión y 2 intentos fallidos de `pcondori`. Decidido: se dejan como están.

### Paleta verde y crema
- [x] Nueva paleta: verde bosque `#2B4D3B` (texto), salvia `#6E9B7B` (acento del menú), salvia clara `#B9D2C2` (acción principal), arena `#E7D7C7` (superficies secundarias) y crema `#FBF7F1` (fondo), con su versión oscura. Todo el texto ≥ 5,2:1 (claro) y ≥ 7,5:1 (oscuro); foco y bordes de campos ≥ 3:1.
- [x] Gráficos revalidados en ambos temas: verde para la serie principal, azul/arcilla para real vs. estimado.
- [x] Ícono de la pestaña y color de barra del navegador con la paleta; `DESIGN.md` actualizado.
- [x] Revisadas las pantallas internas y los modales con la nueva paleta (servidor de prueba sobre `atrapanieblas_test`, verificado).

## Revisión del informe final (2026-11-18)

- [x] Respaldo previo: `docs/Documentos/informe final (respaldo antes de revisión 2026-11-18).docx/.pdf`.
- [x] Capítulo 5 reorganizado según el índice: fases y sprints (Tabla 6), roles Scrum, 37 RF, 14 RNF, 22 historias de usuario con criterios de aceptación, Product Backlog y Sprint Backlog de los 5 sprints con revisión, retrospectiva y velocidad.
- [x] Diagramas de clases de alto y bajo nivel y diagrama físico regenerados desde los modelos reales (`docs/diagramas/generar_diagramas_datos.py`), cada uno en página horizontal.
- [x] Diccionario de datos (Anexo 3) rehecho con las 39 tablas reales; tablas en formato APA; listas de tablas/figuras e índice automáticos.

## Gráficos y exportación institucional por módulo (2026-11-19)

- [x] Cada reporte calcula su resumen y gráficos desde sus mismas filas (`report_charts.py`); `GET /api/v1/reports/charts` los entrega a la web.
- [x] Cada módulo muestra «Resumen y gráficos» del reporte elegido en la barra de filtros (mismo reporte y filtros que la exportación), con vista de tabla.
- [x] PDF institucional: encabezado, criterios, resumen, figuras vectoriales numeradas, tabla de detalle y pie «Página X de Y». Excel: hoja «Resumen y gráficos» con gráficos nativos + hoja «Detalle» con autofiltro. CSV: solo datos.
- [x] Nuevo filtro «Comunicación» (al día / desactualizado / sin comunicación) en dispositivos y en el reporte de estaciones.
- [ ] Revisar visualmente las pantallas y un Excel exportado en el equipo (no se pudo abrir navegador ni LibreOffice en la sesión).

## Primera instalación del ESP32 desde el módulo de firmware (2026-11-19)

- [x] Escritura por USB desde el navegador (esptool-js + Web Serial): bootloader, particiones, boot_app0 y la versión elegida, verificados con SHA-256.
- [x] Configuración automática por puerto serie (Wi-Fi, servidor, NTP, identificador y API key nueva que no se muestra).
- [x] Nginx con HTTPS (443) y certificado propio; el puerto 80 queda para las estaciones.
- [x] Probado con un ESP32 real (`esp32-04`, placa con CP2102): escritura y configuración desde el navegador.
- [ ] Probar el despliegue con `docker compose` en el servidor (HTTPS y estaciones por el puerto 80).

## Exportación del análisis estadístico y tonos de contraste (2026-11-19)

- [x] El análisis estadístico se exporta (`report=analisis`) en Excel, PDF y CSV, con los mismos indicadores de la pantalla y cada sección según los permisos del usuario.
- [x] Tonos de contraste en la paleta: verde bosque para la acción principal y arcilla para lo que pide actuar («Le toca a usted», «Su turno», avisos sin leer); documentado en `DESIGN.md`.

## Estación real `esp32-04` en funcionamiento (2026-11-19)

- [x] Datos precargados en la primera instalación (`STATION_WIFI_SSID`, `STATION_WIFI_PASSWORD`, `STATION_API_URL`, `STATION_NTP_SERVER`); la contraseña Wi-Fi nunca se muestra. `iniciar_red.sh` calcula la dirección de envío con la IP del equipo.
- [x] Aviso para Brave (Web Serial desactivado) y botón **Solo configurar** para un ESP32 que ya tiene el firmware.
- [x] Corregido: al abrir el puerto, el navegador dejaba el ESP32 retenido en reinicio (DTR/RTS); la credencial se emite solo cuando el ESP32 ya respondió.
- [x] Firmware 0.3.1–0.3.4: lector propio del DHT (la biblioteca de Adafruit reiniciaba el ESP32 en bucle si el sensor no respondía), primer intento de Wi-Fi inmediato, comando `sensores` de diagnóstico y reconocimiento del formato DHT11/DHT22 por el contenido (el sensor instalado responde en formato DHT22).
- [x] Lecturas reales llegando: temperatura y presión (BMP280, sin humedad) y humedad (DHT).
- [x] Versión inicial y correcciones cargadas en el sistema; `esp32-04` tiene asignada la 0.3.4.
- [x] `seed-demo` completó las lecturas simuladas de las estaciones de demostración hasta la fecha, para que el modelo provisional estime (`esp32-01`).
- [x] Búsqueda de conjuntos de datos para entrenar el modelo (sin descargar): no hay datos públicos de volumen de atrapanieblas con clima horario en los Andes; útiles como apoyo ERA5-Land/NASA POWER (clima de la zona) y Alto Patache, Gobabeb y Monterey (relación clima–captación).

## Detección de pérdida de conexión en todos los módulos (2026-11-24)

- [x] Regla única de conexión en `backend/app/business/rules/connection.py`: sin conexión tras 3 intervalos de envío + 60 s (tope `DEVICE_STALE_MINUTES`). Antes solo Monitoreo lo notaba; el resto esperaba 30 min.
- [x] La usan Dispositivos (lista y filtro «Comunicación»), el resumen y el menú lateral, el Dashboard, Monitoreo, Atrapanieblas y el reporte de estaciones.
- [x] La lista de Dispositivos y `useDevices` se refrescan cada 30 s.
- [x] `refreshStations`: activar/desactivar, mantenimiento, finalizar incidencia, cambiar el intervalo de envío y asignar o instalar firmware actualizan a la vez todos los módulos que muestran estaciones.
- [x] Pruebas: `tests/test_connection_rule.py` (todos los módulos ven igual a una estación sin comunicación) y `features/devices/api.test.ts`.

## Pendiente

- [ ] Publicar el artefacto en el servidor: `backend/artifacts/` no se versiona; copiar `notebooks/simulacion/salidas/modelo_sim-0.1.0.joblib` (se regenera con `simulacion/ejecutar.py`).
- [ ] **Fases 9–11 (ML de producción)** — pendiente por decisión del usuario (hoy existe solo el módulo provisional). La simulación ya probó el flujo. Falta confirmar el horizonte de predicción y las variables de entrada (exigido por `AGENTS.md`) y reunir al menos un año de datos reales. Luego: tablas `ml_models` y `predictions` (migración Alembic), notebook de preparación de datos, entrenamiento con validación temporal, artefacto versionado, servicio de predicción, `POST/GET /api/v1/predictions` y `GET /api/v1/predictions/comparison`, y reporte real vs. estimado.
- [ ] Calibraciones de sensores: la tabla existe, falta su API y pantalla.
- [ ] Gestión de respaldos desde el panel (permiso `respaldos.gestionar`); hoy se hace con los scripts.
- [ ] Levantar el despliegue con `docker compose up` y ejecutar `test-restore.sh` en el servidor institucional.
- [ ] Calibrar `LITERS_PER_PULSE`, la altura del sensor del tanque y la presión con el hardware real (en el sitio debe rondar 690 hPa; en el laboratorio el BMP280 marca ~661 hPa).
- [ ] Probar la actualización OTA en el ESP32 real (`esp32-04` ya tiene la 0.3.4: cargar una 0.3.5 y asignársela desde el sistema).
- [ ] Reconfigurar `esp32-04` con **Solo configurar**: la IP del equipo de desarrollo cambió (10.1.15.179 → 10.1.8.63) y la estación quedó sin comunicación.
- [ ] Servidor institucional con IP fija y servidor de hora local (`STATION_NTP_SERVER`); hoy las pruebas usan `pool.ntp.org`, que requiere Internet.
- [ ] `esp32-04`: agregar el sensor de volumen (pluviómetro, GPIO 32) y asignarle un atrapanieblas para que el modelo pueda estimar con datos reales.
- [ ] El sensor de presión instalado es un BMP280 (no mide humedad): la humedad depende del DHT. Separar el BMP280 del ESP32 (marca ~2 °C de más por el calor de la placa).
- [ ] Recrear el contenedor Docker de pruebas `atrapanieblas-smoke` (Nginx se reinicia en bucle: le faltan el certificado y `api-proxy.conf`).
- [ ] Quitar de `firmware/platformio.ini` las bibliotecas DHT de Adafruit si ya no se usa `pruebas/prueba_sensores.cpp`.
- [ ] Completar el perfil del usuario `admin` (CI, apellido, celular y fecha de nacimiento) desde **Mi perfil → Editar datos**.
- [ ] Revisar con la institución el catálogo inicial de instituciones de egreso y cargos, y las edades mínimas de egreso por nivel.
- [ ] Para la futura comparativa real vs. estimado (ML): real en terracota y estimado con línea discontinua en Bark, validando que se distingan.
- [ ] Las lecturas de la base de desarrollo son simuladas: no usar esa base para entrenar el modelo real.
- [ ] Actualizar los diagramas UML y de casos de uso (roles `docente`/`director` y nuevo flujo de mantenimiento). Los de clases y el físico ya se actualizaron (2026-11-18).
- [ ] Informe: completar la revisión del Sprint 5, aplicar la encuesta del Anexo 1, agregar Gantt al Anexo 2 y revisar las referencias no citadas.
- [ ] Opcional: dividir el bundle del frontend por rutas (hoy ~1 MB, aceptable en red local).
- [ ] **Proceso: solicitud de reposición de repuestos** (pendiente de aprobación del alcance). Mantenimiento o el sistema (stock mínimo) crea la solicitud → el director la aprueba o rechaza → el administrador registra la entrada al recibirla → se cierra. Estados `pendiente → aprobada/rechazada → recibida`, auditoría. Requiere tabla nueva con migración.
- [ ] **Proceso: calibración de sensores** (tabla `sensor_calibrations` ya existe). El sistema avisa la calibración vencida → mantenimiento la realiza y registra valores de referencia y resultado → el administrador la valida; si falla, se abre una incidencia.
- [ ] **Proceso: plan de mantenimiento preventivo.** Director/administrador programa tareas periódicas (p. ej. limpieza de malla cada 2 semanas) → aviso a mantenimiento al vencer → se ejecuta con el flujo existente → el director ve el cumplimiento (a tiempo / atrasadas).
- [ ] **Proceso: activación controlada de una versión del modelo ML** (después de las fases 9–11). Administrador entrena y registra métricas → director aprueba el paso a producción → se conserva la versión anterior para comparar.
- [ ] Incidencias automáticas: ajustar los umbrales con la institución según el comportamiento real de las estaciones.
