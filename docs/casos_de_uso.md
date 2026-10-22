# Especificación de casos de uso por proceso

Especificación de los procesos del sistema en los que intervienen varios roles. Cada caso de uso
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
| Director | Reporta fallas como el docente; además consulta todos los reportes y exporta reportes. |
| Administrador | Consulta todos los reportes y exporta reportes. |
| Personal de mantenimiento | Acepta los reportes, realiza el trabajo y registra su finalización. |
| Revisión automática del sistema | Proceso interno que se ejecuta cada 15 minutos y detecta fallas sin intervención humana. |
| Usuario sin acceso | Persona registrada que olvidó su contraseña o tiene la cuenta bloqueada. |

# Proceso 1: reportes de incidencia

Todo reporte pasa por los mismos estados: **abierto → aceptado → en progreso → finalizado**. Cada
cambio de estado genera un aviso interno y un registro de auditoría.

---

## CU-01 Reportar incidencia

| | |
|---|---|
| **Actor principal** | Docente (o Director) |
| **Actor secundario** | Personal de mantenimiento (recibe el aviso) |
| **Precondición** | El usuario inició sesión y tiene permiso para reportar incidencias. |
| **Postcondición** | El reporte queda registrado en estado *abierto* y el personal de mantenimiento recibe un aviso. |

**Flujo principal**

1. El usuario ingresa a la pantalla de reportes de incidencia y selecciona «Nuevo reporte».
2. El sistema presenta el formulario.
3. El usuario indica el título, la descripción y la prioridad y, si los conoce, el lugar, el
   dispositivo y el sensor afectados.
4. El usuario envía el reporte.
5. El sistema valida los datos, registra el reporte en estado *abierto* y avisa al personal de
   mantenimiento.
6. El sistema muestra la confirmación del envío.

**Flujos alternativos y de excepción**

- **4a. Datos incompletos.** Si falta el título, la descripción o la prioridad, el sistema señala
  los campos pendientes y no registra el reporte.
- **4b. Sensor sin dispositivo.** Si se indica un sensor sin indicar su dispositivo, o un sensor que
  no pertenece al dispositivo elegido, el sistema rechaza el reporte e informa el motivo.
- **4c. Cancelación.** Si el usuario cierra el formulario antes de enviarlo, no se registra nada.

---

## CU-02 Detectar incidencia automáticamente

| | |
|---|---|
| **Actor principal** | Revisión automática del sistema |
| **Actores secundarios** | Personal de mantenimiento, Director y Administrador (reciben el aviso) |
| **Precondición** | El sistema está en funcionamiento; la revisión se ejecuta cada 15 minutos. |
| **Postcondición** | Por cada falla nueva queda un reporte *abierto*, sin autor, marcado como automático. |

**Flujo principal**

1. La revisión automática se inicia según su intervalo.
2. El sistema identifica las estaciones activas que no se comunican desde hace más de 6 horas.
3. El sistema identifica los sensores activos con 10 o más lecturas rechazadas en las últimas
   24 horas.
4. Por cada caso, el sistema registra un reporte con prioridad *alta* (estación sin comunicación) o
   *media* (lecturas anómalas), con una descripción del problema detectado.
5. El sistema avisa al personal de mantenimiento y a los supervisores, y registra la operación en
   auditoría.

**Flujos alternativos y de excepción**

- **4a. Reporte duplicado.** Si ya existe un reporte automático de la misma causa sin finalizar, o
  finalizado dentro del periodo de la causa, el sistema no crea uno nuevo.
- **2a. Estación fuera de servicio.** Las estaciones en mantenimiento o desactivadas no se revisan.
- **1a. Falla de la revisión.** Si la base de datos no responde, el sistema registra el error y
  repite la revisión en el siguiente intervalo, sin detener el servicio.

---

## CU-03 Aceptar reporte

| | |
|---|---|
| **Actor principal** | Personal de mantenimiento |
| **Actor secundario** | Docente que reportó (recibe el aviso) |
| **Precondición** | El reporte está en estado *abierto*; el usuario tiene permiso para atender incidencias. |
| **Postcondición** | El reporte queda *aceptado* y asignado al técnico; se crea el registro de mantenimiento. |

**Flujo principal**

1. El técnico consulta la bandeja «Por atender», ordenada por prioridad.
2. El técnico abre un reporte y revisa su detalle.
3. El técnico selecciona «Aceptar reporte».
4. El sistema asigna el reporte al técnico, lo pasa a *aceptado* y crea el mantenimiento asociado.
5. El sistema avisa a quien reportó y muestra el nuevo estado.

**Flujos alternativos y de excepción**

- **3a. Reporte ya aceptado.** Si otro técnico lo aceptó antes, el sistema informa quién lo hizo y
  no modifica el reporte.
- **5a. Reporte automático.** Si el reporte lo originó el sistema (CU-02), no hay autor a quien
  avisar; el resto del flujo es igual.

---

## CU-04 Atender y finalizar el mantenimiento

| | |
|---|---|
| **Actor principal** | Personal de mantenimiento (técnico asignado) |
| **Actor secundario** | Docente que reportó (recibe los avisos) |
| **Precondición** | El reporte está *aceptado* y asignado al técnico. |
| **Postcondición** | El reporte queda *finalizado*, con el trabajo registrado; los repuestos usados se descuentan del inventario. |

**Flujo principal**

1. El técnico selecciona «Iniciar mantenimiento».
2. El sistema cambia el estado a *en progreso* y avisa a quien reportó.
3. El técnico realiza el trabajo en campo.
4. El técnico registra el tipo de mantenimiento, la descripción del trabajo, el estado final del
   componente y, si corresponde, los repuestos utilizados con sus cantidades
   (*extensión: Registrar repuestos utilizados*).
5. El sistema verifica el stock, registra las salidas de inventario y cambia el estado a
   *finalizado*.
6. El sistema avisa a quien reportó y registra la operación en auditoría.

**Flujos alternativos y de excepción**

- **5a. Stock insuficiente.** Si algún repuesto no tiene stock suficiente, el sistema informa el
  problema y **no guarda ningún cambio**; el mantenimiento continúa *en progreso*.
- **4a. Reemplazo sin repuestos.** Si el tipo es «reemplazo» y no se indica ningún repuesto, el
  sistema solicita registrarlos.
- **1a. Técnico no asignado.** Si otro usuario intenta avanzar el mantenimiento, el sistema
  rechaza la operación.

---

## CU-05 Consultar el seguimiento

| | |
|---|---|
| **Actor principal** | Docente, Director o Administrador |
| **Precondición** | El usuario inició sesión. |
| **Postcondición** | Ninguna; la consulta no modifica datos. |

**Flujo principal**

1. El usuario ingresa a la pantalla de reportes de incidencia.
2. El sistema muestra los reportes que el usuario puede ver: el docente, los propios; el director
   y el administrador, todos.
3. El usuario aplica filtros si lo desea (fechas, prioridad, estado, dispositivo, autor o
   responsable).
4. El usuario abre un reporte.
5. El sistema muestra su detalle y la línea de tiempo: fecha de cada etapa y persona responsable.

**Flujos alternativos y de excepción**

- **3a. Sin resultados.** Si ningún reporte cumple los filtros, el sistema lo indica.
- **4a. Reporte ajeno.** Si un docente intenta abrir un reporte de otra persona, el sistema lo
  informa como inexistente.

---

## CU-06 Exportar reporte de incidencias

| | |
|---|---|
| **Actor principal** | Director o Administrador |
| **Precondición** | El usuario tiene permisos para supervisar incidencias y generar reportes. |
| **Postcondición** | Se descarga un archivo con los reportes que cumplen los filtros. |

**Flujo principal**

1. El usuario define los filtros en la pantalla de reportes de incidencia.
2. El usuario elige el formato: Excel, PDF o CSV.
3. El usuario selecciona «Exportar».
4. El sistema genera el archivo en el servidor local, con un encabezado que indica los filtros
   aplicados.
5. El navegador descarga el archivo.

**Flujos alternativos y de excepción**

- **1a. Sin fechas.** Si no se indica un periodo, el reporte incluye los últimos 30 días.
- **1b. Periodo inválido.** Si la fecha inicial es posterior a la final, el sistema no permite
  exportar hasta corregirla.

---

# Proceso 2: recuperación de cuenta

La cuenta se recupera mediante el administrador, de forma presencial. El sistema no envía correos,
SMS ni enlaces de recuperación.

## CU-07 Solicitar recuperación de cuenta

| | |
|---|---|
| **Actor principal** | Usuario sin acceso |
| **Actor secundario** | Administrador (atiende la solicitud) |
| **Precondición** | El usuario no puede iniciar sesión. |
| **Postcondición** | Queda una solicitud *pendiente*; el sistema no revela si el usuario existe. |

**Flujo principal**

1. El usuario selecciona «¿Olvidó su contraseña?» en la pantalla de inicio de sesión.
2. El usuario indica su nombre de usuario y, si lo desea, un mensaje para el administrador.
3. El usuario envía la solicitud.
4. El sistema registra la solicitud como *pendiente* y muestra un mensaje genérico.
5. El usuario acude en persona al administrador.

**Flujos alternativos y de excepción**

- **4a. Demasiadas solicitudes desde el mismo equipo.** Si se supera el límite por dirección IP,
  el sistema pide intentarlo más tarde.
- **4b. Demasiadas solicitudes para el mismo usuario.** El sistema muestra el mismo mensaje
  genérico, pero no registra una solicitud nueva.
- **4c. Usuario inexistente.** El sistema responde igual que en el flujo principal; el
  administrador rechaza luego la solicitud.

## CU-08 Resolver solicitud de recuperación

| | |
|---|---|
| **Actor principal** | Administrador |
| **Actor secundario** | Usuario sin acceso (presente para verificar su identidad) |
| **Precondición** | Existe una solicitud *pendiente*; el administrador tiene permiso para gestionar recuperaciones. |
| **Postcondición** | La solicitud queda *aprobada* o *rechazada* y registrada en auditoría. Si se aprueba, el usuario tiene una contraseña temporal y sus sesiones anteriores quedan cerradas. |

**Flujo principal**

1. El administrador consulta las solicitudes pendientes.
2. El administrador verifica en persona la identidad del solicitante.
3. El administrador aprueba la solicitud y confirma que verificó la identidad.
4. El sistema asigna una contraseña temporal, cierra las sesiones activas del usuario y marca la
   solicitud como *aprobada*.
5. El sistema muestra la contraseña temporal una sola vez.
6. El administrador entrega la contraseña temporal al usuario en persona.

**Flujos alternativos y de excepción**

- **3a. Rechazo.** Si la identidad no se confirma, el administrador rechaza la solicitud indicando
  el motivo; el sistema la marca como *rechazada*.
- **3b. Verificación no confirmada.** El sistema no permite aprobar sin confirmar la verificación
  de identidad.
- **4a. Usuario inexistente o desactivado.** El sistema no permite aprobar; la solicitud debe
  rechazarse o el usuario debe reactivarse primero.
- **4b. Solicitud ya resuelta.** Si otro administrador la resolvió antes, el sistema lo informa.

## CU-09 Cambiar la contraseña temporal

| | |
|---|---|
| **Actor principal** | Usuario sin acceso (con contraseña temporal) |
| **Precondición** | El administrador aprobó la solicitud y entregó la contraseña temporal. |
| **Postcondición** | La nueva contraseña queda guardada como hash, el usuario accede al sistema y sus otras sesiones quedan cerradas. |

**Flujo principal**

1. El usuario inicia sesión con la contraseña temporal.
2. El sistema le exige cambiarla antes de usar el sistema.
3. El usuario ingresa la contraseña temporal y la nueva contraseña.
4. El sistema valida la nueva contraseña, la guarda y cierra las demás sesiones.
5. El usuario accede al sistema.

**Flujos alternativos y de excepción**

- **4a. Contraseña actual incorrecta.** El sistema rechaza el cambio.
- **4b. Contraseña nueva débil o igual a la anterior.** El sistema indica los requisitos y no la
  guarda.

---

# Proceso 3: mantenimiento con repuestos

## CU-10 Registrar mantenimiento

| | |
|---|---|
| **Actor principal** | Personal de mantenimiento |
| **Precondición** | El usuario tiene permiso para registrar mantenimientos; el dispositivo está registrado. |
| **Postcondición** | El mantenimiento queda registrado como finalizado y asociado al dispositivo; cada repuesto usado genera una salida de inventario. |

**Flujo principal**

1. El técnico selecciona «Registrar» en la pantalla de mantenimiento.
2. El técnico indica el dispositivo (y, si corresponde, el sensor), la fecha, el tipo, la
   descripción del trabajo y el estado final del componente.
3. El técnico agrega los repuestos utilizados y sus cantidades, si los hubo.
4. El técnico guarda el registro.
5. El sistema valida los datos, registra el mantenimiento, descuenta los repuestos del inventario y
   confirma el registro.

**Flujos alternativos y de excepción**

- **5a. Sensor no asociado.** Si el sensor no pertenece al dispositivo, el sistema rechaza el
  registro.
- **5b. Fecha futura.** El sistema no acepta una fecha posterior a la actual.
- **5c. Reemplazo sin repuestos o repuesto repetido.** El sistema solicita corregir la lista de
  repuestos.
- **5d. Stock insuficiente.** Si algún repuesto no tiene stock suficiente, el sistema lo informa y
  **no guarda ningún cambio**.

---

# Proceso 4: periodo de inventario

Un periodo permite comparar el stock registrado con el conteo físico y cerrar con saldos
valorizados.

## CU-11 Abrir periodo de inventario

| | |
|---|---|
| **Actor principal** | Administrador |
| **Precondición** | El usuario tiene permiso para gestionar el inventario. |
| **Postcondición** | El periodo queda *abierto*. |

**Flujo principal**

1. El administrador selecciona «Nuevo periodo».
2. El administrador indica el nombre, la fecha inicial, la fecha final y, si lo desea, notas.
3. El sistema valida las fechas y registra el periodo como *abierto*.

**Flujos alternativos y de excepción**

- **3a. Fechas inválidas.** Si la fecha inicial es posterior a la final, el sistema lo informa.
- **3b. Periodo superpuesto o nombre repetido.** El sistema indica con qué periodo se superpone o
  que el nombre ya existe.

## CU-12 Registrar conteo físico

| | |
|---|---|
| **Actor principal** | Administrador |
| **Precondición** | El periodo está *abierto*. |
| **Postcondición** | Los conteos quedan guardados y el sistema muestra las diferencias con el stock registrado. |

**Flujo principal**

1. El administrador abre el periodo.
2. El administrador ingresa la cantidad contada de cada repuesto.
3. El sistema guarda los conteos y muestra la diferencia de cada repuesto.

**Flujos alternativos y de excepción**

- **3a. Periodo cerrado.** El sistema no admite conteos en un periodo cerrado.
- **3b. Cantidad negativa o repuesto inexistente.** El sistema rechaza el conteo.

## CU-13 Cerrar periodo

| | |
|---|---|
| **Actor principal** | Administrador |
| **Precondición** | El periodo está *abierto*, ya terminó, el periodo anterior está cerrado y todos los repuestos activos fueron contados. |
| **Postcondición** | El periodo queda *cerrado*; las diferencias se registran como ajustes de inventario y se guardan los saldos valorizados. |

**Flujo principal**

1. El administrador selecciona «Cerrar periodo».
2. El sistema verifica las condiciones de cierre.
3. El sistema calcula los saldos del periodo.
4. El sistema registra un ajuste por cada repuesto con sobrante o faltante.
5. El sistema guarda los saldos valorizados, cierra el periodo y muestra el resumen.

**Flujos alternativos y de excepción**

- **2a. Periodo en curso.** El sistema no permite cerrar un periodo que aún no terminó.
- **2b. Periodo anterior abierto.** El sistema indica qué periodo debe cerrarse primero.
- **2c. Conteo incompleto.** El sistema muestra la lista de repuestos sin contar.

## CU-14 Exportar resumen y acta del periodo

| | |
|---|---|
| **Actores principales** | Director, Administrador |
| **Precondición** | El usuario tiene permisos para consultar el inventario y generar reportes. |
| **Postcondición** | Se descarga el resumen valorizado o el acta de conteo del periodo. |

**Flujo principal**

1. El usuario elige el reporte «Resumen del periodo» o «Planilla / acta de conteo físico» en la
   pantalla de inventario.
2. El usuario selecciona el periodo y, si lo desea, una categoría.
3. El usuario elige el formato y selecciona «Exportar».
4. El sistema genera el archivo y el navegador lo descarga.

**Flujos alternativos y de excepción**

- **2a. Sin periodo.** El sistema no permite exportar hasta que se elija un periodo.
