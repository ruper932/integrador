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

## Pendiente

- [ ] **Fases 9–11 (ML de producción)** — pendiente por decisión del usuario. La simulación ya probó el flujo. Falta confirmar el horizonte de predicción y las variables de entrada (exigido por `AGENTS.md`) y reunir al menos un año de datos reales. Luego: tablas `ml_models` y `predictions` (migración Alembic), notebook de preparación de datos, entrenamiento con validación temporal, artefacto versionado, servicio de predicción, `POST/GET /api/v1/predictions` y `GET /api/v1/predictions/comparison`, y reporte real vs. estimado.
- [ ] Calibraciones de sensores: la tabla existe, falta su API y pantalla.
- [ ] Gestión de respaldos desde el panel (permiso `respaldos.gestionar`); hoy se hace con los scripts.
- [ ] Levantar el despliegue con `docker compose up` y ejecutar `test-restore.sh` en el servidor institucional.
- [ ] Calibrar `LITERS_PER_PULSE` y la altura del sensor del tanque con el hardware real.
- [ ] Completar el perfil del usuario `admin` (CI, apellido, celular y fecha de nacimiento) desde **Mi perfil → Editar datos**.
- [ ] Revisar con la institución el catálogo inicial de instituciones de egreso y cargos, y las edades mínimas de egreso por nivel.
- [ ] Para la futura comparativa real vs. estimado (ML): real en terracota y estimado con línea discontinua en Bark, validando que se distingan.
- [ ] Las lecturas de la base de desarrollo son simuladas: no usar esa base para entrenar el modelo real.
- [ ] Actualizar los diagramas UML y de casos de uso (roles `docente`/`director` y nuevo flujo de mantenimiento).
- [ ] Opcional: dividir el bundle del frontend por rutas (hoy ~1 MB, aceptable en red local).
