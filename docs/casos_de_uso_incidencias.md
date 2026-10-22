# Especificación de casos de uso: gestión de reportes de incidencia

Este proceso permite comunicar al personal de mantenimiento las fallas de las estaciones IoT o de
los atrapanieblas, y dar seguimiento a su atención hasta que el componente vuelve a operar. Un
reporte puede originarse de dos maneras: lo registra un usuario o lo detecta el propio sistema.

Diagramas asociados: [diagramas/incidencias.drawio](diagramas/incidencias.drawio)
(página «Casos de uso · Incidencias» y página «Secuencia · Incidencias»).

## Actores

| Actor | Descripción |
|-------|-------------|
| Docente | Usuario del centro que informa una falla y consulta el estado de sus reportes. |
| Director | Hereda las funciones del docente; además consulta todos los reportes y exporta reportes. |
| Administrador | Consulta todos los reportes y exporta reportes. |
| Personal de mantenimiento | Acepta los reportes, realiza el trabajo y registra su finalización. |
| Revisión automática del sistema | Proceso interno que se ejecuta cada 15 minutos y detecta fallas sin intervención humana. |

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
