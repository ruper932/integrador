# Diagramas UML del sistema ATINA

- **`uml_atina.drawio`**: archivo editable en draw.io Desktop, con una página por diagrama.
- **`uml_atina.pdf`**: todos los diagramas en un PDF (una página por diagrama).
- **`png/`**: cada diagrama como imagen, para insertarla en documentos.

- **`casos_de_uso_modulos.drawio`** / **`.pdf`** / **`png/casos_de_uso/`**: un diagrama de casos de uso
  detallado por cada módulo (actores, «include», «extend» y especializaciones).

Los diagramas se basan en el código actual del sistema (modelos, servicios, endpoints y firmware).

| N.º | Módulo | Diagrama |
|---|---|---|
| 1 | General | Arquitectura en tres capas (componentes) |
| 2 | General | Despliegue en el servidor local (Docker Compose) |
| 3 | General | Casos de uso por rol |
| 4 | 1. Autenticación y usuarios | Clases (usuarios, perfil normalizado, roles, sesiones, auditoría) |
| 5 | 1. Autenticación y usuarios | Actividad: inicio de sesión con bloqueo temporal |
| 6 | 1. Autenticación y usuarios | Secuencia: recuperación de cuenta presencial |
| 7 | 1. Autenticación y usuarios | Estados de la solicitud de recuperación |
| 8 | 2. Monitoreo IoT | Clases (infraestructura, dispositivos, sensores, lecturas) |
| 9 | 2. Monitoreo IoT | Secuencia: recepción de un lote de mediciones |
| 10 | 2. Monitoreo IoT | Actividad: firmware ESP32 con cola sin conexión |
| 11 | 3. Volumen captado | Secuencia: series del dashboard (suma o promedio) |
| 12 | 4. Predicción | Actividad del flujo propuesto (**pendiente**) |
| 13 | 5. Reportes | Secuencia: exportación CSV/Excel/PDF |
| 14 | 6. Inventario | Clases (sistema periódico, conteo, saldos) |
| 15 | 6. Inventario | Actividad: cierre de periodo y valorización |
| 16 | 7. Mantenimiento | Clases |
| 17 | 7. Mantenimiento | Secuencia: registro con descuento de repuestos |

Para volver a exportar desde draw.io Desktop (desde una terminal de VS Code hay que quitar
`ELECTRON_RUN_AS_NODE`):

```bash
env -u ELECTRON_RUN_AS_NODE drawio -x -f pdf -a --crop -o uml_atina.pdf uml_atina.drawio
env -u ELECTRON_RUN_AS_NODE drawio -x -f png -p 4 -s 1.5 -o clases_usuarios.png uml_atina.drawio
```

## Casos de uso por módulo (`casos_de_uso_modulos.drawio`)

| Página | Módulo | Actores |
|---|---|---|
| CU-M1 | Autenticación, usuarios, roles y auditoría | Visitante, Usuario autenticado, Administrador |
| CU-M2 | Infraestructura y monitoreo IoT | Administrador, Director/docente, Observador, Estación ESP32 |
| CU-M3 | Volumen captado y dashboard | Observador, Director/docente |
| CU-M4 | Predicción de volumen (**pendiente**, en tono ámbar y borde discontinuo) | Director/docente, Administrador |
| CU-M5 | Reportes | Director/docente, Administrador |
| CU-M6 | Inventario de repuestos (sistema periódico) | Administrador, Director/docente, Técnico de mantenimiento |
| CU-M7 | Mantenimiento | Técnico de mantenimiento, Administrador, Director/docente |
