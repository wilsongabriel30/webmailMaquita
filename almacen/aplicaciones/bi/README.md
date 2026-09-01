# Tableros / BI — Aplicación del Drive Maquita

Motor de **inteligencia de negocios**: toma datos y produce consultas, tableros y
gráficos, para abrirse desde el [Drive Maquita (Almacén)](../../README.md).

Módulos del motor (solo `numpy` y `pandas` — sin acople a otros sistemas):

- `motor_datos.py` — conectores de datos (interfaz `IConectorDatos`) y esquema.
- `motor_consultas.py` — construye y ejecuta consultas sobre los datos.
- `motor_visualizacion.py` — genera las visualizaciones (series, barras, etc.).
- `motor_semantico.py` — capa semántica (métricas y dimensiones con nombre).
- `motor_compartido.py` — utilidades comunes.
- **`conector_drive.py`** — fuente de datos del **Drive**: lee un archivo tabular
  (`.xlsx`/`.xls`/`.csv`) del Drive y lo entrega como `DataFrame`.

## El conector del Drive

Desacoplado: recibe una función `leer_bytes(ruta) -> bytes`, así el motor no depende
de ningún cliente concreto del Drive. En producción se le pasa un lector que llama a
la API del Drive (`/api/almacen/archivos/descargar`) con el token del usuario.

```python
from bi import ConectorDrive

conector = ConectorDrive(leer_bytes=mi_lector_del_drive)   # bytes de la ruta dada
df       = conector.obtener_datos({"ruta": "/Datos/ventas.xlsx"})
esquema  = conector.obtener_esquema({"ruta": "/Datos/ventas.xlsx"})   # tipos inferidos
```

## Estado

- **Fase 1 — hecha:** motor auditado y portable.
- **Fase 2 — hecha:** **conector de datos del Drive** (`ConectorDrive`) — lee
  `.xlsx`/`.csv` del Drive → `DataFrame`. Probado (datos, esquema con tipos inferidos,
  `test_conexion`). Incluye el arreglo de un `import logging` faltante en el paquete.
- **Fase 3 — pendiente (app de tableros):**
  1. Un lector real del Drive (`leer_bytes` que llama a `/api/almacen` con el token del
     usuario, como el resto del Almacén).
  2. Interfaz web de tableros (elegir un archivo del Drive → ver/editar el tablero).
  3. Punto de entrada `app_bi.py` + auth por el token del Drive (`auth_drive`, igual que
     el editor de PDF) + servicio.

A diferencia del editor de PDF (que ya venía completo), el BI de Maquita es un **motor
transversal** del sistema de gestión; esta app de tableros sobre archivos del Drive es
un desarrollo nuevo construido sobre ese motor.
