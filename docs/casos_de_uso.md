# Especificación de casos de uso por proceso

Tabla descriptiva de cada caso de uso de los procesos del sistema en los que intervienen varios roles. Cada caso de uso
tiene su diagrama de casos de uso y su diagrama de secuencia en
[diagramas/procesos.drawio](diagramas/procesos.drawio), una página por diagrama.

Los diagramas de secuencia muestran tres componentes: la **interfaz web**, el **controlador**
(que agrupa la API y la lógica de negocio del módulo) y la **base de datos**. Solo representan el
error principal de cada caso; los demás flujos alternativos se describen en este documento.

| Proceso | Casos de uso | Páginas del archivo |
|---------|--------------|---------------------|
| Reportes de incidencia | CU-01 a CU-06 | «CU-01 · Casos de uso», «CU-01 · Secuencia», … «CU-06 · Secuencia» |
| Recuperación de cuenta | CU-07 a CU-09 | «Recuperación · Casos de uso», «Recuperación · Secuencia» |
| Mantenimiento con repuestos | CU-10 | «Mantenimiento · Casos de uso», «Mantenimiento · Secuencia» |
| Periodo de inventario | CU-11 a CU-14 | «Periodo de inventario · Casos de uso», «Periodo de inventario · Secuencia» |

## Actores

| Actor | Descripción |
|-------|-------------|
| Docente | Usuario del centro que informa una falla y consulta el estado de sus reportes. |
| Director | Reporta fallas como el docente; además supervisa todos los reportes y exporta reportes. |
| Administrador | Supervisa los reportes, resuelve las solicitudes de recuperación de cuenta y gestiona los periodos de inventario. |
| Personal de mantenimiento | Atiende los reportes de incidencia y registra los mantenimientos con los repuestos utilizados. |
| Revisión automática del sistema | Proceso interno que se ejecuta cada 15 minutos y detecta fallas sin intervención humana. |
| Usuario sin acceso | Persona registrada que olvidó su contraseña o tiene la cuenta bloqueada. |

# Proceso 1: reportes de incidencia

Todo reporte pasa por los mismos estados: **abierto → aceptado → en progreso → finalizado**. Cada
cambio de estado genera un aviso interno y un registro de auditoría.

---

## CU-01 Reportar incidencia

| Campo | Descripción |
|---|---|
| **Código** | CU-01 |
| **Nombre** | Reportar incidencia |
| **Proceso** | Reportes de incidencia |
| **Actor principal** | Docente (o Director) |
| **Actores secundarios** | Personal de mantenimiento (recibe el aviso) |
| **Descripción** | Permite a un docente o al director informar una falla de una estación IoT o de un atrapanieblas al personal de mantenimiento. |
| **Precondición** | El usuario inició sesión y tiene permiso para reportar incidencias. |
| **Flujo principal** | 1. El usuario ingresa a la pantalla de reportes de incidencia y selecciona «Nuevo reporte».<br>2. El sistema presenta el formulario.<br>3. El usuario indica el título, la descripción y la prioridad y, si los conoce, el lugar, el dispositivo y el sensor afectados.<br>4. El usuario envía el reporte.<br>5. El sistema valida los datos, registra el reporte en estado *abierto* y avisa al personal de mantenimiento.<br>6. El sistema muestra la confirmación del envío. |
| **Flujos alternativos y de excepción** | 4a. Datos incompletos. Si falta el título, la descripción o la prioridad, el sistema señala los campos pendientes y no registra el reporte.<br>4b. Sensor sin dispositivo. Si se indica un sensor sin indicar su dispositivo, o un sensor que no pertenece al dispositivo elegido, el sistema rechaza el reporte e informa el motivo.<br>4c. Cancelación. Si el usuario cierra el formulario antes de enviarlo, no se registra nada. |
| **Postcondición** | El reporte queda registrado en estado *abierto* y el personal de mantenimiento recibe un aviso. |
| **Relaciones** | «include» Validar dispositivo y sensor<br>«include» Notificar al personal de mantenimiento |

---

## CU-02 Detectar incidencia automáticamente

| Campo | Descripción |
|---|---|
| **Código** | CU-02 |
| **Nombre** | Detectar incidencia automáticamente |
| **Proceso** | Reportes de incidencia |
| **Actor principal** | Revisión automática del sistema |
| **Actores secundarios** | Personal de mantenimiento, Director y Administrador (reciben el aviso) |
| **Descripción** | El sistema revisa periódicamente las estaciones y los sensores, y abre un reporte cuando detecta una falla. |
| **Precondición** | El sistema está en funcionamiento; la revisión se ejecuta cada 15 minutos. |
| **Flujo principal** | 1. La revisión automática se inicia según su intervalo.<br>2. El sistema identifica las estaciones activas que no se comunican desde hace más de 6 horas.<br>3. El sistema identifica los sensores activos con 10 o más lecturas rechazadas en las últimas 24 horas.<br>4. Por cada caso, el sistema registra un reporte con prioridad *alta* (estación sin comunicación) o *media* (lecturas anómalas), con una descripción del problema detectado.<br>5. El sistema avisa al personal de mantenimiento y a los supervisores, y registra la operación en auditoría. |
| **Flujos alternativos y de excepción** | 1a. Falla de la revisión. Si la base de datos no responde, el sistema registra el error y repite la revisión en el siguiente intervalo, sin detener el servicio.<br>2a. Estación fuera de servicio. Las estaciones en mantenimiento o desactivadas no se revisan.<br>4a. Reporte duplicado. Si ya existe un reporte automático de la misma causa sin finalizar, o finalizado dentro del periodo de la causa, el sistema no crea uno nuevo. |
| **Postcondición** | Por cada falla nueva queda un reporte *abierto*, sin autor, marcado como automático. |
| **Relaciones** | «include» Detectar estación sin comunicación<br>«include» Detectar lecturas anómalas<br>«include» Evitar reportes duplicados<br>«include» Notificar a mantenimiento y supervisores |

---

## CU-03 Aceptar reporte

| Campo | Descripción |
|---|---|
| **Código** | CU-03 |
| **Nombre** | Aceptar reporte |
| **Proceso** | Reportes de incidencia |
| **Actor principal** | Personal de mantenimiento |
| **Actores secundarios** | Docente que reportó (recibe el aviso) |
| **Descripción** | Permite al personal de mantenimiento tomar un reporte abierto y quedar como responsable de su atención. |
| **Precondición** | El reporte está en estado *abierto*; el usuario tiene permiso para atender incidencias. |
| **Flujo principal** | 1. El técnico consulta la bandeja «Por atender», ordenada por prioridad.<br>2. El técnico abre un reporte y revisa su detalle.<br>3. El técnico selecciona «Aceptar reporte».<br>4. El sistema asigna el reporte al técnico, lo pasa a *aceptado* y crea el mantenimiento asociado.<br>5. El sistema avisa a quien reportó y muestra el nuevo estado. |
| **Flujos alternativos y de excepción** | 3a. Reporte ya aceptado. Si otro técnico lo aceptó antes, el sistema informa quién lo hizo y no modifica el reporte.<br>5a. Reporte automático. Si el reporte lo originó el sistema (CU-02), no hay autor a quien avisar; el resto del flujo es igual. |
| **Postcondición** | El reporte queda *aceptado* y asignado al técnico; se crea el registro de mantenimiento. |
| **Relaciones** | «include» Consultar reportes por atender<br>«include» Crear mantenimiento asociado<br>«include» Notificar a quien reportó |

---

## CU-04 Atender y finalizar el mantenimiento

| Campo | Descripción |
|---|---|
| **Código** | CU-04 |
| **Nombre** | Atender y finalizar el mantenimiento |
| **Proceso** | Reportes de incidencia |
| **Actor principal** | Personal de mantenimiento (técnico asignado) |
| **Actores secundarios** | Docente que reportó (recibe los avisos) |
| **Descripción** | Permite al técnico asignado iniciar el mantenimiento, registrar el trabajo realizado y darlo por finalizado. |
| **Precondición** | El reporte está *aceptado* y asignado al técnico. |
| **Flujo principal** | 1. El técnico selecciona «Iniciar mantenimiento».<br>2. El sistema cambia el estado a *en progreso* y avisa a quien reportó.<br>3. El técnico realiza el trabajo en campo.<br>4. El técnico registra el tipo de mantenimiento, la descripción del trabajo, el estado final del componente y, si corresponde, los repuestos utilizados con sus cantidades (*extensión: Registrar repuestos utilizados*).<br>5. El sistema verifica el stock, registra las salidas de inventario y cambia el estado a *finalizado*.<br>6. El sistema avisa a quien reportó y registra la operación en auditoría. |
| **Flujos alternativos y de excepción** | 1a. Técnico no asignado. Si otro usuario intenta avanzar el mantenimiento, el sistema rechaza la operación.<br>4a. Reemplazo sin repuestos. Si el tipo es «reemplazo» y no se indica ningún repuesto, el sistema solicita registrarlos.<br>5a. Stock insuficiente. Si algún repuesto no tiene stock suficiente, el sistema informa el problema y **no guarda ningún cambio**; el mantenimiento continúa *en progreso*. |
| **Postcondición** | El reporte queda *finalizado*, con el trabajo registrado; los repuestos usados se descuentan del inventario. |
| **Relaciones** | «include» Iniciar mantenimiento<br>«include» Registrar trabajo y estado final<br>«extend» Registrar repuestos utilizados [si se usaron repuestos], que incluye «Descontar del inventario»<br>«include» Notificar a quien reportó |

---

## CU-05 Consultar el seguimiento

| Campo | Descripción |
|---|---|
| **Código** | CU-05 |
| **Nombre** | Consultar el seguimiento |
| **Proceso** | Reportes de incidencia |
| **Actor principal** | Docente, Director o Administrador |
| **Actores secundarios** | Ninguno |
| **Descripción** | Permite consultar el estado de los reportes, su responsable y la fecha de cada etapa. |
| **Precondición** | El usuario inició sesión. |
| **Flujo principal** | 1. El usuario ingresa a la pantalla de reportes de incidencia.<br>2. El sistema muestra los reportes que el usuario puede ver: el docente, los propios; el director y el administrador, todos.<br>3. El usuario aplica filtros si lo desea (fechas, prioridad, estado, dispositivo, autor o responsable).<br>4. El usuario abre un reporte.<br>5. El sistema muestra su detalle y la línea de tiempo: fecha de cada etapa y persona responsable. |
| **Flujos alternativos y de excepción** | 3a. Sin resultados. Si ningún reporte cumple los filtros, el sistema lo indica.<br>4a. Reporte ajeno. Si un docente intenta abrir un reporte de otra persona, el sistema lo informa como inexistente. |
| **Postcondición** | Ninguna; la consulta no modifica datos. |
| **Relaciones** | «extend» Aplicar filtros [si filtra la lista]<br>«extend» Ver detalle y línea de tiempo [si abre un reporte] |

---

## CU-06 Exportar reporte de incidencias

| Campo | Descripción |
|---|---|
| **Código** | CU-06 |
| **Nombre** | Exportar reporte de incidencias |
| **Proceso** | Reportes de incidencia |
| **Actor principal** | Director o Administrador |
| **Actores secundarios** | Ninguno |
| **Descripción** | Permite descargar un reporte de incidencias en Excel, PDF o CSV con los filtros de la pantalla. |
| **Precondición** | El usuario tiene permisos para supervisar incidencias y generar reportes. |
| **Flujo principal** | 1. El usuario define los filtros en la pantalla de reportes de incidencia.<br>2. El usuario elige el formato: Excel, PDF o CSV.<br>3. El usuario selecciona «Exportar».<br>4. El sistema genera el archivo en el servidor local, con un encabezado que indica los filtros aplicados.<br>5. El navegador descarga el archivo. |
| **Flujos alternativos y de excepción** | 1a. Sin fechas. Si no se indica un periodo, el reporte incluye los últimos 30 días.<br>1b. Periodo inválido. Si la fecha inicial es posterior a la final, el sistema no permite exportar hasta corregirla. |
| **Postcondición** | Se descarga un archivo con los reportes que cumplen los filtros. |
| **Relaciones** | «include» Aplicar filtros del módulo<br>«include» Generar archivo en el servidor<br>«include» Registrar la exportación en auditoría |

---

# Proceso 2: recuperación de cuenta

La cuenta se recupera mediante el administrador, de forma presencial. El sistema no envía correos,
SMS ni enlaces de recuperación.

## CU-07 Solicitar recuperación de cuenta

| Campo | Descripción |
|---|---|
| **Código** | CU-07 |
| **Nombre** | Solicitar recuperación de cuenta |
| **Proceso** | Recuperación de cuenta |
| **Actor principal** | Usuario sin acceso |
| **Actores secundarios** | Administrador (atiende la solicitud) |
| **Descripción** | Permite a un usuario que no puede ingresar pedir al administrador la recuperación de su cuenta. |
| **Precondición** | El usuario no puede iniciar sesión. |
| **Flujo principal** | 1. El usuario selecciona «¿Olvidó su contraseña?» en la pantalla de inicio de sesión.<br>2. El usuario indica su nombre de usuario y, si lo desea, un mensaje para el administrador.<br>3. El usuario envía la solicitud.<br>4. El sistema registra la solicitud como *pendiente* y muestra un mensaje genérico.<br>5. El usuario acude en persona al administrador. |
| **Flujos alternativos y de excepción** | 4a. Demasiadas solicitudes desde el mismo equipo. Si se supera el límite por dirección IP, el sistema pide intentarlo más tarde.<br>4b. Demasiadas solicitudes para el mismo usuario. El sistema muestra el mismo mensaje genérico, pero no registra una solicitud nueva.<br>4c. Usuario inexistente. El sistema responde igual que en el flujo principal; el administrador rechaza luego la solicitud. |
| **Postcondición** | Queda una solicitud *pendiente*; el sistema no revela si el usuario existe. |
| **Relaciones** | Ninguna. Inicia el proceso que continúa en CU-08. |

## CU-08 Resolver solicitud de recuperación

| Campo | Descripción |
|---|---|
| **Código** | CU-08 |
| **Nombre** | Resolver solicitud de recuperación |
| **Proceso** | Recuperación de cuenta |
| **Actor principal** | Administrador |
| **Actores secundarios** | Usuario sin acceso (presente para verificar su identidad) |
| **Descripción** | Permite al administrador aprobar o rechazar una solicitud de recuperación tras verificar la identidad en persona. |
| **Precondición** | Existe una solicitud *pendiente*; el administrador tiene permiso para gestionar recuperaciones. |
| **Flujo principal** | 1. El administrador consulta las solicitudes pendientes.<br>2. El administrador verifica en persona la identidad del solicitante.<br>3. El administrador aprueba la solicitud y confirma que verificó la identidad.<br>4. El sistema asigna una contraseña temporal, cierra las sesiones activas del usuario y marca la solicitud como *aprobada*.<br>5. El sistema muestra la contraseña temporal una sola vez.<br>6. El administrador entrega la contraseña temporal al usuario en persona. |
| **Flujos alternativos y de excepción** | 3a. Rechazo. Si la identidad no se confirma, el administrador rechaza la solicitud indicando el motivo; el sistema la marca como *rechazada*.<br>3b. Verificación no confirmada. El sistema no permite aprobar sin confirmar la verificación de identidad.<br>4a. Usuario inexistente o desactivado. El sistema no permite aprobar; la solicitud debe rechazarse o el usuario debe reactivarse primero.<br>4b. Solicitud ya resuelta. Si otro administrador la resolvió antes, el sistema lo informa. |
| **Postcondición** | La solicitud queda *aprobada* o *rechazada* y registrada en auditoría. Si se aprueba, el usuario tiene una contraseña temporal y sus sesiones anteriores quedan cerradas. |
| **Relaciones** | «include» Verificar la identidad en persona<br>«extend» Asignar contraseña temporal e invalidar sesiones [si aprueba]<br>«extend» Rechazar con motivo [si rechaza] |

## CU-09 Cambiar la contraseña temporal

| Campo | Descripción |
|---|---|
| **Código** | CU-09 |
| **Nombre** | Cambiar la contraseña temporal |
| **Proceso** | Recuperación de cuenta |
| **Actor principal** | Usuario sin acceso (con contraseña temporal) |
| **Actores secundarios** | Ninguno |
| **Descripción** | Obliga al usuario a reemplazar la contraseña temporal por una propia antes de usar el sistema. |
| **Precondición** | El administrador aprobó la solicitud y entregó la contraseña temporal. |
| **Flujo principal** | 1. El usuario inicia sesión con la contraseña temporal.<br>2. El sistema le exige cambiarla antes de usar el sistema.<br>3. El usuario ingresa la contraseña temporal y la nueva contraseña.<br>4. El sistema valida la nueva contraseña, la guarda y cierra las demás sesiones.<br>5. El usuario accede al sistema. |
| **Flujos alternativos y de excepción** | 4a. Contraseña actual incorrecta. El sistema rechaza el cambio.<br>4b. Contraseña nueva débil o igual a la anterior. El sistema indica los requisitos y no la guarda. |
| **Postcondición** | La nueva contraseña queda guardada como hash, el usuario accede al sistema y sus otras sesiones quedan cerradas. |
| **Relaciones** | Ninguna. Continúa el proceso tras CU-08. |

---

# Proceso 3: mantenimiento con repuestos

## CU-10 Registrar mantenimiento

| Campo | Descripción |
|---|---|
| **Código** | CU-10 |
| **Nombre** | Registrar mantenimiento |
| **Proceso** | Mantenimiento con repuestos |
| **Actor principal** | Personal de mantenimiento |
| **Actores secundarios** | Ninguno |
| **Descripción** | Permite registrar un mantenimiento ya realizado y descontar del inventario los repuestos utilizados. |
| **Precondición** | El usuario tiene permiso para registrar mantenimientos; el dispositivo está registrado. |
| **Flujo principal** | 1. El técnico selecciona «Registrar» en la pantalla de mantenimiento.<br>2. El técnico indica el dispositivo (y, si corresponde, el sensor), la fecha, el tipo, la descripción del trabajo y el estado final del componente.<br>3. El técnico agrega los repuestos utilizados y sus cantidades, si los hubo.<br>4. El técnico guarda el registro.<br>5. El sistema valida los datos, registra el mantenimiento, descuenta los repuestos del inventario y confirma el registro. |
| **Flujos alternativos y de excepción** | 5a. Sensor no asociado. Si el sensor no pertenece al dispositivo, el sistema rechaza el registro.<br>5b. Fecha futura. El sistema no acepta una fecha posterior a la actual.<br>5c. Reemplazo sin repuestos o repuesto repetido. El sistema solicita corregir la lista de repuestos.<br>5d. Stock insuficiente. Si algún repuesto no tiene stock suficiente, el sistema lo informa y **no guarda ningún cambio**. |
| **Postcondición** | El mantenimiento queda registrado como finalizado y asociado al dispositivo; cada repuesto usado genera una salida de inventario. |
| **Relaciones** | «include» Validar dispositivo y sensor<br>«include» Validar el trabajo (tipo, fecha y repuestos)<br>«extend» Registrar repuestos utilizados [si se usaron repuestos], que incluye «Descontar del inventario» |

---

# Proceso 4: periodo de inventario

Un periodo permite comparar el stock registrado con el conteo físico y cerrar con saldos
valorizados.

## CU-11 Abrir periodo de inventario

| Campo | Descripción |
|---|---|
| **Código** | CU-11 |
| **Nombre** | Abrir periodo de inventario |
| **Proceso** | Periodo de inventario |
| **Actor principal** | Administrador |
| **Actores secundarios** | Ninguno |
| **Descripción** | Permite iniciar un periodo de inventario con fechas definidas. |
| **Precondición** | El usuario tiene permiso para gestionar el inventario. |
| **Flujo principal** | 1. El administrador selecciona «Nuevo periodo».<br>2. El administrador indica el nombre, la fecha inicial, la fecha final y, si lo desea, notas.<br>3. El sistema valida las fechas y registra el periodo como *abierto*. |
| **Flujos alternativos y de excepción** | 3a. Fechas inválidas. Si la fecha inicial es posterior a la final, el sistema lo informa.<br>3b. Periodo superpuesto o nombre repetido. El sistema indica con qué periodo se superpone o que el nombre ya existe. |
| **Postcondición** | El periodo queda *abierto*. |
| **Relaciones** | Ninguna. Inicia el proceso que continúa en CU-12. |

## CU-12 Registrar conteo físico

| Campo | Descripción |
|---|---|
| **Código** | CU-12 |
| **Nombre** | Registrar conteo físico |
| **Proceso** | Periodo de inventario |
| **Actor principal** | Administrador |
| **Actores secundarios** | Ninguno |
| **Descripción** | Permite registrar la cantidad física contada de cada repuesto y compararla con el stock registrado. |
| **Precondición** | El periodo está *abierto*. |
| **Flujo principal** | 1. El administrador abre el periodo.<br>2. El administrador ingresa la cantidad contada de cada repuesto.<br>3. El sistema guarda los conteos y muestra la diferencia de cada repuesto. |
| **Flujos alternativos y de excepción** | 3a. Periodo cerrado. El sistema no admite conteos en un periodo cerrado.<br>3b. Cantidad negativa o repuesto inexistente. El sistema rechaza el conteo. |
| **Postcondición** | Los conteos quedan guardados y el sistema muestra las diferencias con el stock registrado. |
| **Relaciones** | Ninguna. Requiere un periodo abierto (CU-11). |

## CU-13 Cerrar periodo

| Campo | Descripción |
|---|---|
| **Código** | CU-13 |
| **Nombre** | Cerrar periodo |
| **Proceso** | Periodo de inventario |
| **Actor principal** | Administrador |
| **Actores secundarios** | Ninguno |
| **Descripción** | Permite cerrar un periodo terminado, ajustando las diferencias del conteo y calculando los saldos valorizados. |
| **Precondición** | El periodo está *abierto*, ya terminó, el periodo anterior está cerrado y todos los repuestos activos fueron contados. |
| **Flujo principal** | 1. El administrador selecciona «Cerrar periodo».<br>2. El sistema verifica las condiciones de cierre.<br>3. El sistema calcula los saldos del periodo.<br>4. El sistema registra un ajuste por cada repuesto con sobrante o faltante.<br>5. El sistema guarda los saldos valorizados, cierra el periodo y muestra el resumen. |
| **Flujos alternativos y de excepción** | 2a. Periodo en curso. El sistema no permite cerrar un periodo que aún no terminó.<br>2b. Periodo anterior abierto. El sistema indica qué periodo debe cerrarse primero.<br>2c. Conteo incompleto. El sistema muestra la lista de repuestos sin contar. |
| **Postcondición** | El periodo queda *cerrado*; las diferencias se registran como ajustes de inventario y se guardan los saldos valorizados. |
| **Relaciones** | «include» Verificar que el conteo esté completo<br>«include» Generar ajustes por diferencia<br>«include» Calcular saldos valorizados |

## CU-14 Exportar resumen y acta del periodo

| Campo | Descripción |
|---|---|
| **Código** | CU-14 |
| **Nombre** | Exportar resumen y acta del periodo |
| **Proceso** | Periodo de inventario |
| **Actor principal** | Director, Administrador |
| **Actores secundarios** | Ninguno |
| **Descripción** | Permite descargar el resumen valorizado o el acta de conteo físico de un periodo. |
| **Precondición** | El usuario tiene permisos para consultar el inventario y generar reportes. |
| **Flujo principal** | 1. El usuario elige el reporte «Resumen del periodo» o «Planilla / acta de conteo físico» en la pantalla de inventario.<br>2. El usuario selecciona el periodo y, si lo desea, una categoría.<br>3. El usuario elige el formato y selecciona «Exportar».<br>4. El sistema genera el archivo y el navegador lo descarga. |
| **Flujos alternativos y de excepción** | 2a. Sin periodo. El sistema no permite exportar hasta que se elija un periodo. |
| **Postcondición** | Se descarga el resumen valorizado o el acta de conteo del periodo. |
| **Relaciones** | Ninguna. Usa el módulo de reportes. |

