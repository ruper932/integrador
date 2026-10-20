# Sistema Web de Monitoreo de Agua Captada mediante Atrapanieblas con IoT y Predicción de Volumen (Machine Learning)

> Resumen en Markdown del documento académico original (.docx).
> **Institución:** Universidad Privada Franz Tamayo — Ingeniería de Sistemas
> **Estudiante:** Limber Ignacio Romero Urrelo · **Docente:** Sharon Lizbeth Castellón Tito · La Paz, Bolivia, 2026
> **Caso:** Centro de Educación Alternativa (C.E.A.) Ildefonso de las Muecas, Titicachi, municipio de Chuma, La Paz

---

## 1. Contexto y problema

- El C.E.A. (fundado en 1995, formación técnica humanística agropecuaria) depende de **un único ojo de agua comunitario**, insuficiente y variable, para regar sus invernaderos académicos.
- Se plantea el **atrapanieblas** (malla Raschel) como fuente **complementaria**. Referencia del documento: un atrapanieblas recolecta en promedio 3–5 L/día por m².
- No existe un registro histórico que relacione condiciones meteorológicas con el volumen captado; no se sabe qué parte de la demanda puede cubrir.
- **Pregunta de investigación:** ¿Cómo conocer el comportamiento y el volumen de agua captada mediante atrapanieblas en relación con las condiciones meteorológicas del C.E.A.?

**Novedad:** integrar en una sola arquitectura captación física, monitoreo IoT en tiempo real, modelo de machine learning, interoperabilidad local (MCP) y dashboard web para apoyo a decisiones.

---

## 2. Objetivos

### Objetivo general
Desarrollar un sistema web de monitoreo de agua captada mediante atrapanieblas, integrando una estación IoT y un modelo de predicción de volumen basado en machine learning, para disponer de información histórica y estimaciones que apoyen la planificación del riego en el C.E.A. durante el segundo semestre de 2026.

### Objetivos específicos
1. Diseñar una plataforma web local (FastAPI + React + PostgreSQL, arquitectura cliente-servidor) para almacenar, consultar y visualizar mediciones, volumen captado y predicciones.
2. Construir una estación IoT con ESP32 y sensores ambientales y de medición de agua, e integrarla y calibrarla con la plataforma.
3. Desarrollar un modelo de machine learning que prediga el **volumen diario** de agua captada.
4. Realizar un módulo de reportes e indicadores con información histórica y comparativa para la planificación del riego.

---

## 3. Alcance y límites

### Dentro del alcance
- Fabricación e instalación de atrapanieblas físicos con malla Raschel.
- Estación meteorológica IoT con **ESP32, sensor BME680 y caudalímetro**.
- Entrenamiento de un modelo de ML para predecir el volumen captado.
- Dashboard web (React + FastAPI) con datos, predicciones, controles y reportes.
- Pruebas de campo en los invernaderos del C.E.A.: precisión predictiva y eficiencia de riego.

### Fuera del alcance
- Diseño o construcción de invernaderos (se usa la infraestructura existente).
- Tratamiento o potabilización del agua captada.
- Modelos de ML para calidad de agua, suelo o plagas.
- Sistemas de almacenamiento (cisternas, tanques).
- Seguridad avanzada (cámaras, biometría).
- Aplicación móvil e integración con sistemas externos.
- Comercialización del agua captada.

### Delimitaciones
| Tipo | Detalle |
|---|---|
| Temporal | Semestre II de 2026 (agosto a primeros días de diciembre). Ago–sep: documentación; oct: desarrollo de la estación IoT; nov: recolección de mediciones y dataset; dic: pruebas de caja negra y de campo, comparación real vs. estimado |
| Espacial | Predios del C.E.A. en Titicachi, Chuma. 4 invernaderos académicos, 2 estructuras atrapanieblas (el texto indica "20 m" de malla; verificar unidad), laboratorio básico como servidor local |
| Generalización | Los resultados no se extrapolan a otras comunidades |

---

## 4. Requerimientos funcionales

### Módulo IoT y adquisición de datos
| ID | Requerimiento |
|---|---|
| RF-01 | Recopilar temperatura y humedad relativa mediante sensores conectados al ESP32. |
| RF-02 | Recopilar velocidad y dirección del viento cuando se disponga de los sensores. |
| RF-03 | Registrar presencia o intensidad de niebla cuando se implemente el mecanismo de medición del prototipo. |
| RF-04 | Registrar el volumen de agua captado mediante el dispositivo de medición seleccionado. |
| RF-05 | Registrar el nivel de agua almacenada cuando se implemente el sensor correspondiente. |
| RF-06 | El ESP32 debe transmitir las mediciones a la API del servidor local por la red institucional mediante solicitudes HTTP. |

### Módulo de monitoreo hídrico
| ID | Requerimiento |
|---|---|
| RF-07 | Validar los datos recibidos antes de almacenarlos. |
| RF-08 | Guardar cada medición con fecha, hora, sensor y estado de validez. |
| RF-09 | Consultar el historial de mediciones ambientales y operativas. |
| RF-10 | Consultar volumen captado y nivel de almacenamiento por fecha o periodo. |

### Módulo de datos y machine learning
| ID | Requerimiento |
|---|---|
| RF-11 | Organizar las mediciones válidas en un conjunto de datos histórico. |
| RF-12 | Usar un modelo de ML para estimar el volumen captado. |
| RF-13 | Generar predicciones con las variables ambientales y operativas disponibles. |
| RF-14 | Almacenar fecha, variables utilizadas y resultado de cada predicción. |
| RF-15 | Comparar el volumen estimado con el volumen real registrado. |

### Módulo web y usuarios
| ID | Requerimiento |
|---|---|
| RF-16 | Autenticación para usuarios autorizados. |
| RF-17 | Mostrar variables ambientales, volumen captado y nivel de almacenamiento en tablas, indicadores o gráficos. |
| RF-18 | El administrador puede crear, consultar, actualizar y desactivar cuentas. |
| RF-19 | Asignar roles y permisos según las funciones de cada usuario. |

### Módulo de reportes
| ID | Requerimiento |
|---|---|
| RF-20 | Generar reportes históricos de variables ambientales, volumen captado y predicciones. |
| RF-21 | Filtrar reportes por fecha o periodo. |
| RF-22 | Consultar o exportar los reportes en un formato definido para el proyecto. |

---

## 5. Requerimientos no funcionales

| ID | Categoría | Requerimiento |
|---|---|---|
| RNF-01 | Rendimiento | Panel principal y consultas habituales en **máximo 3 s** bajo condiciones normales de la red local. |
| RNF-02 | Comunicación | La estación IoT transmite al servidor mediante HTTP dentro de la red local. |
| RNF-03 | Usabilidad | Formularios, etiquetas y mensajes comprensibles para los usuarios de la institución. |
| RNF-04 | Compatibilidad | Funcionar en navegadores web modernos de las computadoras autorizadas. |
| RNF-05 | Seguridad | Contraseñas almacenadas con **hash seguro**, nunca en texto plano. |
| RNF-06 | Control de acceso | Restringir funciones según el rol del usuario. |
| RNF-07 | Integridad | Validar los datos recibidos antes de guardarlos en la base de datos. |
| RNF-08 | Disponibilidad | El servidor local debe iniciar los servicios principales tras un reinicio, si la configuración institucional lo permite. |
| RNF-09 | Recuperación | La estación IoT informa la pérdida de comunicación o **conserva temporalmente** las mediciones si no puede conectarse. |
| RNF-10 | Escalabilidad | Permitir incorporar nuevos sensores sin rehacer los módulos existentes. |
| RNF-11 | Mantenibilidad | Código modular que separe presentación, lógica de negocio, acceso a datos y procesamiento predictivo. |
| RNF-12 | Trazabilidad | Conservar fecha, hora, sensor y usuario en las operaciones relevantes. |
| RNF-13 | Respaldo | Procedimiento de copia de seguridad de la base de datos definido por el administrador. |
| RNF-14 | Validación predictiva | Informar cuando no existan datos suficientes para generar una predicción. |

---

## 6. Historias de usuario

| ID | Prioridad | Riesgo | Usuario | Historia | Estimación |
|---|---|---|---|---|---|
| HU-01 | Alta | Medio | Usuario autorizado | Ingresar con credenciales para acceder según mi rol | 5 h |
| HU-02 | Alta | Alto | Sistema | Recibir y validar mediciones del ESP32 y almacenarlas | 15 h |
| HU-03 | Alta | Alto | Sistema | Registrar el volumen captado por el atrapanieblas | 15 h |
| HU-04 | Alta | Medio | Sistema | Registrar el nivel de almacenamiento (cuando exista el sensor) | 10 h |
| HU-05 | Alta | Bajo | Director o docente | Consultar variables ambientales, volumen captado y nivel de almacenamiento | 10 h |
| HU-06 | Alta | Medio | Sistema | Organizar mediciones válidas en un dataset para entrenar y validar el modelo | 15 h |
| HU-07 | Alta | Alto | Sistema | Estimar el volumen captado con ML | 20 h |
| HU-08 | Alta | Medio | Director o docente | Comparar volumen real vs. estimado | 10 h |
| HU-09 | Media | Bajo | Director o docente | Consultar y generar reportes por periodo | 10 h |
| HU-10 | Media | Medio | Administrador | Gestionar usuarios y roles | 10 h |

### Product Backlog (resumen)
| Módulo | Prioridad | ID | Elemento | Estimación |
|---|---|---|---|---|
| Análisis | Alta | HU-00 | Relevamiento (cuestionarios, entrevistas, observación) | 5 días |
| Dashboard web | Alta | HU-01 | Autenticación y permisos | 3 días |
| IoT | Alta | HU-02 | Recepción de mediciones | 5 días |
| IoT | Alta | HU-03 | Registro del volumen captado | 5 días |
| IoT | Media | HU-04 | Nivel de almacenamiento | 3 días |
| Dashboard web | Alta | HU-05 | Consulta del monitoreo | 5 días |
| Datos | Alta | HU-06 | Preparación de datos históricos | 6 días |
| Machine learning | Alta | HU-07 | Entrenamiento del modelo | 8 días |
| Machine learning | Alta | HU-08 | Comparación real vs. estimado | 4 días |
| Reportes | Media | HU-09 | Históricos y reportes | 4 días |
| Administración | Media | HU-10 | Gestión de usuarios | 3 días |
| Validación | Alta | HU-11 | Pruebas de caja negra | 5 días |
| Validación | Alta | HU-12 | Pruebas de campo | 5 días |

---

## 7. Arquitectura y tecnologías

### Flujo de datos
`Sensores → ESP32 (conversión de unidades, ID de sensor, fecha/hora, validación básica) → HTTP (red local) → API FastAPI (validación) → PostgreSQL → modelo ML → dashboard`

### Estación IoT
- Microcontrolador **ESP32**, sensor **BME680** (temperatura/humedad), anemómetro, método para dirección del viento, mecanismo de detección de niebla, **caudalímetro** o medición volumétrica y sensor de nivel del tanque.
- Selección final según disponibilidad, costo, rango, precisión y compatibilidad con el ESP32.

### Backend
- **FastAPI** (REST, tipado, validación automática, OpenAPI), organizado en módulos: autenticación, usuarios, procesamiento de datos, reportes.
- **PostgreSQL** para mediciones y datos administrativos.

### Frontend
- **React + TypeScript + Vite**, React Router, Axios, TanStack Query, Tailwind CSS (también se mencionan shadcn/ui y Recharts en la webgrafía).
- La interfaz debe separar el monitoreo hídrico de los módulos administrativos.

### Machine learning
- Python: **Pandas, NumPy, Scikit-learn**, **XGBoost o LightGBM** (regresión basada en árboles), **Matplotlib/Seaborn**, **Joblib** para guardar/cargar el modelo.
- Pipeline: revisión de registros → valores faltantes → codificación de categóricas → normalización/estandarización → selección de variables → split entrenamiento/validación → entrenamiento → evaluación.
- Métricas: **MAE, MSE (error cuadrático medio) y R²**. Se elige el modelo con menor error entre volumen real y estimado.

---

## 8. Metodología

- **Scrum**, adaptado a un equipo de una persona. El documento menciona también "Scrumban" en el índice; unificar el término.
- Sprints: análisis, diseño, desarrollo web, implementación IoT, preparación de datos, machine learning y evaluación.
- Seguimiento con Product Backlog, planificación de Sprints y bitácora de actividades.
- Fases: Pre Game (requerimientos, historias, backlog), Game (análisis y diseño: componentes, casos de uso, secuencia, actividad, clases, físico, despliegue) y Post Game (pruebas).

---

## 9. Pruebas

- **Caja negra** sobre endpoints de la API: códigos HTTP, estructura JSON, reglas de negocio, autenticación y permisos.
- **Caja blanca** sobre lógica interna: cobertura de rutas, validaciones y manejo de errores.
- Criterio de éxito: HTTP esperado, JSON coherente con el esquema y consistencia con las reglas de negocio; en operaciones protegidas, exigir autenticación válida y rechazar usuarios sin permisos.

| ID | Módulo | Caso | Resultado esperado |
|---|---|---|---|
| CB-01/02 | Health | Estado de la API y de la base de datos | HTTP 200 |
| CB-03 | Autenticación | Credenciales correctas | HTTP 200 con token o flujo 2FA |
| CB-04 | Autenticación | Contraseña incorrecta | HTTP 401 |
| CB-05/06 | Autenticación | Perfil con y sin token | 200 / 401 |
| CB-07/08 | IoT | Lectura válida / incompleta | 200-201 / 422 |
| CB-09/10 | Infraestructura | Crear invernadero / consultar inexistente | 200-201 / 404 |
| CB-11 | Riego | Crear decisión de riego | 200-201 |
| CB-12 | Alertas | Crear alerta | 200-201 |
| CB-13 | Umbrales | Crear parámetro | 200-201 |
| CB-14 | ML | Crear predicción | 200-201 con resultado |
| CB-15 | Reportes | Reporte de predicciones | 200 con datos consolidados |
| CB-16 | Usuarios | Crear usuario administrativo | 200-201 |
| CB-17/18 | Solicitudes / Tickets | Crear solicitud / ticket | 200-201 |

Los 18 casos figuran como **Aceptado** en el documento.

---

## 10. Modelo de datos (anexo: diccionario)

- **Catálogos:** roles, estados (usuario, invernadero, atrapaniebla, fuente de agua, dispositivo, sensor, actuador, válvula, alerta, envío, sincronización), tipos (ubicación, fuente, dispositivo, sensor, actuador, notificación), calidad del dato, modos de riego, niveles de riesgo, severidades, ámbitos de umbral.
- **Seguridad:** `usuarios`, `auditoria_acciones`.
- **Infraestructura:** `ubicaciones`, `invernaderos`, `atrapanieblas`, `fuentes_agua`, `fuentes_agua_atrapanieblas`.
- **Dispositivos:** `dispositivos`, `dispositivos_ubicaciones`, `dispositivos_fuentes_agua`, `sensores`, `lecturas_sensor`, `calibraciones_sensor`, `actuadores`, `actuadores_invernaderos`.
- **Machine learning:** `modelos_ml`, `predicciones_ml`, `simulaciones_ml`.
- **Riego:** `decisiones_riego` (+ relaciones con invernaderos, actuadores y fuentes), `metricas_decision_riego`, `eventos_riego`, `estado_riego_actual`.
- **Alertas:** `alertas` (+ por invernadero, dispositivo, sensor, decisión y simulación), `notificaciones_locales`.
- **Umbrales:** `parametros_umbral`, `configuraciones_umbral` (+ por invernadero y sensor).
- **Sincronización y reportes:** `sincronizaciones_mcp`, `reportes_semanales`.

---

## 11. Estado, conclusiones y recomendaciones

### Estado según el propio documento
- Arquitectura y diseño definidos; pruebas de caja negra reportadas como aceptadas.
- **Pendiente:** construcción, instalación y verificación en campo de la estación IoT; base de datos de campo consolidada; entrenamiento del modelo, métricas y comparación real vs. predicho. Todavía no hay evidencia de que el modelo genere estimaciones confiables.

### Recomendaciones
1. Completar la implementación y calibración de la estación IoT y proteger el equipo de la humedad y el clima.
2. Establecer un procedimiento regular de recolección (fecha, hora, variables, volumen, validez).
3. Evaluar el modelo con métricas de error y **reentrenar periódicamente**.
4. Reforzar seguridad: autenticación, roles y copias de seguridad.
5. Elaborar manuales de uso para el personal del C.E.A.

---

## 12. Inconsistencias a revisar en el documento

1. **Alcance vs. implementación:** los RF cubren monitoreo, ML y reportes, pero las pruebas y el diccionario de datos incluyen **riego, actuadores, válvulas, alertas, umbrales, simulaciones, tickets, solicitudes y sincronización MCP**, que no tienen RF asociado. Además, el alcance excluye "integración con sistemas externos".
2. **Módulos administrativos:** la justificación menciona inventario, biblioteca, préstamos y docentes, que no aparecen en los RF ni en el backlog.
3. **Metodología:** Scrum en el texto y Scrumban en el índice.
4. **Autenticación:** CB-03 contempla 2FA, que no figura en los RF ni RNF.
5. **Datos del atrapanieblas:** "20 m" de malla sin unidad clara (¿m² o m?).
6. **Dispositivo de medición:** el alcance fija BME680 y caudalímetro, mientras la justificación técnica deja la selección abierta.
