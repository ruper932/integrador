# Decisiones técnicas

Registro de decisiones tomadas durante la implementación. Cada una puede revisarse.

## Arquitectura

- Monolito modular FastAPI en tres capas: `presentation` (routers y esquemas Pydantic),
  `business` (servicios, reglas), `data` (modelos y repositorios SQLAlchemy).
- Los servicios reciben un `RequestContext` (usuario, IP) para autorizar y auditar.
- Cada operación de escritura es una transacción: si una regla falla, nada se guarda
  (por ejemplo, un mantenimiento sin stock suficiente no deja registros parciales).

## Identificadores

- Enteros autoincrementales para entidades; UUID para `batch_id` y `message_id` de mediciones.

## Seguridad

- **Contraseñas**: `hashlib.scrypt` (biblioteca estándar) con sal aleatoria. No se añadió
  una dependencia externa de hashing.
- **Sesiones**: token aleatorio de 256 bits en cookie `HttpOnly`, `SameSite=Strict`, `path=/api`.
  En la base solo se guarda su HMAC-SHA256 con `SECRET_KEY`, con expiración y revocación.
  El token nunca llega a JavaScript, por lo que no se guarda en `localStorage`.
- **API keys de dispositivos**: mismo esquema (HMAC), se muestran una sola vez y pueden rotarse.
- Bloqueo temporal tras 5 intentos fallidos (15 min); mensaje de error genérico.
- La IP del cliente solo se toma de `X-Real-IP` si `TRUST_PROXY_HEADERS=true` (detrás de Nginx).
- Rol complementario `mantenimiento` para otorgar a un director/docente el permiso de registrar
  mantenimientos sin darle otros permisos.

## Usuarios: modelo normalizado

- `users` guarda solo lo necesario para autenticarse. Los datos personales están en
  `user_profiles` (1:1): nombres, apellido paterno, apellido materno, CI (número, complemento y
  departamento de expedición), correo institucional, correo personal, celular, dirección y cargo.
- La formación académica está en `user_degrees` (1:N: una persona puede tener varios títulos), con
  catálogos de `academic_levels` (bachiller, técnico, maestro/a normalista, licenciatura,
  maestría…), `institutions` (instituciones de egreso) y `positions` (cargo en el CEA).
- El nombre completo no se almacena: se deriva del perfil.
- Reglas: al menos un apellido; CI numérico de 4 a 10 dígitos, único junto con su complemento;
  celular de Bolivia de 8 dígitos que inicia en 6 o 7; correo institucional único. Los nombres se
  guardan con mayúscula inicial y los correos en minúsculas.
- El catálogo inicial de instituciones está orientado a La Paz (UMSA, UPEA, ESFM “Simón Bolívar”,
  “Warisata”, “Santiago de Huata”, entre otras). Conviene que la institución lo revise; el
  administrador puede agregar instituciones desde el formulario de usuario.
- La auditoría registra qué campos del perfil cambiaron, no sus valores (CI o celular).
- **Fecha de nacimiento** obligatoria al guardar un perfil: la persona debe tener al menos 18 años
  (y no más de 100). En la base admite NULL solo para perfiles anteriores al cambio; el perfil se
  considera incompleto sin ella.
- **Año de egreso coherente con la edad**: cada nivel académico tiene una edad mínima de egreso
  (`academic_levels.min_graduation_age`): bachiller 16, técnico auxiliar 17, técnico medio 18,
  técnico superior 19, maestro/a normalista y licenciatura 21, diplomado y especialidad 22,
  maestría 23, doctorado 25. Se compara por año (año de egreso − año de nacimiento). Son valores
  razonables según la duración habitual de los estudios en Bolivia; conviene que la institución
  los revise. Al cambiar la fecha de nacimiento se revalidan los títulos ya registrados.
- La migración copió el nombre existente de cada usuario al perfil antes de eliminar
  `users.full_name`; el usuario `admin` quedó con el perfil incompleto (falta CI, apellido y celular).

## Inventario periódico

- Se combina el **sistema periódico** con el control de stock que exige `AGENTS.md` (no se permite
  una salida mayor al stock disponible):
  1. Se abren periodos (mes, trimestre o gestión) sin superposición de fechas.
  2. Al final del periodo se registra el conteo físico de cada repuesto.
  3. Al cerrar, la diferencia entre lo contado y el saldo según registros genera un ajuste
     (`ajuste_sobrante` o `ajuste_faltante`), fechado al final del periodo y trazable.
  4. Se congelan los saldos (`inventory_period_balances`); el periodo cerrado no admite movimientos
     ni conteos. Los periodos se cierran en orden y solo después de su fecha final.
- Cada movimiento tiene **fecha efectiva** (`occurred_at`) y fecha de registro (`created_at`).
- **Valorización por costo promedio ponderado** del periodo:
  (valor inicial + valor de las entradas) / (cantidad inicial + cantidad de las entradas). El
  costo unitario (Bs) se registra en las entradas; si alguna entrada no tiene costo (p. ej. una
  donación), el valor de ese repuesto queda como "sin costo" en lugar de inventarse.
- Reportes de inventario (CSV, Excel y PDF): resumen valorizado del periodo, planilla y acta de
  conteo físico con líneas de firma, kardex por repuesto, movimientos, consumo por mantenimiento y
  stock actual.

## Reportes de incidencia y flujo de mantenimiento

- Roles: `observador` se renombró a `docente` y `director_docente` a `director` (cambio pedido por el
  usuario; `AGENTS.md` describe aún los roles originales). La migración renombra, por lo que los
  usuarios conservan sus asignaciones. El docente obtuvo `infraestructura.consultar` para indicar
  qué estación falla, y `mantenimiento` dejó de ser un rol solo complementario.
- El **estado del reporte no se guarda**: se deriva del mantenimiento que lo atiende (`abierto` si no
  tiene; si no, `aceptado`, `en_progreso` o `finalizado`). Así no puede haber dos estados
  contradictorios.
- Aceptar un reporte crea el mantenimiento (`maintenance_records`) con el técnico como responsable.
  Los detalles del trabajo (dispositivo, tipo, descripción, estado final) se completan al finalizar;
  una restricción CHECK impide un mantenimiento `finalizado` incompleto. Los registros directos
  (sin reporte) se crean ya finalizados y los existentes quedaron así en la migración.
- Las etapas se recorren en orden (aceptado → en progreso → finalizado) y solo las avanza el
  personal asignado. La fecha de realización es la del momento de finalizar.
- Los repuestos se descuentan al finalizar, en la misma transacción: si falta stock, el
  mantenimiento sigue en progreso y no queda nada a medias.
- Un docente solo ve sus propios reportes; un reporte ajeno responde 404 (no revela que existe).
- **Avisos internos** (`notifications`): sin correo, SMS ni servicios externos. El frontend consulta
  al servidor local cada 30 s. Se avisa al personal con `incidencias.atender` cuando se abre un
  reporte y a quien lo reportó en cada etapa. Los avisos se marcan como leídos; no se eliminan.
- El reporte de exportación «Mantenimientos» incluye solo los finalizados y el número de reporte.

## Módulo de atrapanieblas

- Pantalla «Atrapanieblas» (permiso `infraestructura.consultar`), inspirada en la versión anterior del
  sistema (Proyecto Integrador I), que no se modificó: código, nombre, ubicación (latitud, longitud y
  altitud), malla (área y tipo), **orientación** (nueva columna opcional) y fecha de instalación.
- Integración con IoT mediante `GET /api/v1/fog-collectors/overview`: estaciones asociadas y su última
  comunicación, captación de los últimos 7 días, rendimiento (L/m²·día), nivel del tanque, reportes de
  incidencia abiertos y último mantenimiento.
- El **estado no se guarda**: se deriva de las estaciones: inactivo, sin estación IoT, en mantenimiento
  (estación en mantenimiento o incidencia en atención), sin datos recientes (todas las estaciones
  activas desactualizadas) u operativo.
- Ubicación en un **plano esquemático** (SVG) a partir de las coordenadas, con norte y escala
  aproximada; no usa mapas en línea, porque el sistema debe funcionar sin Internet.
- La edición (administrador) usa los endpoints existentes de atrapanieblas y ubicaciones.

## Reportes por módulo

- No hay una pantalla de reportes aparte: cada módulo tiene su botón «Exportar reporte» con los
  reportes y filtros que le corresponden (histórico de lecturas y resumen general, dispositivos,
  inventario, mantenimiento, reportes de incidencia, usuarios y auditoría). El botón solo aparece si
  el rol puede generar alguno de esos reportes.
- **Análisis estadístico** (`GET /api/v1/analysis`, pantalla «Análisis estadístico»): reúne para un
  periodo (y, opcionalmente, un atrapanieblas o dispositivo) la captación total y diaria (promedio,
  mediana, desviación estándar), la captación por atrapanieblas, la estadística de cada variable
  ambiental, la correlación de Pearson entre el volumen diario y cada variable, la calidad de las
  lecturas, los tiempos de atención de los reportes de incidencia, los mantenimientos y los
  repuestos más usados. Los días sin datos no se cuentan como cero. Lo consulta quien puede generar
  reportes (director y administrador) y cada sección exige además el permiso de su módulo.
- La correlación se presenta como asociación, no como causa; se informa el número de días usados.
- Gráficos del análisis (Recharts, ya instalado): captación diaria en barras, línea o acumulado con
  media móvil de 7 días y línea de la media; histograma de la captación diaria (regla de Sturges);
  barras divergentes de correlación (clic para elegir la variable) vinculadas a un diagrama de
  dispersión con recta de tendencia; barras horizontales para atrapanieblas, calidad, incidencias y
  mantenimientos. Todos tienen información al pasar el cursor y la opción «Ver tabla».
- Polos de la correlación: terracota (positiva) y glicina oscurecida (negativa), validados para
  daltonismo y contraste en claro y oscuro; la dirección de la barra y el valor rotulado también
  indican el signo, así que el color no es la única señal.

- El catálogo de reportes (`app/business/services/report_catalog.py`) es la única fuente de
  verdad: para cada reporte define su módulo, el permiso que exige (además de
  `reportes.generar`) y los filtros que admite, marcando los obligatorios. El backend lo usa para
  autorizar y describir los filtros; el frontend arma el formulario con `GET /api/v1/reports/catalog`
  y solo envía los filtros del reporte elegido.
- Módulos: monitoreo IoT y volumen (volumen, variable, mediciones, estado de las estaciones),
  inventario (stock, movimientos, resumen del periodo, conteo, kardex, consumo), mantenimiento,
  reportes de incidencia, y usuarios y auditoría.
- Los reportes de usuarios (datos personales) y de auditoría exigen `usuarios.gestionar` y
  `auditoria.consultar`, por lo que solo el administrador los genera; el director genera el resto.
- Cada archivo lista en su encabezado los filtros aplicados con nombres legibles (no
  identificadores), y la auditoría de `reporte.exportar` guarda los filtros usados.
- Las listas de personas para filtrar (responsables, quienes reportaron, usuarios de auditoría) se
  obtienen de `GET /api/v1/reports/filter-options`, sin dar acceso a la gestión de usuarios.
  Incluyen cuentas desactivadas, porque los reportes son históricos.
- Los códigos de error de filtros obligatorios ya publicados se conservan (`variable_requerida`,
  `periodo_requerido`, `repuesto_requerido`).
- PDF: ancho de columnas según el contenido (sin cortar palabras del encabezado) y letra menor en
  reportes con muchas columnas.

## Mediciones

- **Volumen captado: incremental.** Cada lectura son los litros captados desde la anterior. Las
  series y totales suman lecturas válidas; nunca se suman valores acumulados.
- Variables instantáneas (temperatura, humedad, nivel…) se promedian por intervalo.
- Calidad de lectura: `valida`, `sin_dato` (`null`), `fuera_de_rango`, `unidad_invalida`, `invalida`.
  Las lecturas con observación se guardan para trazabilidad, pero nunca como válidas
  (restricciones CHECK en PostgreSQL). Las lecturas de sensores no asociados o con fecha futura
  se rechazan sin guardarse.
- Fechas en UTC con zona horaria obligatoria; las agrupaciones por día/semana/mes usan
  `America/La_Paz`.
- Un dispositivo se considera desactualizado tras 30 minutos sin comunicación (`DEVICE_STALE_MINUTES`).

## Inventario

- El stock actual se mantiene en `inventory_items.current_stock` y se modifica solo mediante
  movimientos, con bloqueo de fila (`SELECT … FOR UPDATE`). Cada movimiento guarda stock antes/después.
- `salida_mantenimiento` solo la genera el módulo de mantenimiento.

## Frontend: sistema visual (DESIGN.md)

- La estética la dicta `DESIGN.md` (estilo «Visual», editorial): fondo crema `#f6f6f4`, tarjetas
  blancas con bordes finos `#d0d0c8`, tinta negra, neutros oliva-salvia, superficie carbón `#2c2c26`
  para el único botón relleno y el amarillo resaltador `#fff347` solo como marca decorativa (trazos de
  2–4 px: barra del ítem activo del menú y marca del encabezado de cada página).
- Tipografía: Fraunces (sustituto libre de la serif editorial, peso 300) solo para titulares grandes
  y cifras de los indicadores; IBM Plex Mono para toda la interfaz. Ambas instaladas como paquetes
  locales (sin CDN). Pesos máximos 500.
- Diseño plano: sin sombras ni degradados; radio de 3 px en botones, campos, etiquetas y navegación y
  de 8 px en tarjetas y diálogos. Botón secundario con borde negro de 1 px.
- Desviaciones deliberadas por legibilidad (WCAG AA): el texto de las etiquetas usa Olive Char
  (`#57584b`) y no Lichen (4,2:1 sobre Bone); los bordes de los campos usan `#8e8f7d` (≥ 3:1) en vez
  de Ash; el tracking del texto es -0,04 em en lugar de -0,067 em, porque más cerrado dificultaba la
  lectura de la monoespaciada; advertencias y errores usan ocre y terracota apagados, siempre con
  icono y texto.
- Gráficos: oliva `#5d6c14` para una serie; oliva / ocre (`#b98a3e`) para los polos de la
  correlación. Validados para daltonismo y contraste en claro y oscuro (los tonos salvia del
  documento se leen como gris y no distinguen series).
- `DESIGN.md` solo define el tema claro; el modo oscuro aplica la misma paleta sobre carbón.
- El menú lateral se ensanchó a 280 px: la monoespaciada es más ancha.
- A pedido del usuario: los botones de la barra superior y del menú lateral no tienen borde; al pasar
  el cursor se sombrean suavemente en los bordes (`--hover-shadow`, única sombra del sistema). La
  hamburguesa está dentro del menú lateral, en lugar del logo.
- Sin barra superior: arriba a la izquierda del menú lateral están la hamburguesa y los avisos; el
  bloque de perfil abajo a la izquierda abre el menú de usuario (mi perfil, cambiar contraseña, modo
  claro u oscuro, cerrar sesión). El estado del servidor queda en el recuadro del menú lateral. En el
  celular, donde el menú está oculto, un botón flotante arriba a la izquierda lo abre.
- El menú lateral desplegado se superpone al contenido: en escritorio se reserva solo el riel
  contraído (84 px), así el ancho de la página no cambia. Se cierra al navegar, con Escape o al hacer
  clic fuera (capa invisible: la página no se oscurece ni aclara), y ya no recuerda si quedó desplegado.
- Los reportes Excel y PDF usan los mismos tonos.

## Frontend

- Gráficos sin animación (equipos modestos; además evita un fallo de renderizado observado).
- Una serie por gráfico y un único eje Y.
