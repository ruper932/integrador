# Modelo de machine learning para predecir el volumen captado

> Explicación del modelo propuesto para el sistema: qué predice, qué algoritmo usa y por qué, con
> qué variables, cómo se evalúa y qué falta para usarlo con datos reales.
>
> **Estado:** el modelo está **probado en una simulación con datos sintéticos** y es el único
> modelo previsto. Todavía **no se integró** al sistema, porque faltan datos reales y confirmar el
> horizonte de predicción y las variables. Las cifras de este documento salen de esa simulación y
> **no** indican el desempeño real.

---

## 1. Qué problema resuelve

El C.E.A. necesita saber **cuánta agua aportarán los atrapanieblas** para planificar el riego de
los invernaderos. El modelo responde:

> **¿Cuántos litros captará el atrapanieblas mañana (día D+1), con la información disponible al
> cierre de hoy (día D)?**

| Aspecto | Decisión propuesta |
|---|---|
| Tipo de problema | **Regresión**: el resultado es un número (litros), no una categoría. |
| Objetivo | Volumen total captado el **día siguiente**, en litros. |
| Granularidad | **Diaria**, en hora de Bolivia. El documento de requerimientos pide predecir el "volumen diario". |
| Entradas | Solo datos medidos **hasta el cierre del día D**. Nunca datos del día que se predice. |
| Cantidad de modelos | **Uno solo**, como exigen `AGENTS.md` y el objetivo específico 3. |

⚠️ El horizonte D+1 es **un supuesto pendiente de confirmar**. Si para planificar el riego sirve
más otro horizonte, por ejemplo el total de la semana, se cambia la preparación de datos y el resto
del enfoque se mantiene.

---

## 2. El algoritmo elegido: Gradient Boosting con histogramas

Se usa **`HistGradientBoostingRegressor`** de scikit-learn.

### Cómo funciona, en pocas palabras

Construye **muchos árboles de decisión pequeños, uno tras otro**. Cada árbol aprende a corregir el
error de los anteriores. La predicción final es la suma de todos. Por ejemplo, un árbol puede
aprender que *"si hubo más de 6 horas con humedad ≥ 95 % y el viento estuvo entre 3 y 6 m/s, el
volumen sube"*. El siguiente árbol ajusta lo que el primero no explicó.

La palabra «histogramas» indica que agrupa los valores de cada variable en intervalos. Así entrena
rápido, incluso en equipos modestos. Es la misma técnica de **LightGBM**, que menciona el documento
de requerimientos.

### Por qué este algoritmo

| Razón | Por qué importa en este proyecto |
|---|---|
| **Capta relaciones no lineales y umbrales** | La captación no crece en línea recta: casi no hay agua hasta que la humedad se acerca a la saturación. La eficiencia de la malla tiene un **óptimo de viento**, y con poco o demasiado viento capta menos. Los árboles representan esos umbrales y combinaciones sin fórmulas a mano. |
| **Admite valores faltantes sin rellenarlos** | Si un sensor falla, el dato queda **vacío (`null`), nunca 0**, como exige el proyecto. Este modelo aprende qué hacer con el vacío. Rellenarlo con 0 diría falsamente "no hubo humedad" o "no hubo viento". |
| **No necesita normalizar ni escalar** | Los árboles comparan con umbrales y no dependen de la escala. El paso de normalización y estandarización que menciona el documento no hace falta, y se elimina una fuente de error. |
| **Funciona bien con pocos datos tabulares** | Habrá cientos de días, no millones. Con pocos datos, los modelos de árboles suelen rendir mejor que las redes neuronales en datos de tabla. |
| **Rápido y liviano** | Entrena en segundos en el servidor local, sin GPU ni Internet. Se guarda como un archivo versionado (`joblib`). |
| **Sin dependencias nuevas** | scikit-learn ya está en la pila de `AGENTS.md`. XGBoost y LightGBM, que menciona el documento, son la misma familia de técnicas, pero agregarían bibliotecas que requieren aprobación. |
| **Explicable** | Se puede medir **cuánto influye cada variable**, con importancia por permutación. Sirve para la defensa y para entender el sitio. |

### Alternativas consideradas

| Alternativa | Por qué no es la principal |
|---|---|
| Regresión lineal | No representa los umbrales: la humedad casi no influye hasta el 95 % y el viento tiene un óptimo. Sirve solo como comparación. |
| Bosque aleatorio (Random Forest) | Es una alternativa válida y del mismo tipo. El boosting suele ser algo más preciso en datos de tabla y genera archivos más chicos. Si el boosting fallara, sería la primera opción de reemplazo. |
| XGBoost o LightGBM | Técnica equivalente, con más opciones, pero suman una dependencia. Se pueden adoptar si el tribunal o el docente lo piden y se aprueba la dependencia. |
| Redes neuronales o LSTM | Necesitan muchos más datos (años de lecturas). Con unos cientos de días se sobreajustan y son difíciles de explicar. |
| Modelos de series de tiempo puros (ARIMA) | Usan solo el historial del volumen e ignoran el clima, que es justamente lo que el proyecto quiere relacionar. |

> No se usan varios modelos de producción. Las "referencias" de la sección 4 no son modelos
> alternativos: son reglas simples para comprobar que el modelo aporta valor.

---

## 3. Variables de entrada

Se calculan **por día** a partir de las lecturas válidas. Cada una tiene un motivo físico:

| Grupo | Variables | Por qué |
|---|---|---|
| Volumen reciente | Volumen del día D; del día anterior; media de 7 días | La niebla llega en **episodios que duran varios días**: lo de hoy anticipa lo de mañana. |
| Humedad | Media; máxima; **horas con humedad ≥ 95 %** | La captación ocurre cerca de la saturación. Las horas ≥ 95 % indican mejor la niebla que el promedio. |
| Niebla | Intensidad media; horas con intensidad ≥ 40 %; promedio de las últimas 6 h | Medición directa del recurso. Las últimas horas del día anticipan si el episodio continúa. |
| Viento | Velocidad media | La literatura muestra que la **eficiencia de la malla depende fuertemente del viento**. |
| Temperatura | Media; rango del día | Los días con niebla tienen poca amplitud térmica (sin sol fuerte). |
| Presión | Media; cambio respecto del día anterior | Una presión que baja suele indicar sistemas húmedos que traen niebla. |
| Época del año | Seno y coseno del día del año | Hay temporada húmeda (diciembre a marzo) y seca (mayo a agosto). El seno y coseno indican que el 31 de diciembre y el 1 de enero son días cercanos. |

**Advertencias según los sensores:**
- El firmware actual **no mide viento ni niebla**. El modelo admite que falten, pero sin ellos
  pierde dos de las variables más informativas. Por eso se recomienda priorizar el anemómetro y un
  medidor de niebla: un colector estándar de 1 m² con su pluviómetro.
- Una humedad que se queda en **100 % por horas** puede ser un sensor saturado y no niebla real.
  Conviene validarla antes de entrenar.

**Control de calidad:** un día con menos del **75 % de las horas** con dato de volumen no se usa
como total del día, porque no representa lo que realmente se captó.

---

## 4. Cómo se evalúa

### Validación temporal (sin "ver el futuro")

Los datos se ordenan por fecha y **nunca se mezclan**:
1. **Entrenamiento:** el primer 70 % de los días. Ahí se eligen los ajustes del modelo con
   validación cruzada temporal (`TimeSeriesSplit`, 5 cortes): siempre se entrena con el pasado y
   se prueba con lo que sigue.
2. **Prueba:** el último 30 %, que el modelo **nunca vio**. Ahí se calculan las métricas finales.

Mezclar los días al azar daría métricas engañosamente buenas: el modelo "conocería" días vecinos
del periodo de prueba.

### Métricas

| Métrica | Qué indica | Cómo se lee |
|---|---|---|
| **MAE** (error absoluto medio) | Cuántos litros se equivoca en promedio por día | "Se equivoca ±X L/día". Es la métrica principal: está en litros y es fácil de explicar. |
| **MSE / RMSE** | Igual que el MAE, pero castiga más los errores grandes | RMSE es la raíz del MSE y queda en litros. El documento pide MSE: se informan los dos. |
| **R²** | Qué parte de la variación del volumen explica el modelo | 1 es perfecto; 0 equivale a predecir siempre el promedio; negativo es peor que eso. |

### Comparación con referencias simples (obligatoria)

No hay estudios publicados que predigan el volumen de atrapanieblas con machine learning, así que
no existen métricas externas para comparar. Por eso el modelo **debe superar a dos reglas simples**:

- **Persistencia:** "mañana se captará lo mismo que hoy".
- **Media de 7 días:** "mañana se captará el promedio de la última semana".

**Si el modelo no las supera, se informa así** y no se promete precisión.

### Comparación real vs. estimado

Cada predicción se guarda y, cuando llega el volumen real del día, se comparan los dos. Así se
cumple RF-15 y HU-08: errores por día y totales por mes.

---

## 5. Cuándo **no** se predice

El sistema **no inventa una predicción** si no hay datos suficientes (RNF-14). Responde
`datos_insuficientes` y lista lo que falta cuando:
- falta el **volumen del día D** o la **humedad media**, o
- falta **más del 30 %** de las variables.

Cada predicción registra **fecha, variables usadas, resultado, versión del modelo y estado**
(RF-14).

---

## 6. Qué mostró la simulación

Se probó todo el flujo con **2 años de datos sintéticos**: preparación, entrenamiento, validación,
artefacto, inferencia y comparación. Los detalles están en `docs/simulacion_ml.md`.

| Periodo de prueba (219 días) | MAE (L/día) | RMSE (L/día) | R² |
|---|---:|---:|---:|
| Modelo | 14,7 | 21,3 | 0,38 |
| Referencia: persistencia | 17,0 | 27,4 | −0,02 |
| Referencia: media de 7 días | **14,1** | **20,9** | **0,41** |

**Lectura honesta:**
- El flujo **funciona** y respeta las reglas: validación temporal, sin datos futuros y aviso de
  datos insuficientes.
- El modelo **supera a la persistencia, pero no a la media de 7 días** en estos datos inventados.
  No se ajustó el generador para que "ganara".
- **Sobrestima en la época seca y subestima en la húmeda.** El entrenamiento vio solo una
  transición entre estaciones.
- Conclusión: con datos reales, **la comparación con las referencias es decisiva**, y hace falta
  cubrir varias estaciones.

---

## 7. Cuántos datos hacen falta

| Datos disponibles | Qué se puede hacer |
|---|---|
| Un mes (noviembre, según el cronograma) | **Probar el flujo** con datos reales y comparar con las referencias. No alcanza para un modelo confiable: unos 30 días de una sola época. |
| Una temporada (3 a 4 meses) | Primer modelo **provisional**, válido solo para esa época. |
| **Un año o más** | Modelo que cubre las épocas húmeda y seca. Es lo mínimo para evaluarlo en serio. |

**Reentrenamiento:** a medida que se acumulen meses, se reentrena de forma **controlada y
documentada**: con nueva versión, nuevas métricas y aprobación. Nunca automáticamente.

---

## 8. Integración con el sistema (pendiente)

Cuando se confirmen el horizonte y las variables y haya datos reales:

```text
Lecturas válidas (PostgreSQL)
   → preparación diaria (fuera de la API)
   → entrenamiento y evaluación (fuera de la API) → artefacto versionado (artifacts/)
   → servicio de predicción en el backend (carga el artefacto)
   → POST /api/v1/predictions · GET /api/v1/predictions · GET /api/v1/predictions/comparison
   → tablas ml_models y predictions
   → dashboard, análisis y reportes: real vs. estimado
```

- El **entrenamiento queda separado de la API**, y la API solo carga el artefacto aprobado.
- El modelo **no controla el riego**: entrega información para que las personas decidan.

---

## 9. Decisiones pendientes

1. **Horizonte:** ¿el volumen de mañana (D+1) o el total de la semana?
2. **Variables definitivas**, según los sensores realmente instalados: viento y niebla.
3. **Umbral mínimo de datos** para habilitar la primera versión, por ejemplo una temporada completa.
4. **Algoritmo:** quedarse con scikit-learn o aprobar XGBoost o LightGBM, como menciona el documento.
5. **Periodicidad del reentrenamiento** y quién lo aprueba.

---

## Resumen para la defensa

> Se usa **un único modelo de regresión por gradient boosting** (`HistGradientBoostingRegressor`)
> para predecir el **volumen diario captado el día siguiente**.
>
> Se eligió porque representa los **umbrales físicos** de la captación (humedad cercana a la
> saturación y un óptimo de viento), **admite sensores sin dato** sin falsearlos con ceros, rinde
> bien con **pocos datos**, entrena **rápido y sin Internet** y permite **explicar** qué variables
> influyen.
>
> Se evalúa con **validación temporal** y con MAE, RMSE/MSE y R², y **siempre contra dos
> referencias simples**: "igual que hoy" y "media de la semana".
>
> Su confiabilidad depende de **contar con datos reales de varias estaciones del año**.
