# Tableros / BI — Aplicación del Drive Maquita (motor)

Motor de **inteligencia de negocios**: toma datos y produce consultas, tableros y
gráficos, para abrirse desde el [Drive Maquita (Almacén)](../../README.md).

Módulos (solo dependen de `numpy` y `pandas` — sin acople a otros sistemas):

- `motor_consultas.py` — construye y ejecuta consultas sobre los datos.
- `motor_datos.py` — carga y prepara los conjuntos de datos.
- `motor_visualizacion.py` — genera las visualizaciones (series, barras, etc.).
- `motor_semantico.py` — capa semántica (métricas y dimensiones con nombre).
- `motor_compartido.py` — utilidades comunes.

## Estado

- **Fase 1 (hecha):** motor traído y auditado (limpio, sin secretos, portable).
- **Fase 2 (pendiente):** empaquetado como app del Drive:
  - Interfaz de tableros (frontend) para ver y editar los reportes.
  - Fuente de datos (a partir de archivos del Drive: hojas de cálculo, CSV).
  - Autenticación por el **token del usuario del Drive**.

Hasta la Fase 2, este directorio es el **motor de referencia**, no un servicio autónomo.
