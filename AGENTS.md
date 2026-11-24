# AGENTS.md

## Contexto del proyecto

Sistema web local de monitoreo de agua captada mediante atrapanieblas, con IoT y predicción de volumen basada en machine learning.

Caso de estudio: Centro de Educación Alternativa “Ildefonso de las Muñecas”, Titicachi, Chuma, La Paz, Bolivia.

El sistema opera principalmente en una red local institucional. No debe asumirse conectividad permanente a Internet ni disponibilidad de servicios externos.

## Objetivo del sistema

Desarrollar un sistema IoT de monitoreo de agua captada mediante atrapanieblas con predicción de volumen basada en machine learning, para generar información sobre el comportamiento de la captación y apoyar la planificación del riego.

El sistema debe permitir:

- Registrar y visualizar variables ambientales.
- Registrar el volumen de agua captada.
- Registrar el nivel de almacenamiento cuando exista el sensor correspondiente.
- Consultar históricos por fecha, dispositivo o variable.
- Generar predicciones de volumen con un único modelo de machine learning.
- Comparar el volumen real con el volumen estimado.
- Generar y exportar reportes.
- Administrar usuarios, roles y permisos.
- Administrar el inventario de repuestos y componentes del hardware IoT.
- Registrar mantenimientos y reemplazos de componentes.
- Mantener trazabilidad de operaciones relevantes.

## Alcance obligatorio

El proyecto incluye exclusivamente:

1. Plataforma web local con backend en FastAPI y frontend en React.
2. Estación IoT basada en ESP32 y sensores ambientales/de volumen.
3. Un único modelo de machine learning para predecir el volumen de agua captada.
4. Dashboard web para visualizar datos, predicciones, reportes y administración.
5. Módulo de inventario de repuestos y componentes del hardware IoT.
6. Módulo de mantenimiento asociado a dispositivos y sensores.
7. Autenticación, control de acceso basado en roles y auditoría.
8. Seguridad adecuada para un entorno local y rural, sin dependencia de servicios externos.

## Fuera de alcance

No implementar ni proponer funcionalidades fuera de este alcance sin aprobación explícita del usuario.

Queda fuera del alcance:

- Control automático de riego.
- Actuadores o válvulas controladas por el sistema.
- Modelos ML1, ML2 o ML3.
- Simulación de escenarios climáticos.
- Gemelo digital.
- MCP o FastMCP.
- MQTT, Redis, Celery, Kafka u otros intermediarios no requeridos.
- Aplicación móvil.
- Integración con plataformas externas.
- Tratamiento o potabilización del agua.
- Comercialización del agua captada.
- Seguridad biométrica o cámaras.
- 2FA por SMS, correo electrónico o aplicaciones externas.
- Recuperación de cuenta mediante enlaces enviados por correo o SMS.
- Dependencia de servicios en la nube para el funcionamiento principal.

## Stack tecnológico

### Backend

- Python.
- FastAPI.
- Uvicorn.
- Pydantic.
- SQLAlchemy.
- Alembic.
- PostgreSQL.
- Psycopg.
- pytest.
- HTTPX.
- Ruff.

### Frontend

- React.
- TypeScript.
- Vite.
- Tailwind CSS.
- shadcn/ui.
- React Router.
- TanStack Query.
- Axios.
- React Hook Form.
- Zod.
- Recharts.
- Vitest.
- React Testing Library.
- Playwright.
- esptool-js (versión fija 0.7.0, aprobada el 2026-11-19): solo para la primera instalación del ESP32 por USB desde el navegador (Web Serial). Se carga bajo demanda y funciona sin Internet.

### Machine learning

- pandas.
- NumPy.
- scikit-learn.
- joblib.

Debe existir un único modelo de machine learning para la predicción del volumen de agua captada.

### Reportes

- openpyxl para Excel.
- ReportLab para PDF.
- Exportación CSV cuando corresponda.
- Excel y PDF incluyen el resumen y los gráficos del reporte (gráficos nativos de Excel y vectoriales en PDF, nunca capturas de pantalla); el CSV lleva solo los datos.

### IoT

- ESP32.
- PlatformIO.
- Framework Arduino.
- Comunicación HTTP/JSON hacia la API local.
- Lector propio del DHT11/DHT22 (`firmware/src/dht_sensor.cpp`), con límite de tiempo por pulso; reconoce el formato DHT11 o DHT22 por el contenido.

### Despliegue

- Docker Compose.
- Nginx: HTTPS en el puerto 443 para el sistema web, con certificado propio de la institución (`deployment/scripts/generar-certificado.sh`, sin Internet); el puerto 80 queda solo para las estaciones ESP32 y redirige los navegadores a HTTPS.
- Servidor local institucional.
- PostgreSQL.

## Arquitectura obligatoria

El backend debe seguir una arquitectura por tres capas:

```text
PRESENTACIÓN
Frontend React + Routers y esquemas FastAPI
        │
        ▼
LÓGICA DE NEGOCIO
Servicios, reglas de negocio y servicio de predicción ML
        │
        ▼
ACCESO A DATOS
Repositorios SQLAlchemy + PostgreSQL
```

### Reglas de arquitectura

- Los endpoints FastAPI no deben contener lógica de negocio compleja.
- Los endpoints no deben ejecutar consultas SQL directamente.
- Los servicios deben contener las reglas de negocio.
- Los repositorios deben encapsular el acceso a datos.
- El frontend nunca debe acceder directamente a PostgreSQL.
- El frontend solo consume la API REST.
- El modelo de machine learning debe estar encapsulado en un servicio de predicción.
- El entrenamiento del modelo debe estar separado de la ejecución de la API.
- Los artefactos del modelo deben cargarse desde una ubicación controlada.
- No introducir una cuarta capa arquitectural.
- Mantener un monolito modular: una sola aplicación backend, organizada internamente por capas.

## Estructura esperada

```text
atrapanieblas/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   ├── presentation/
│   │   │   ├── api/
│   │   │   └── schemas/
│   │   ├── business/
│   │   │   ├── services/
│   │   │   ├── rules/
│   │   │   └── ml/
│   │   └── data/
│   │       ├── database.py
│   │       ├── models/
│   │       └── repositories/
│   ├── alembic/
│   ├── artifacts/
│   ├── tests/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── lib/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
│
├── firmware/
├── notebooks/
├── deployment/
├── docs/
├── compose.yaml
└── README.md
```

## Módulos del sistema

### 1. Autenticación y usuarios

El sistema debe permitir:

- Inicio de sesión con usuario y contraseña.
- Cierre de sesión.
- Consulta del perfil autenticado.
- Creación, edición, desactivación y consulta de usuarios.
- Asignación de roles y permisos.
- Registro de acciones administrativas en auditoría.

No se implementará 2FA por SMS, correo, aplicación externa ni códigos enviados por canales externos.

### 2. Monitoreo IoT

El sistema debe recibir mediciones desde el ESP32 mediante HTTP/JSON.

Variables esperadas:

- Temperatura.
- Humedad relativa.
- Presión atmosférica, si el sensor está disponible.
- Velocidad del viento, si el sensor está disponible.
- Dirección del viento, si el sensor está disponible.
- Presencia o intensidad de niebla, según el mecanismo implementado.
- Volumen de agua captada.
- Nivel de almacenamiento, si el sensor está disponible.

Reglas:

- Toda medición debe incluir identificador del dispositivo, fecha de medición y valor.
- El servidor debe registrar la fecha de recepción.
- El sistema debe validar estructura, unidades, rangos y estado del dispositivo antes de almacenar.
- Una medición inválida no debe almacenarse como válida.
- Las variables no medidas deben representarse como `null`, no como `0`.
- El sistema debe prevenir duplicados mediante un identificador único de mensaje o lote.
- Si el ESP32 pierde conexión, debe conservar temporalmente las mediciones y reenviarlas al restablecerse la conexión.
- El dashboard debe mostrar la fecha de la última comunicación y advertir datos desactualizados.
- Existe una sola regla de conexión para todo el sistema (`backend/app/business/rules/connection.py`): una estación pierde la conexión cuando pasan 3 intervalos de envío (`sample_interval_s`) más 60 s sin comunicarse, con `DEVICE_STALE_MINUTES` como tope. Ningún módulo debe calcular la conexión por su cuenta.
- Toda pantalla que muestre la conexión de las estaciones debe refrescarse periódicamente (30 s). Toda acción que cambie el estado de una estación o sensor (activar/desactivar, estado final de un mantenimiento o incidencia, intervalo de envío, firmware) debe avisar a los demás módulos con `refreshStations` (`frontend/src/features/devices/api.ts`).
- Un sensor ausente o mal conectado no debe detener ni reiniciar el ESP32: su lectura se envía como `null`.

### 3. Volumen de agua captada

El sistema debe registrar el volumen captado por cada atrapanieblas.

Reglas:

- Definir explícitamente si el valor recibido es incremental o acumulado.
- No sumar directamente valores acumulativos.
- El volumen captado debe asociarse a un atrapanieblas, dispositivo, sensor y periodo.
- El sistema debe permitir consultar el volumen por día, semana, mes o rango personalizado.
- El sistema debe permitir comparar el volumen real con el volumen estimado por el modelo.

### 4. Predicción de volumen

Existe un único modelo de machine learning.

El modelo debe estimar el volumen de agua captada a partir de variables ambientales y operativas disponibles.

Reglas:

- No crear múltiples modelos de producción.
- No implementar ML1, ML2 ni ML3.
- No implementar simulación de escenarios.
- No usar el modelo para controlar riego automáticamente.
- Definir claramente el horizonte de predicción antes de implementar el modelo.
- No usar variables futuras que no estén disponibles al momento de generar la predicción.
- La evaluación debe respetar el orden temporal de los datos.
- El sistema debe informar cuando no existan datos suficientes para generar una predicción.
- Cada predicción debe registrar fecha, variables utilizadas, resultado, versión del modelo y estado.
- El modelo debe poder compararse con el volumen real registrado.
- El reentrenamiento debe ser un proceso controlado y documentado, no una operación automática sin validación.

### 5. Reportes

El sistema debe permitir:

- Consultar históricos de variables ambientales.
- Consultar volumen captado y nivel de almacenamiento.
- Consultar predicciones generadas.
- Consultar comparaciones real vs. estimado.
- Filtrar por fecha, periodo, dispositivo, sensor o atrapanieblas.
- Exportar reportes en CSV, Excel o PDF.

Los reportes deben generarse desde el backend. El frontend solo solicita y descarga el archivo.

- Cada reporte calcula su resumen y sus gráficos a partir de sus mismas filas (`report_charts.py`), así la pantalla, el Excel y el PDF coinciden con el detalle exportado.
- Los módulos muestran esos gráficos con `GET /api/v1/reports/charts` (mismos filtros y permisos que la exportación; no se registra como exportación en auditoría).
- El análisis estadístico también se exporta (`report=analisis`), con cada sección según los permisos del usuario.

### 6. Inventario de repuestos IoT

El inventario está orientado exclusivamente a los repuestos, componentes, consumibles y herramientas necesarias para mantener el hardware IoT y las estructuras atrapanieblas.

Debe permitir administrar:

- Repuestos y componentes.
- Categorías de inventario.
- Stock actual.
- Stock mínimo.
- Unidad de medida.
- Estado del repuesto.
- Compatibilidad con dispositivos y sensores.
- Entradas y salidas de inventario.
- Historial de movimientos.
- Alertas de stock bajo.
- Reportes de inventario.

Categorías sugeridas:

- Microcontroladores.
- Sensores ambientales.
- Sensores hídricos.
- Energía y alimentación.
- Protección ambiental.
- Conectividad y cableado.
- Estructura y fijaciones.
- Herramientas.
- Consumibles.

Reglas de inventario:

- Una entrada aumenta el stock disponible.
- Una salida disminuye el stock disponible.
- No se permite una salida mayor al stock disponible.
- Cada movimiento debe registrar fecha, usuario, tipo de movimiento, cantidad y motivo.
- Un repuesto puede estar asociado a uno o varios dispositivos o sensores.
- El stock mínimo debe permitir generar alertas de reposición.
- Los repuestos no deben eliminarse físicamente; deben desactivarse para conservar trazabilidad.
- El sistema debe permitir consultar el stock disponible antes de registrar una salida.
- El inventario debe poder relacionarse con mantenimientos y reemplazos de hardware.

### 7. Mantenimiento

El sistema debe permitir registrar mantenimientos sobre dispositivos y sensores.

Cada mantenimiento debe registrar:

- Dispositivo o sensor atendido.
- Fecha y hora.
- Usuario responsable.
- Tipo de mantenimiento.
- Descripción.
- Estado final del componente.
- Repuestos utilizados.
- Cantidad utilizada de cada repuesto.

Reglas:

- Al registrar un mantenimiento con reemplazo de repuesto, debe generarse una salida de inventario.
- La salida debe reducir el stock disponible.
- El mantenimiento debe quedar asociado al dispositivo o sensor atendido.
- No se debe permitir registrar un repuesto inexistente o sin stock suficiente.

## Roles y permisos

### Administrador

Puede:

- Gestionar usuarios y roles.
- Gestionar dispositivos, sensores y atrapanieblas.
- Gestionar inventario.
- Aprobar o rechazar solicitudes de recuperación de cuenta.
- Restablecer contraseñas de usuarios.
- Consultar auditoría.
- Gestionar respaldos.
- Acceder a configuración técnica.

### Director o docente

Puede:

- Consultar dashboard.
- Consultar históricos.
- Consultar predicciones.
- Consultar comparativas real vs. estimado.
- Generar reportes.
- Consultar inventario.
- Registrar mantenimientos, si se le asigna el permiso correspondiente.

### Observador

Puede:

- Consultar dashboard.
- Consultar históricos autorizados.
- Consultar reportes autorizados.

No puede:

- Administrar usuarios.
- Modificar configuración de hardware.
- Registrar mediciones.
- Modificar inventario.
- Aprobar recuperaciones de cuenta.

## Seguridad para sistema offline rural

El sistema debe priorizar seguridad local, simplicidad operativa y disponibilidad.

No se usarán mecanismos que dependan de Internet, telefonía móvil, correo electrónico o servicios de terceros.

### Autenticación

- Autenticación mediante usuario y contraseña.
- Contraseñas almacenadas únicamente como hash seguro.
- Nunca almacenar contraseñas en texto plano.
- Nunca registrar contraseñas en logs.
- Utilizar tokens de sesión firmados y con expiración.
- El token debe almacenarse de forma segura en el navegador.
- Invalidar la sesión al cerrar sesión.
- Proteger todos los endpoints administrativos y de escritura.
- Aplicar autorización en el backend, no solo ocultar elementos en el frontend.

### Control de acceso

- Implementar RBAC en el backend.
- Cada endpoint debe definir el permiso requerido.
- Un usuario sin permisos debe recibir `403 Forbidden`.
- Un usuario no autenticado debe recibir `401 Unauthorized`.
- Las operaciones sensibles deben registrarse en auditoría.

### Recuperación de cuenta

La recuperación de cuenta debe realizarse mediante una solicitud presencial o interna al administrador.

Flujo obligatorio:

1. El usuario solicita recuperación de cuenta desde la pantalla de inicio de sesión.
2. El sistema crea una solicitud con estado `pendiente`.
3. El usuario se comunica presencialmente con el administrador.
4. El administrador verifica la identidad del solicitante.
5. El administrador aprueba o rechaza la solicitud desde el panel de administración.
6. Si aprueba, el administrador genera una contraseña temporal o permite definir una nueva contraseña.
7. El usuario debe cambiar la contraseña temporal en el primer inicio de sesión.
8. La solicitud queda registrada como `aprobada` o `rechazada`.
9. La operación debe quedar registrada en auditoría.

Reglas:

- No enviar enlaces de recuperación por correo.
- No enviar códigos por SMS.
- No usar aplicaciones externas de autenticación.
- No exponer si un usuario existe o no al solicitar recuperación.
- Limitar la cantidad de solicitudes por usuario y por dirección IP.
- Una solicitud pendiente no debe permitir acceso al sistema.
- Solo un administrador autorizado puede aprobar una solicitud.
- El restablecimiento debe invalidar sesiones activas del usuario afectado.

### Seguridad del ESP32

- Cada ESP32 debe tener una identidad única.
- Cada dispositivo debe tener una credencial o API key propia.
- Las credenciales no deben estar escritas en el código fuente.
- Las credenciales deben cargarse desde configuración segura del firmware.
- La API debe validar el identificador y la credencial del dispositivo.
- Un dispositivo desactivado no debe poder enviar mediciones.
- Las mediciones deben incluir un identificador único para evitar duplicados.
- El firmware debe conservar temporalmente las mediciones cuando no haya conexión con el servidor.
- Al restablecerse la conexión, el ESP32 debe reenviar las mediciones pendientes.
- El firmware debe informar pérdida de comunicación o lecturas desactualizadas.
- La primera instalación por USB desde el navegador emite una API key nueva (la anterior queda revocada) y la envía directamente al ESP32 por el puerto serie: nunca se muestra en pantalla ni se registra.
- La contraseña Wi-Fi precargada (`STATION_WIFI_PASSWORD` en `.env`) solo se envía al ESP32; la API no la devuelve en ninguna consulta.
- Antes de instalar por USB una versión nueva, debe cargarse y asignarse en el sistema, para que la actualización por red no vuelva a una versión anterior.
- Cada versión cargada debe aumentar `FIRMWARE_VERSION` en `firmware/include/config.h`.

### Seguridad del servidor local

- PostgreSQL no debe estar expuesto directamente a los equipos de usuarios.
- Solo la API debe comunicarse con la base de datos.
- El servidor debe reiniciar los servicios principales después de un reinicio, cuando la configuración institucional lo permita.
- Definir respaldos periódicos de PostgreSQL.
- Probar la restauración de respaldos.
- Mantener respaldos fuera del contenedor de la base de datos.
- Registrar accesos administrativos y cambios de configuración.
- No exponer credenciales, secretos ni claves en el repositorio.
- Usar variables de entorno y `.env` excluido del control de versiones.
- Incluir `.env.example` con nombres de variables, pero sin valores reales.
- El servidor debe tener una IP fija o una reserva en el router: las estaciones envían a una dirección fija y un cambio de IP las deja sin comunicación.

## Validación de datos

Toda entrada debe validarse antes de ser almacenada.

Reglas generales:

- Validar tipos de datos.
- Validar campos obligatorios.
- Validar unidades de medida.
- Validar rangos físicos razonables.
- Validar fechas y zonas horarias.
- Validar identificadores de dispositivos y sensores.
- Validar que el dispositivo esté activo.
- Validar que el sensor esté asociado al dispositivo.
- Registrar el estado de calidad de la lectura.
- No almacenar datos inválidos como válidos.
- Retornar errores claros y consistentes.

Ejemplos de validación:

- La temperatura no debe aceptar valores físicamente imposibles.
- La humedad relativa debe estar entre 0 y 100 por ciento.
- El volumen captado no debe ser negativo.
- El nivel del tanque no debe ser negativo.
- Una fecha futura no debe aceptarse como fecha de medición.
- Un dispositivo inactivo no debe aceptar mediciones.

## Convenciones de API

- Prefijo base: `/api/v1`.
- Formato de intercambio: JSON.
- Fechas en ISO 8601.
- Identificadores numéricos o UUID, según decisión de implementación.
- Respuestas de error consistentes.
- Documentación automática mediante OpenAPI en `/docs`.

Endpoints base esperados:

```text
GET    /api/v1/health
GET    /api/v1/health/db

POST   /api/v1/auth/login
POST   /api/v1/auth/logout
GET    /api/v1/auth/me

POST   /api/v1/auth/recovery-requests
GET    /api/v1/admin/recovery-requests
POST   /api/v1/admin/recovery-requests/{id}/approve
POST   /api/v1/admin/recovery-requests/{id}/reject

GET    /api/v1/users
POST   /api/v1/users
GET    /api/v1/users/{id}
PUT    /api/v1/users/{id}
DELETE /api/v1/users/{id}

GET    /api/v1/devices
POST   /api/v1/devices
GET    /api/v1/devices/{id}
PUT    /api/v1/devices/{id}
DELETE /api/v1/devices/{id}

GET    /api/v1/sensors
POST   /api/v1/sensors
GET    /api/v1/sensors/{id}
PUT    /api/v1/sensors/{id}
DELETE /api/v1/sensors/{id}

POST   /api/v1/iot/measurements/batch
GET    /api/v1/measurements
GET    /api/v1/dashboard/summary
GET    /api/v1/dashboard/series

POST   /api/v1/predictions
GET    /api/v1/predictions
GET    /api/v1/predictions/comparison

GET    /api/v1/reports/export
GET    /api/v1/reports/charts

GET    /api/v1/firmware/releases
POST   /api/v1/firmware/releases
PUT    /api/v1/firmware/assignments
GET    /api/v1/firmware/releases/{id}/flash-plan
GET    /api/v1/firmware/releases/{id}/image
GET    /api/v1/firmware/base/{name}
GET    /api/v1/firmware/station-defaults
POST   /api/v1/firmware/first-install
GET    /api/v1/iot/firmware

GET    /api/v1/inventory/categories
POST   /api/v1/inventory/categories

GET    /api/v1/inventory/items
POST   /api/v1/inventory/items
GET    /api/v1/inventory/items/{id}
PUT    /api/v1/inventory/items/{id}
DELETE /api/v1/inventory/items/{id}

POST   /api/v1/inventory/items/{id}/movements
GET    /api/v1/inventory/items/{id}/movements

GET    /api/v1/inventory/alerts/low-stock
GET    /api/v1/inventory/reports/stock
GET    /api/v1/inventory/reports/movements

GET    /api/v1/maintenance
POST   /api/v1/maintenance
GET    /api/v1/maintenance/{id}
```

## Modelo de datos mínimo

### Seguridad y administración

- `users`
- `roles`
- `user_roles`
- `audit_logs`
- `account_recovery_requests`

### Infraestructura física

- `locations`
- `fog_collectors`
- `tanks`
- `greenhouses`

### IoT

- `devices`
- `device_credentials`
- `device_locations`
- `sensors`
- `sensor_types`
- `sensor_readings`
- `measurement_batches`
- `sensor_calibrations`

### Machine learning

- `ml_models`
- `predictions`

### Inventario y mantenimiento

- `inventory_categories`
- `inventory_items`
- `inventory_item_compatibility`
- `inventory_movement_types`
- `inventory_movements`
- `maintenance_records`
- `maintenance_items`

## Reglas de negocio prioritarias

1. El sistema debe funcionar en red local sin depender de Internet.
2. Solo debe existir un modelo de machine learning para predecir el volumen captado.
3. El modelo no debe controlar riego automáticamente.
4. El sistema no debe implementar 2FA por SMS, correo ni aplicaciones externas.
5. La recuperación de cuenta debe realizarse mediante solicitud al administrador.
6. El administrador debe verificar la identidad del usuario antes de aprobar una recuperación.
7. Las contraseñas deben almacenarse como hash seguro.
8. Los permisos deben validarse en el backend.
9. Toda medición IoT debe validarse antes de almacenarse.
10. Una medición no medida debe representarse como `null`, no como `0`.
11. El sistema debe prevenir duplicados de mediciones.
12. El ESP32 debe conservar temporalmente datos cuando pierda conexión.
13. El sistema debe mostrar advertencias cuando los datos estén desactualizados.
14. El inventario debe controlar entradas, salidas, stock actual y stock mínimo.
15. No se puede retirar del inventario más stock del disponible.
16. Cada movimiento de inventario debe ser trazable.
17. Los reemplazos de hardware deben vincularse con mantenimientos y salidas de inventario.
18. Los registros históricos no deben eliminarse físicamente.
19. Las operaciones relevantes deben registrarse en auditoría.
20. El código debe mantener separación clara entre presentación, lógica de negocio y acceso a datos.

## Reglas para agentes de código

### Antes de programar

- Leer este archivo antes de modificar el proyecto.
- No asumir funcionalidades no definidas en este documento.
- No agregar tecnologías nuevas sin justificación y aprobación.
- No implementar MCP, MQTT, Redis, Celery ni servicios en la nube.
- No implementar múltiples modelos de machine learning.
- No implementar control automático de riego.
- No implementar 2FA por SMS, correo o aplicaciones externas.
- No implementar recuperación mediante enlaces enviados por canales externos.

### Al escribir código

- Usar español para nombres de dominio, mensajes de usuario y documentación.
- Usar inglés para identificadores técnicos cuando el proyecto ya lo establezca.
- Mantener tipado estricto en TypeScript.
- Usar Pydantic para validar entradas y salidas del backend.
- Usar servicios para lógica de negocio.
- Usar repositorios para acceso a datos.
- Evitar lógica de negocio en routers, componentes React o consultas SQL directas.
- Escribir pruebas para reglas de negocio críticas.
- No dejar credenciales, secretos ni datos sensibles en el código.
- No generar migraciones destructivas sin confirmación explícita.
- No eliminar datos históricos.
- No modificar el esquema de base de datos sin usar Alembic.

### Al implementar ML

- Confirmar primero el horizonte de predicción.
- Confirmar las variables disponibles.
- No usar datos futuros como entrada.
- Usar validación temporal.
- Registrar métricas de evaluación.
- No prometer precisión sin evidencia experimental.
- Informar explícitamente cuando no haya datos suficientes.
- Mantener el modelo entrenado como artefacto versionado.
- Separar entrenamiento, evaluación e inferencia.

### Al implementar seguridad

- Aplicar autenticación y autorización en el backend.
- No confiar en validaciones del frontend.
- No exponer información sensible en mensajes de error.
- No registrar contraseñas, tokens ni credenciales en logs.
- Invalidar sesiones tras cambios de contraseña.
- Registrar operaciones administrativas en auditoría.
- Implementar recuperación de cuenta únicamente mediante solicitud al administrador.

## Criterios de aceptación

Una funcionalidad se considera completa cuando:

- Cumple con las reglas de negocio definidas aquí.
- Respeta la arquitectura de tres capas.
- Valida entradas en backend.
- Aplica permisos según rol.
- Registra operaciones relevantes en auditoría.
- No introduce dependencias externas no autorizadas.
- Incluye pruebas cuando corresponde.
- No rompe la compatibilidad con la API existente.
- No modifica el esquema de base de datos sin migración Alembic.
- Está documentada suficientemente para su mantenimiento.

## Prioridad de implementación

1. Configuración base del backend y base de datos.
2. Autenticación, usuarios, roles y auditoría.
3. Recuperación de cuenta mediante solicitud al administrador.
4. Dispositivos, sensores y ubicaciones.
5. Recepción y validación de mediciones IoT.
6. Dashboard e históricos.
7. Inventario de repuestos IoT.
8. Mantenimiento y vinculación con inventario.
9. Preparación de datos históricos.
10. Entrenamiento y evaluación del único modelo ML.
11. Predicción y comparación real vs. estimado.
12. Reportes y exportaciones.
13. Despliegue local con Docker Compose y Nginx.