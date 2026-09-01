# Tableros / BI — Aplicación del Drive Maquita

App de **inteligencia de negocios** sobre el [Drive Maquita (Almacén)](../../README.md):
elige un archivo de datos del Drive (`.xlsx`/`.csv`) y genera un **tablero automático**
—KPIs y gráficos— sin salir de la organización.

## Cómo funciona

1. `cliente_drive.py` **descarga** el archivo del Drive (`/api/almacen`) con el token
   del usuario, y **lista** los archivos de datos de una carpeta.
2. `conector_drive.py` (`ConectorDrive`) lo convierte en un `DataFrame`.
3. `tableros.py` (`generar_tableros`) detecta columnas categóricas y numéricas y arma
   KPIs + rankings, produciendo configuraciones **Chart.js** con el motor de BI.
4. `app_bi.py` sirve el selector, la página del tablero (Chart.js) y `/api/tablero`.

Motor (solo `numpy`/`pandas`): `motor_datos`, `motor_consultas`, `motor_visualizacion`,
`motor_semantico`, `motor_compartido`.

## Instalación

```bash
python -m venv venv
venv/bin/pip install -r requirements.txt
cp .env.example .env      # completa WEBMAIL_SECRET_KEY, REDIS_URL, ALMACEN_INTERNAL_URL
venv/bin/gunicorn 'app_bi:app' --bind 0.0.0.0:8791
```

## Estado

- **Fase 1 — hecha:** motor auditado y portable.
- **Fase 2 — hecha:** `ConectorDrive` (lee `.xlsx`/`.csv` del Drive → `DataFrame`,
  probado) + arreglo de un `import logging` faltante en el paquete.
- **Fase 3 — hecha:** app de tableros (`app_bi.py`, `cliente_drive.py`, `tableros.py`,
  `config.py`, `auth_drive.py`). Auth por el **token del Drive** (igual que el editor).
  **Verificado:** generación de tableros (KPIs + gráficos Chart.js de un archivo real) y
  **arranque de la app** (rutas `/`, `/tablero`, `/api/tablero`).
- **Opcional pendiente:** prueba end-to-end sirviendo tráfico real (listar/descargar del
  Drive con un usuario) y desplegar el servicio; y **corregir un bug del motor de
  consultas** (`ejecutar_consulta` lanza *"truth value of a Series is ambiguous"* en
  rankings) — por eso `tableros.py` agrega con `pandas` y usa el motor solo para la
  visualización.
