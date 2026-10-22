# Revisión del informe final: inconsistencias

Documento revisado: `docs/Documentos/Informe final fusionado APA 6.docx` (versión del 22/10/2026).

Este archivo tiene dos partes. La primera resume lo que ya se corrigió en el documento. La segunda lista lo que sigue pendiente: son puntos que necesitan una decisión o un dato del autor, porque cambian el contenido técnico o dependen de información de la institución.

Los números de tabla, figura y sección corresponden a la versión revisada.

---

## 1. Correcciones aplicadas

### 1.1 Solicitadas

| Corrección | Qué se hizo |
|---|---|
| Índices automáticos | El índice general, el de figuras y el de tablas se generaron con las herramientas de índice (campos TOC). Se actualizan en Word con clic derecho › *Actualizar campo* › *Actualizar toda la tabla*. |
| Introducción | Dos párrafos nuevos que explican el proyecto: estación IoT, validación y visualización de datos, modelo de predicción, módulos administrativos y funcionamiento en red local. |
| Misión y visión | Agregadas en 1.2.1 como citas en bloque, tomadas de Calderon Apanqui, Condori Quispe y Ticona Huanca (2014, pp. 3–4). La referencia se añadió a la bibliografía. |
| Antecedentes del problema | Dos párrafos nuevos: la dependencia del ojo de agua comunitario y la falta de registros meteorológicos e hídricos. |
| Antecedentes del proyecto | Fila «Autor» en las cinco tablas. Hay tres autores verificados en la fuente; los otros dos siguen pendientes (ver 2.4). |
| Delimitación de contenido | Párrafo que describe los módulos del sistema antes de 3.3.1. Los alcances pasaron de 5 a 11, frente a 7 límites. |
| Metodología Scrum (5.1) | Reducida a tres párrafos (qué es Scrum, por qué se usa y cómo se adapta). Los sprints van en la Tabla 6. |
| Requerimientos | Los funcionales (22) y no funcionales (14) están en las Tablas 7 y 8. |
| Historias de usuario | Ordenadas por prioridad (Alta → Media) y, dentro de cada prioridad, por riesgo (Alto → Bajo). |
| Tablas y figuras | Número y título debajo, centrados y en 11 pt, seguidos de «Fuente: …». Se numeraron las tablas y figuras que no tenían número. |
| «plataforma» → «sistema» | Se cambiaron 16 menciones y se ajustó el artículo («la plataforma» → «el sistema»). Se mantuvo «plataforma Ubidots» (Tabla 3), porque Ubidots es un producto externo y no el sistema del proyecto. |
| Formato general | Arial 12, interlineado doble, sangría de primera línea de 1,27 cm y texto justificado. |

Excepciones al formato general, para respetar APA 6:

- **Tablas:** interlineado sencillo, 10 pt y alineación a la izquierda, porque el justificado abre huecos en columnas estrechas.
- **Títulos de tablas y figuras:** 11 pt, centrados.
- **Referencias:** sangría francesa y alineación a la izquierda. APA 6 (§ 8.03) recomienda no justificar, y las líneas con URL quedan con grandes espacios.
- **Citas en bloque** (40 palabras o más): sangría izquierda de 1,27 cm, sin comillas y con la página al final.

### 1.2 Detectadas durante la revisión y ya corregidas

- **Antecedente 3 (Tabla 3).** El informe atribuía el trabajo a «Torres et al., UPTC». El artículo es de Cortés Rojas y Caicedo Rojas (2022), de la Fundación Universitaria de San Gil (UNISANGIL), y está publicado en *Ciencia Latina*, 6(6). Se corrigieron el autor, la institución y la referencia.
- **Antecedente 5 (Tabla 5).** El título aparecía duplicado. La referencia «Universidad de Alcalá (2023)» se reemplazó por la autora: Irazábal Ortiz (2023).
- **Antecedente 2 (Tabla 2).** El autor figura como el consorcio del proyecto LIFE Nieblas (ICIA, Cabildo de Gran Canaria, Gesplan, ITC y CREAF, entre otros socios). Quién coordina el proyecto sigue sin confirmar (ver 2.4).
- **Erratas.** Se corrigieron 40, por ejemplo «lluevia», «funcionamieneto», «factivilidad» y «delas».
- **Nombre de la institución.** «Idelfonso» pasó a «Ildefonso» en el título del organigrama.
- **Referencias duplicadas.** Se eliminaron las repetidas de FastAPI, React y PostgreSQL.
- **Numeración.** Se rehízo la del marco teórico, se renumeraron las ecuaciones (1 a 4) y se reubicó la sección 4.7.4.

---

## 2. Inconsistencias pendientes

### 2.1 Contenido que no corresponde al alcance del sistema

| Ubicación | Inconsistencia | Acción sugerida |
|---|---|---|
| Introducción; 1.2.3 | Se habla de «interoperabilidad local mediante MCP» y de «monitoreo IoT en tiempo real». MCP está fuera del alcance. Además, la estación envía lotes de mediciones por HTTP, lo que no es tiempo real estricto. | Eliminar la mención a MCP. Usar «monitoreo continuo» o «monitoreo periódico». |
| 5.4.2 Pruebas de software | El sistema aparece como «Sistema Inteligente de Optimización, Recolección y Predicción de Agua mediante Machine Learning y Atrapanieblas». | Usar el título del proyecto. |
| 5.4.2 y 5.4.2.1 (CB-01 a CB-18) | Las pruebas de caja negra incluyen módulos de riego, alertas, umbrales, solicitudes y tickets. También usan endpoints que no existen en la API: `POST /api/v1/iot/lecturas`, `/invernaderos`, `/riego/decisiones`, `/alertas`, `/umbrales/parametros`, `/ml/predicciones`, `/solicitudes` y `/tickets`. | Rehacer los casos con los endpoints reales, por ejemplo `POST /api/v1/iot/measurements/batch`, `GET /api/v1/measurements`, `POST /api/v1/predictions`, `GET /api/v1/reports/export`, `/api/v1/inventory/...` y `/api/v1/maintenance`. |
| 5.4.2.3; Conclusiones | La conclusión de la validación menciona «monitoreo en tiempo real» e «interoperabilidad». Las conclusiones se apoyan en pruebas de caja negra hechas sobre esos endpoints inexistentes y no mencionan los módulos de inventario, mantenimiento, incidencias ni recuperación de cuenta. | Actualizarlas después de rehacer las pruebas. |
| Anexos: diccionario de datos (Tablas 29, 33 y 34, entre otras) | Incluye actuadores, decisiones de riego, umbrales, sincronización MCP y simulación de escenarios con ML. El sistema no controla el riego, no usa MCP y no simula escenarios. | Regenerar el diccionario desde el esquema real de la base de datos (modelos SQLAlchemy y migraciones Alembic). |
| 3.3.1 Alcance | «…midiendo precisión predictiva y eficiencia de riego». El sistema apoya la planificación del riego, pero no lo controla ni lo mide. | «…midiendo la precisión predictiva y la utilidad de la información para planificar el riego». |
| 2.1 Justificación técnica; 2.3 Justificación social | Mencionan libros, préstamos, biblioteca, disponibilidad de docentes y áreas de enseñanza. Parece texto de otro proyecto. | Eliminarlo y describir los módulos reales: inventario de repuestos, mantenimiento e incidencias. |

### 2.2 Hardware y tecnologías

| Ubicación | Inconsistencia | Acción sugerida |
|---|---|---|
| 3.3.1 Alcance | Se habla de «sensor BME680 y caudalímetro». El firmware usa SHT31 (temperatura y humedad), BMP280 (presión), un pluviómetro de balancín o caudalímetro por pulsos (volumen) y JSN-SR04T (nivel del tanque). | Unificar con el firmware (`firmware/README.md`). |
| 2.1 Justificación técnica | Se prevén un anemómetro y un sensor de dirección del viento, que el firmware actual no incluye. | Presentarlos como opcionales: «si el sensor está disponible». |
| 2.1; 4.10; 4.17.1 | El modelo usaría XGBoost o LightGBM, y los gráficos se harían con Matplotlib y Seaborn. El stack definido usa pandas, NumPy, scikit-learn y joblib, y los gráficos del sistema se generan con Recharts. | Si se compararán algoritmos en la etapa experimental, aclarar que en producción habrá un único modelo. Si no, quitar XGBoost y LightGBM o justificarlos como dependencia adicional. Matplotlib y Seaborn solo tienen sentido en los cuadernos de análisis. |

### 2.3 Requerimientos, historias de usuario y backlog

| Ubicación | Inconsistencia | Acción sugerida |
|---|---|---|
| 5.2.2 (Tablas 7 y 8) | Los requerimientos funcionales cubren cinco módulos: IoT, monitoreo hídrico, datos y ML, reportes, y web y usuarios. Faltan inventario de repuestos, mantenimiento, incidencias, recuperación de cuenta, auditoría y análisis estadístico, aunque figuran en la delimitación (3.3) y en los casos de uso CU-01 a CU-14. | Añadir requerimientos funcionales para esos módulos. |
| 5.2.3 y 5.2.4 (Tablas 9 y 10) | El Product Backlog tiene HU-00, HU-11 y HU-12, que no tienen historia de usuario en la Tabla 9. | Agregar las historias o quitar esos ID del backlog. |
| 5.2.3 (Tabla 9) | HU-02, HU-03, HU-04, HU-06 y HU-07 empiezan con «Como sistema, quiero…». Una historia de usuario se escribe desde un rol humano. | Reformularlas, por ejemplo: «Como administrador, quiero que el sistema reciba las mediciones de la estación…». |
| Capítulo 5 | Los procesos de los casos de uso (incidencias, recuperación de cuenta, mantenimiento y periodo de inventario) no tienen historias ni elementos en el backlog. | Alinear el backlog, las historias y los casos de uso. |
| Diagramas de secuencia | CU-14 (Exportar resumen y acta del periodo) no tiene diagrama de secuencia. | Agregarlo o indicar que sigue el mismo flujo que CU-06. |

### 2.4 Antecedentes y fuentes

| Ubicación | Inconsistencia | Acción sugerida |
|---|---|---|
| Tabla 1 | El autor no está verificado: no se encontró la publicación de «ONG LIDER + Universidad San Francisco Xavier». | Completarlo con la fuente original o reemplazar el antecedente. |
| Tabla 4 | El autor de Katxaña Urna (UMSA) no está verificado. El año tampoco coincide: la tabla dice 2024 y la referencia, 2018. En la bibliografía figura «Katxaa Urna», sin la ñ. | Verificarlo en el repositorio de la UMSA y unificar año y título. |
| Tabla 2 (LIFE Nieblas): autor | Las fuentes no coinciden sobre quién coordina el proyecto. iAgua y elDiario.es (febrero de 2023) dicen que lo lidera el ICIA (Gobierno de Canarias). RTVC (diciembre de 2024) presenta a dos técnicos del Cabildo de Gran Canaria como «coordinadores del proyecto LIFE Nieblas». La referencia bibliográfica está a nombre del Cabildo. | Confirmar el beneficiario coordinador en la base de datos de proyectos LIFE de la Comisión Europea y ajustar la tabla y la referencia. |
| Tabla 2 (LIFE Nieblas): cifras | Las cifras del resumen (215.000 L anuales, 33 ha reforestadas, 2 millones de euros de la UE y más de 10 L/m² al día) no coinciden con lo publicado. iAgua (7/2/2023) informa 75.000 L captados desde 2021, 15 ha reforestadas y una inversión de más de 2 millones de euros, financiada en un 55 % por la UE y en un 33 % por el Cabildo. | Corregirlas con una fuente citable, de preferencia los informes oficiales del proyecto. |
| Tabla 3 | El resumen menciona ESP32, DHT22, transmisión GSM, almacenamiento MySQL, mapas SIG y 6 meses de despliegue a 2.500 msnm. Nada de eso aparece en el artículo. | Reemplazar el resumen por la propuesta que sigue a esta tabla. |
| 4.6.4; 4.11 | Se cita a Agbo, Al-Aqrabi, Hill y Alsboui (2022), pero no tienen referencia. | Añadir la referencia. |
| 4.17 | Se cita a Python Software Foundation (2026), sin referencia. | Añadir la referencia. |
| 4.15.1; 4.15.2; 5.4.1 | Se citan ISO/IEC 25010:2023, ISO/IEC 27002 y OWASP API Security Top 10 (2023), sin referencias. | Añadir las referencias. |
| Webgrafía | «SciELO Colombia. (2023). Captadores de niebla y recolección de agua en un ecosistema de...»: el título está truncado y figura como autor el repositorio, no los autores del artículo. | Citar el artículo con sus autores y su título completo. |
| 1.2.1 | «Fundada en 1995» y «más de 25 años de trayectoria» no tienen fuente. El trabajo de Calderon Apanqui et al. (2014) no da el año de fundación. | Confirmarlo con la institución y citar la fuente. |

Propuesta de resumen para la Tabla 3, basada en el artículo:

> Prototipo funcional IoT para evaluar la viabilidad de instalar un atrapanieblas tipo chileno en Chiquinquirá (Boyacá, Colombia). Integra un Arduino MKR1000 WiFi y una Raspberry Pi 4 con un pluviómetro y sensores de velocidad y dirección del viento, temperatura, humedad relativa y presión atmosférica. Los datos se transmiten mediante MQTT (Mosquitto), se almacenan y visualizan en Node-RED y se respaldan en Ubidots para consultarlos de forma remota. Los autores concluyen que el prototipo permite decidir si conviene una inversión a gran escala en un sitio determinado.

### 2.5 Datos de la institución

| Ubicación | Inconsistencia | Acción sugerida |
|---|---|---|
| Introducción; 3.3.1; 3.5; Figura 1 | El nombre aparece como «Centro de Educación Alternativa Cetha Ildefonso de las Muñecas», «C.E.A. Cetha Ildefonso de las Muñecas», «C.E.A. “Ildefonso de las Muñecas”» y «CEA Ildefonso de las Muñecas». | Confirmar el nombre oficial y usarlo siempre igual. Por ejemplo, la primera vez «Centro de Educación Alternativa (C.E.A.) “Ildefonso de las Muñecas”» y después «C.E.A. “Ildefonso de las Muñecas”». |
| 3.5 Delimitación espacial | Se mencionan «4 invernaderos académicos» y «2 estructuras atrapanieblas (20 m² malla)» sin fuente ni registro. | Confirmarlo con la institución e indicar el origen del dato (visita, entrevista o inventario). |

### 2.6 Contenido incompleto (resaltado en amarillo en el documento)

1. 1.2.3: autor de las Tablas 1 y 4.
2. Marco teórico, después de 4.10.2: definición de machine learning.
3. 4.15.1: métricas de calidad.
4. 4.15.2: pruebas de caja negra.
5. 4.17.1: metodología Scrum.
6. 4.17.1: herramientas tecnológicas (COCOMO, VAN, TIR, PostgreSQL y demás).
7. 5.2.1: identificación de roles Scrum.
8. 5.2.5: Sprint Backlog.
9. 5.4.1: seguridad del software (controles ISO/IEC 27002 aplicados).

### 2.7 Figuras

| Ubicación | Inconsistencia | Acción sugerida |
|---|---|---|
| Figuras 25 a 28 | Los cuatro diagramas de actividad se titulan igual: «Diagrama de actividad». | Darles títulos distintos según el proceso que representa cada uno. |
| Figuras 29 a 33 | Los títulos son irregulares: «Diagrama de clases», «Diagrama de Clases (continuación)» y «Diagrama clases de bajo nivel». | Unificar mayúsculas y redacción. |
| Figuras 2 y 25 a 35 | Son diagramas del informe base y no se revisaron contra el sistema actual. Pueden contener elementos fuera de alcance, como en el diccionario de datos. | Revisarlos y actualizarlos si corresponde. |

---

## 3. Al abrir el documento en Word

- Word preguntará si quiere actualizar los campos. Responda **Sí** para que los índices tomen la paginación de Word.
- Después de completar las secciones pendientes, actualice los tres índices: clic derecho › *Actualizar campo* › *Actualizar toda la tabla*.

## Fuentes consultadas

- Calderon Apanqui, D., Condori Quispe, C., & Ticona Huanca, H. (2014). ESFM «Warisata». <https://red.minedu.gob.bo/repositorio/fuente/26910.pdf>
- Cortés Rojas, H. F., & Caicedo Rojas, E. (2022). *Ciencia Latina*, 6(6). <https://ciencialatina.org/index.php/cienciala/article/view/4161>
- Irazábal Ortiz, B. (2023). Universidad de Alcalá. <https://ebuah.uah.es/dspace/handle/10017/58272>
- iAgua (7/2/2023). Avances del proyecto LIFE Nieblas. <https://www.iagua.es/noticias/gobierno-canarias/icia-logra-importantes-avances-proyecto-captacion-agua-niebla-gran>
- elDiario.es (2023). Un proyecto que recoge agua de niebla logra captar 75.000 litros y reforestar 15 hectáreas en Gran Canaria. <https://www.eldiario.es/canariasahora/ciencia_y_medio_ambiente/proyecto-recoge-agua-niebla-logra-captar-75-000-litros-reforestar-15-hectareas-gran-canaria_1_9928872.html>
- RTVC. El Cabildo de Gran Canaria presenta su proyecto LIFE Nieblas. <https://rtvc.es/el-cabildo-de-gran-canaria-presenta-su-proyecto-life-nieblas/>
- Schwaber, K., & Sutherland, J. (2020). *The Scrum Guide*. <https://scrumguides.org/scrum-guide.html>
