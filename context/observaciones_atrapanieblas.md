# Observaciones: requerimientos vs. sistema actual e investigación sobre atrapanieblas

> Revisión de `requerimientos_atrapanieblas.md` (secciones 1 a 11; la sección 12 de inconsistencias
> se omitió a pedido) contra el sistema implementado, más una investigación breve sobre atrapanieblas.
> **No se realizó ningún cambio en el sistema.** Fecha: 20/10/2026.

## Resumen

- **Se cumple la mayor parte de los requerimientos de software**: adquisición y validación de
  mediciones, monitoreo, históricos, usuarios, roles, reportes y requerimientos no funcionales de
  seguridad, trazabilidad, respaldo y recuperación de la estación.
- **Pendiente principal: el modelo de machine learning en el sistema** (RF-12 a RF-15, RF-20 en lo
  referido a predicciones, RNF-14 y casos de prueba CB-14 y CB-15). Hoy solo existe una simulación
  fuera de la API, con datos sintéticos.
- **Diferencias de hardware con el documento**: el firmware usa SHT31 + BMP280 (no BME680) y
  pluviómetro de balancín (no caudalímetro), y todavía no lee viento. La investigación respalda el
  pluviómetro de balancín y señala al viento como variable clave (detalle en la sección 3).
- **Hay requisitos del documento que chocan con `AGENTS.md`** (riego, actuadores, alertas y umbrales
  configurables, MCP, simulaciones, 2FA). Requieren una decisión antes de implementarse (sección 2).

---

## 1. Cumplimiento de los requerimientos

Leyenda: ✅ cumple · ⚠️ cumple en parte o con diferencias · ❌ no implementado.

### Requerimientos funcionales

| ID | Estado | Observación sobre el sistema actual |
|---|---|---|
| RF-01 Temperatura y humedad | ✅ | Tipos de sensor y validación de rangos; firmware con SHT31. |
| RF-02 Viento | ⚠️ | El backend admite velocidad y dirección, pero **el firmware no lee anemómetro ni veleta**. |
| RF-03 Niebla | ⚠️ | Tipo `niebla` en el backend; en el firmware es opcional (`HAS_FOG_SENSOR`) y el mecanismo de medición no está definido. |
| RF-04 Volumen captado | ✅ | Pluviómetro de balancín por pulsos, volumen incremental. Falta calibrar `LITERS_PER_PULSE` con el hardware real. |
| RF-05 Nivel almacenado | ✅ | Sensor ultrasónico; nivel y porcentaje de llenado visibles en el módulo Atrapanieblas. |
| RF-06 Envío HTTP a la API local | ✅ | `POST /api/v1/iot/measurements/batch` con credencial propia por dispositivo. |
| RF-07 Validar antes de guardar | ✅ | Estructura, unidades, rangos, fecha futura, dispositivo activo y sensor asociado; sin duplicados. |
| RF-08 Fecha, hora, sensor y validez | ✅ | Fecha de medición y de recepción, sensor y calidad (`valida`, `sin_dato`, `fuera_de_rango`…). |
| RF-09 Historial | ✅ | Histórico de lecturas con filtros. |
| RF-10 Volumen y nivel por periodo | ✅ | Por día, semana, mes o rango; resumen general, análisis estadístico y reportes. |
| RF-11 Conjunto de datos histórico | ⚠️ | Preparado en la simulación (`notebooks/simulacion/preparar_datos.py`); no existe exportación automatizada desde la base. |
| RF-12 Modelo de ML | ❌ | Pendiente por decisión: solo simulación con datos sintéticos. |
| RF-13 Predicciones con variables disponibles | ❌ | Pendiente; la simulación usa solo variables disponibles al cierre del día D. |
| RF-14 Almacenar cada predicción | ❌ | Faltan las tablas `ml_models` y `predictions`. |
| RF-15 Real vs. estimado | ❌ | Solo en la simulación (`comparacion_real_vs_estimado.csv`). |
| RF-16 Autenticación | ✅ | Usuario y contraseña; sesión en cookie HttpOnly. |
| RF-17 Tablas, indicadores y gráficos | ✅ | Resumen general, análisis estadístico (seis tipos de gráfico) y módulo Atrapanieblas. |
| RF-18 Gestión de cuentas | ✅ | Crear, consultar, editar y desactivar, sin borrado físico. |
| RF-19 Roles y permisos | ✅ | RBAC en el backend; roles administrador, director, docente y mantenimiento. |
| RF-20 Reportes históricos | ⚠️ | Variables ambientales y volumen sí; **predicciones, no**, porque dependen del modelo. |
| RF-21 Filtro por fecha o periodo | ✅ | Cada módulo exporta con sus filtros, con atajos de periodo. |
| RF-22 Formato definido | ✅ | CSV, Excel y PDF; el encabezado indica los filtros aplicados. |

### Requerimientos no funcionales

| ID | Estado | Observación |
|---|---|---|
| RNF-01 ≤ 3 s | ✅ | Medido en el servidor con datos de demostración (11 520 lecturas): resumen 16 ms, series 2–4 ms, histórico 34 ms, análisis 133 ms, atrapanieblas 101 ms. **Volver a medir con un año de datos reales**: serían unas 800 000 lecturas o más si se lee cada 5 min. |
| RNF-02 HTTP en red local | ✅ | |
| RNF-03 Usabilidad | ✅ | Interfaz y mensajes en español, con validación en los formularios. |
| RNF-04 Navegadores modernos | ⚠️ | Probado solo en Chromium. Falta probar en Firefox y en los equipos reales del C.E.A. |
| RNF-05 Hash de contraseñas | ✅ | scrypt con sal. |
| RNF-06 Control de acceso | ✅ | Permiso por endpoint: 401 sin sesión, 403 sin permiso. |
| RNF-07 Integridad | ✅ | Validación en la API y restricciones CHECK en PostgreSQL. |
| RNF-08 Arranque tras reinicio | ⚠️ | `restart: unless-stopped` en Docker Compose. Depende de que el servicio Docker esté habilitado al arrancar el servidor; `iniciar.sh` es solo para desarrollo. |
| RNF-09 Recuperación de la estación | ✅ | Cola persistente en LittleFS con reenvío; el panel avisa cuando los datos están desactualizados. |
| RNF-10 Nuevos sensores | ⚠️ | Agregar un sensor de un tipo existente se hace desde la interfaz. **Un tipo de variable nuevo requiere una migración**: no hay API ni pantalla para crear tipos de sensor. |
| RNF-11 Código modular | ✅ | Tres capas; el procesamiento predictivo está separado (`notebooks/`). Falta el servicio de predicción. |
| RNF-12 Trazabilidad | ✅ | Auditoría con usuario, fecha, IP y detalle. |
| RNF-13 Respaldo | ⚠️ | Scripts `backup-loop.sh`, `restore.sh` y `test-restore.sh`; **falta ejecutarlos y probar la restauración en el servidor institucional**. |
| RNF-14 Datos insuficientes | ⚠️ | Implementado en la inferencia de la simulación; falta en la API. |

### Historias de usuario y pruebas

- **HU-01 a HU-06, HU-09 y HU-10**: cubiertas. **HU-07 y HU-08**: pendientes, dependen del modelo.
  **HU-00 (relevamiento) y HU-12 (pruebas de campo)**: no son de software.
- **HU-11 (caja negra)**: 137 pruebas automáticas del backend (pytest) recorren los endpoints con
  códigos HTTP, permisos y reglas de negocio. Además hay 22 pruebas del frontend (Vitest).
- Casos de prueba del documento que hoy **no tienen equivalente** en el sistema:
  - **CB-03**: espera "token o flujo 2FA". El sistema entrega una cookie de sesión (no un token en el
    JSON), y el 2FA está fuera de alcance.
  - **CB-11 (riego), CB-12 (alertas) y CB-13 (umbrales)**: ver la sección 2.
  - **CB-14 y CB-15**: predicciones, pendientes.
- **CB-17 y CB-18** (solicitudes y tickets) corresponden a las solicitudes de recuperación de cuenta
  y a los reportes de incidencia, con otros nombres.

---

## 2. Puntos que requieren una decisión (documento vs. `AGENTS.md`)

El documento menciona elementos que `AGENTS.md` deja expresamente **fuera de alcance**. No se
implementaron. Antes de hacerlo hay que decidir cuál de los dos documentos manda:

| Elemento del documento | Dónde aparece | Situación en `AGENTS.md` |
|---|---|---|
| Interoperabilidad local por **MCP** | "Novedad" (sección 1), tabla `sincronizaciones_mcp` | Excluido ("MCP o FastMCP") |
| **Riego**, decisiones de riego, **actuadores y válvulas** | Modelo de datos y CB-11 | Excluido (control automático de riego y actuadores) |
| **Simulaciones de ML** (`simulaciones_ml`) | Modelo de datos | Excluido (simulación de escenarios) |
| **2FA** | CB-03 | Excluido (2FA por canales externos) |
| **Alertas y umbrales configurables** | CB-12, CB-13 y modelo de datos | No están excluidos, pero tampoco definidos. Hoy hay alertas calculadas (datos desactualizados, stock bajo, avisos de incidencias) y rangos fijos por tipo de sensor; no se pueden crear alertas ni editar umbrales. |
| **XGBoost o LightGBM** | Sección 7 | La pila de `AGENTS.md` solo incluye scikit-learn. La simulación usa `HistGradientBoostingRegressor`, de la misma familia que LightGBM, sin agregar dependencias. |
| **MSE** como métrica | Sección 7 | La simulación informa MAE, RMSE y R². RMSE es la raíz de MSE; se puede agregar MSE sin costo. |
| **4 invernaderos** | Delimitación espacial | El sistema admite cualquier cantidad; los datos de demostración tienen 2. |

Otros puntos del documento a tener en cuenta:
- **Manuales de uso** (recomendación 5): no existen. Hay documentación técnica (`README.md`,
  `docs/`), pero no una guía para el personal del C.E.A.
- **Plazo de datos**: con mediciones solo en noviembre, el modelo se entrenaría con unos 30 días
  de una sola época del año. Alcanza para probar el flujo, no para un modelo confiable
  (ver la sección 3.6).

---

## 3. Investigación sobre atrapanieblas y observaciones para el proyecto

### 3.1 Funcionamiento y diseño

- El **colector estándar de niebla** (Standard Fog Collector, SFC; Schemenauer y Cereceda, 1994)
  es un panel de **1 m²** de malla Raschel con **coeficiente de sombra del 35 %**, con su base a
  **2 m del suelo** y colocado **perpendicular al viento**. Ese 35 % describe la malla, **no** su
  eficiencia de captación.
- Los **atrapanieblas grandes** suelen tener **40 m²** de malla. Según FogQuest, uno produce en
  promedio unos **200 L/día** a lo largo del año (≈ 5 L/m²·día), con días sin agua y días de hasta
  1000 L. Cuestan entre 1000 y 1500 USD y duran unos 10 años.
- La niebla se capta sobre todo por **impactación** de gotas de 5 a 50 μm en fibras de alrededor
  de 1 mm. La malla de plástico se curva con el viento, y parte del agua cae fuera de la canaleta.

**Para el proyecto:** el sistema ya registra área y tipo de malla, orientación, altitud y
coordenadas de cada atrapanieblas, y calcula el rendimiento en L/m²·día. Conviene **instalar un SFC
de 1 m² junto a los atrapanieblas grandes**: es la referencia que permite comparar el sitio con la
literatura y sirve también como medidor de la intensidad de la niebla (RF-03).

### 3.2 Rendimientos de referencia

| Fuente | Dato | Equivalente |
|---|---|---|
| Revisión de varios sitios | 0,1 a 10 L/m²·día según el lugar y la niebla | — |
| FogQuest, colector de 40 m² | ≈ 200 L/día de promedio anual | ≈ 5 L/m²·día |
| Peña Blanca (Coquimbo, Chile), 252 m² | ≈ 500 000 L/año | ≈ 5,4 L/m²·día |
| El Verde (Chota, Cajamarca, Perú), malla Raschel de 3,75 m | 5,3–16,4 L/día (época lluviosa); 1,8–7,9 L/día (seca) | ≈ 1,4–4,4 y 0,5–2,1 L/m²·día, si la medida es en m² |

**Observaciones:**
- La cifra del documento (**3–5 L/m²·día**) coincide con sitios buenos y conocidos. Para Titicachi
  debe tomarse como **hipótesis por verificar**: el rango real varía en dos órdenes de magnitud
  según el sitio.
- La época del año pesa mucho; en Cajamarca, la época seca rinde menos de la mitad.
- Los datos sintéticos de la simulación dan ~0,3–0,9 L/m²·día. No son un dato del sitio: solo
  prueban el flujo.
- No encontré estudios publicados con rendimientos en el norte de La Paz. Hay antecedentes en
  Bolivia (Valles Cruceños, ONG Zabalketa, 2018), sin cifras públicas. **Los datos del C.E.A.
  serían un aporte local.**

### 3.3 Viento: la variable que más influye

- La eficiencia de la malla **depende fuertemente de la velocidad del viento**. En 3419 muestras en
  California, la Raschel captó un 160 % más que otra malla con vientos menores a 1 m/s, pero un 45 %
  menos con vientos mayores a 5 m/s.
- Las mallas monofilamento y tridimensionales suelen rendir más que la Raschel tejida. Una malla de
  acero inoxidable con recubrimiento hidrofóbico superó a la Raschel a todas las velocidades
  probadas. En un estudio, la Raschel de 5 capas llegó al 55,3 % de eficiencia.

**Observaciones:**
- Hoy el firmware **no mide viento** (RF-02). Por lo anterior, para el modelo de ML el viento es
  **casi tan importante como la niebla**. Conviene priorizar el **anemómetro** y la **veleta** sobre
  otros sensores opcionales.
- La **dirección del viento** sirve además para verificar la orientación de la malla. El sistema ya
  guarda la orientación de cada atrapanieblas.
- Si más adelante se prueban otras mallas, el sistema permite registrar el tipo de cada una y
  comparar su rendimiento.

### 3.4 Medición del volumen: pluviómetro de balancín, mejor que caudalímetro

- En la práctica, el agua de niebla se mide con **lecturas manuales diarias** (opción de bajo costo
  de FogQuest) o con un **pluviómetro de balancín con registro horario**. En Gobabeb (Namibia), por
  ejemplo, se usa un colector cilíndrico tipo Juvik sobre un pluviómetro de balancín Young 52202.
- En esa misma serie se **descartan los eventos falsos de niebla**: lluvia, llovizna o viento fuerte
  coincidentes, o humedad relativa menor al 70 %.

**Observaciones:**
- El escurrimiento de un atrapanieblas es **un goteo** (litros por hora, no por minuto). Los
  **caudalímetros de turbina** habituales necesitan caudales mucho mayores para registrar, así que
  medirían mal o nada. Esto es una inferencia a partir de los caudales de referencia, no un dato
  medido. La elección actual del firmware (**pluviómetro de balancín por pulsos**) es la adecuada.
  Conviene corregir el documento, que dice "caudalímetro".
- **Calibración:** verter volúmenes conocidos y ajustar `LITERS_PER_PULSE`. Ya figura como
  pendiente en `tareas.md`.
- **La lluvia también cae en la malla y en el colector.** Para no mezclarla con la niebla, conviene
  marcar los días de lluvia, por ejemplo con humedad, presión y observación, o con un pluviómetro
  abierto aparte. Hoy el sistema no separa lluvia de niebla.
- La regla de Gobabeb (descartar eventos con humedad < 70 % o con lluvia) es simple y podría servir
  para validar los datos del modelo.

### 3.5 Sensores de humedad en niebla

- En condiciones de condensación, los sensores de humedad tipo BME280/BME680 pueden **quedar
  marcando 100 %** hasta secarse y necesitar un ciclo de secado. La serie SHT3x tiene un
  **calefactor interno** que ayuda a recuperarlos.
- En otra experiencia, un BME680 dentro de un abrigo meteorológico (Stevenson) funcionó más de un
  año con niebla, lluvia y nieve.

**Observaciones:**
- El SHT31 del firmware es una buena elección frente al BME680 del documento.
- Hay que montar el sensor en un **abrigo con ventilación** y considerar activar el calefactor
  periódicamente.
- Un **100 % persistente** debería revisarse como posible sensor saturado, no como niebla
  confirmada. Este dato engañaría al modelo.

### 3.6 Machine learning

- No encontré estudios publicados que **predigan el volumen captado** con bosques aleatorios o
  gradient boosting. Lo más cercano predice la **frecuencia de niebla** (California, con LightGBM y
  XGBoost) o **clasifica zonas con potencial** (India). Es una brecha en la literatura y un posible
  aporte del proyecto, pero también significa que **no hay métricas de referencia** con qué
  comparar.

**Observaciones:**
- El horizonte supuesto en la simulación (volumen del día D+1 con datos hasta el cierre de D)
  coincide con el "volumen diario" del documento. Falta **confirmarlo** formalmente, como exige
  `AGENTS.md`.
- **Variables con más fundamento** según lo revisado:
  - Velocidad y dirección del viento.
  - Humedad cercana a la saturación (horas ≥ 95 %).
  - Intensidad de la niebla, idealmente medida con el SFC.
  - Época del año.
  - Volumen de los días anteriores.
- **Con un solo mes de datos** (noviembre), el modelo apenas podrá compararse con referencias
  simples: persistencia (mañana igual a hoy) y media de 7 días. Hay que informarlo así en la
  defensa y **reentrenar cuando haya más meses**.
- Como no hay referencias publicadas, conviene **comparar siempre contra esas referencias simples**.
  La simulación ya lo hace.

### 3.7 Datos reales disponibles (`data/último paquete.csv`)

El sistema procesó el archivo; no se leyó su contenido directamente. Resultados:
- **15 horas** de lecturas cada 10 s, con 3 reinicios del ESP32.
- **Sin fecha ni hora real**: el tiempo es un contador de segundos desde el encendido.
- **Sin volumen** captado.
- La **presión mediana es de 861 hPa**. A la altitud de Titicachi (~3100 m) la atmósfera estándar
  da **≈ 690 hPa**: 861 hPa corresponde a unos 1300 m. Hay que **calibrar el sensor de presión** o
  confirmar dónde se tomaron los datos.
- Picos de temperatura de ~46 °C, posiblemente por sol directo o calor dentro de la caja. Confirma
  la necesidad del abrigo ventilado de la sección 3.5.

**Para el firmware:** sincronizar la hora (NTP en la red local, o un reloj RTC) antes de registrar.
El firmware actual ya se niega a guardar lecturas sin hora válida, pero estos datos provienen de
otra versión.

---

## 4. Recomendaciones priorizadas

1. **Decidir los puntos de la sección 2** (MCP, riego y actuadores, simulaciones, 2FA, alertas y
   umbrales) y alinear el documento con `AGENTS.md`, o al revés.
2. **Confirmar el horizonte de predicción y las variables**, para habilitar la implementación del
   modelo en el sistema (RF-12 a RF-15, RNF-14, CB-14 y CB-15).
3. **Hardware:**
   - Agregar anemómetro y veleta.
   - Definir la medición de niebla, idealmente un SFC de 1 m² con su propio pluviómetro de balancín.
   - Usar un abrigo ventilado para el sensor de temperatura y humedad.
   - Calibrar el pluviómetro de balancín y el sensor de presión.
   - Sincronizar la hora (NTP o RTC).
4. **Separar lluvia de niebla** en los datos: por ejemplo, con una marca de día lluvioso o un
   pluviómetro abierto.
5. **Recolectar datos durante el mayor tiempo posible**, idealmente una época húmeda y una seca, y
   reentrenar el modelo a medida que haya más meses.
6. **Operación:**
   - Probar la restauración de respaldos en el servidor real.
   - Habilitar Docker al arranque.
   - Probar en los navegadores y equipos del C.E.A.
   - Volver a medir los tiempos de respuesta con datos reales.
7. **Manual de uso** para el personal del C.E.A. (recomendación 5 del documento).

---

## Fuentes

- Schemenauer, R. S. y Cereceda, P. (1994). *A Proposed Standard Fog Collector for Use in
  High-Elevation Regions*. Journal of Applied Meteorology, 33(11), 1313–1322. Citado en:
  [Optimal Design of Multi-Layer Fog Collectors (arXiv)](https://arxiv.org/pdf/2001.09953) y
  [Shi et al., MIT](https://dspace.mit.edu/bitstream/1721.1/109556/1/Optimal%20design.pdf).
- [Fernández et al. (2018), *Fog Water Collection Effectiveness: Mesh Intercomparisons* (FogQuest)](https://www.fogquest.org/wp-content/uploads/2023/07/i-Fernandez-2018-Fog-Water-aaqr-17-01-fog-0040.pdf)
- [Montecinos et al. (2018), *Fog collection efficiency* (FogQuest)](https://www.fogquest.org/wp-content/uploads/2022/08/c-Montecinos-et-al-Fog-collection-effic_AR-2018.pdf)
- [Holmes et al. (2015), *Large fog collectors: new strategies…* (FogQuest)](https://www.fogquest.org/wp-content/uploads/2023/07/i-Holmes-et-al-2015-Large_fog_collectors_New_strategies_for.pdf)
- [Estudio de mallas Raschel multicapa (Journal AUT)](https://journals.aut.ac.ir/article_5372_0f43328079a6ddf73d6453b8123308ec.pdf)
- [Water Yield of a Fog Harvester as Affected by Mesh Material and its Orientation](https://journals.bsu.edu.ph/mjsir/article/view/153)
- [Estudio de 2026 sobre mallas en Chile (Technical Geography)](https://technicalgeography.org/pdf/2_2026/13_cepeda.pdf)
- [FogQuest — preguntas frecuentes](https://fogquest.org/f-a-q/) y [FogQuest — nuevo registrador de datos](https://www.fogquest.org/latest-news/new-data-logger-being-tested)
- [FogQuest — Manual de captación de agua de niebla (2022)](https://fogquest.org/videos-information/fogquest-manual/)
- [SSWM — Fog drip (atrapanieblas)](https://sswm.info/water-nutrient-cycle/water-sources/hardwares/precipitation-harvesting/fog-drip)
- [Schemenauer et al. (2004), colectores de niebla en Hajja, Yemen (FogQuest)](https://www.fogquest.org/wp-content/uploads/2023/07/i-Schemenauer-et-al-2004-Fog-Collection-Hajja.pdf)
- [Gobabeb, Namibia — serie anual de niebla con pluviómetro de balancín (B2FIND)](https://b2find.eudat.eu/dataset/3fcb40ea-aae1-5b22-adc2-366e545bd9cf)
- [Atrapanieblas en Chota, Cajamarca (SINIA, MINAM Perú)](https://sinia.minam.gob.pe/documentos/uso-innovador-atrapanieblas-mitigar-estres-hidrico-promover) y [nota de política (PDF)](https://sinia.minam.gob.pe/sites/default/files/archivos/public/docs/POLICYBRIEFSRSTEVINMANUELBECERRAREGALADOvf1_0.pdf)
- [Cosecha de aguas en Peña Blanca, Chile (El Ciudadano)](https://www.elciudadano.com/?p=149589)
- [Neblinómetros y el proyecto de Zabalketa en Bolivia (UPV/EHU)](https://www.ehu.eus/documents/d/gipuzkoako-ingeniaritza-eskola/inigo-neblinometros) y [EGU21-4529](https://meetingorganizer.copernicus.org/EGU21/EGU21-4529.html)
- [Uso de atrapanieblas en Latinoamérica (Revista Repertorio, UNED)](https://revistas.uned.ac.cr/index.php/repertorio/article/download/4249/6443/20492)
- [EGU26-8182 — predicción de frecuencia de niebla con RF, LightGBM y XGBoost](https://meetingorganizer.copernicus.org/EGU26/EGU26-8182.html)
- [Potencial de agua de niebla con Gradient Boosting, Pithoragarh (UTS)](https://opus.lib.uts.edu.au/bitstream/10453/191546/2/1-s2.0-S1474706525002888-main.pdf)
- Sensores de humedad en condensación: [Arduino Forum](https://forum.arduino.cc/t/robust-humidity-sensor/697994), [Core Electronics Forum](https://forum.core-electronics.com.au/t/how-to-prevent-outdoor-temperature-humidity-sensors-from-having-wildly-incorrect-humidity-readings/20660), [Bosch Sensortec Community](https://community.bosch-sensortec.com/t5/MEMS-sensors-forum/BME680-Humidity-Inaccuracy/m-p/20072). Son experiencias de foros, no datos de fabricante.
- Presión esperada a 3100 m: cálculo propio con la atmósfera estándar internacional.
