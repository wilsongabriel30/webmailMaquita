# CONTRATO DE LA API DEL ALMACÉN — congelado 2026-07-03

Inventario REAL de la API que consume el explorador de archivos original.
Fuente: `modulos/nextcloud/interfaces/api/nextcloud_api.py` del sistema de origen.
Prefijo: `/api/nextcloud`. Autenticación: sesión del sistema de origen (login_required).

> **Nota de nomenclatura.** «nextcloud» en este documento es un **nombre técnico heredado**:
> el prefijo del contrato de API (`/api/nextcloud`) y el módulo del sistema de origen. **No** se
> refiere al producto Nextcloud (esa integración está descontinuada, ver el README). Estos
> identificadores se conservan porque el explorador del Drive los consume tal cual; renombrarlos
> rompería el frontend. El producto es el **Almacén (Drive Maquita)**.

El Almacén Maquita debe implementar estos endpoints con LAS MISMAS entradas y salidas.
La suite `pruebas_contrato/` verifica los marcados con ✅ (núcleo v1).

| # | Método(s) | Ruta | Función | Descripción |
|---|---|---|---|---|
| 1 | GET | `/archivos` ✅ | listar_archivos | Lista archivos y carpetas en una ruta |
| 2 | GET | `/notify-push/token` | obtener_notify_push_token | Obtiene un pre-auth token de Notify Push para autenticar el WebSocket. |
| 3 | GET | `/buscar` | buscar_archivos | Busca archivos por nombre en todo el espacio del usuario |
| 4 | POST | `/archivos` ✅ | subir_archivo | Sube uno o más archivos |
| 5 | GET | `/archivos/descargar` ✅ | descargar_archivo | Descarga un archivo |
| 6 | GET | `/archivos/ver` | ver_archivo | Sirve un archivo para visualización inline (sin forzar descarga). Útil para PDFs, imágenes, videos en iframes/ |
| 7 | DELETE | `/archivos` ✅ | eliminar_archivo | Elimina un archivo o carpeta |
| 8 | POST | `/archivos/mover` ✅ | mover_archivo | Body: {"origen": "/ruta/archivo", "destino": "/nueva/ruta/archivo"} |
| 9 | POST | `/archivos/copiar` ✅ | copiar_archivo | Body: {"origen": "/ruta/archivo", "destino": "/nueva/ruta/archivo"} |
| 10 | POST | `/archivos/renombrar` ✅ | renombrar_archivo | Body: {"ruta": "/archivo.txt", "nuevo_nombre": "nuevo.txt"} |
| 11 | POST | `/carpetas` ✅ | crear_carpeta | Body: {"ruta": "/", "nombre": "Nueva Carpeta"} |
| 12 | POST | `/carpetas/estilo` | cambiar_estilo_carpeta | Body: {"folder_id": "12345", "color": "#ea4335", "icono": "star"} |
| 13 | POST | `/compartir` | compartir | Body: {"ruta": "/archivo", "tipo": 0, "destinatario": "usuario", "permisos": 1} |
| 14 | GET, POST | `/mi-perfil` | mi_perfil_nube |  |
| 15 | GET | `/compartidos` ✅ | listar_compartidos | Lista recursos compartidos |
| 16 | DELETE | `/compartidos/<share_id>` ✅ | eliminar_compartido | Elimina un share |
| 17 | GET | `/shares` | obtener_shares_archivo | Obtiene todos los shares de un archivo/carpeta específico. Usado por el modal de compartir para mostrar usuari |
| 18 | PUT | `/compartidos/<share_id>` | actualizar_compartido | Body: {"permisos": 1} Actualiza los permisos de un share existente. |
| 19 | GET | `/usuarios/buscar` ✅ | buscar_usuarios | Busca usuarios y grupos de Nextcloud para el autocompletado de compartir. |
| 20 | GET | `/usuarios/buscar-directorio` (alias histórico) | buscar_usuarios_directorio | Busca usuarios institucionales del sistema central/Nómina y permite correos externos. |
| 21 | GET | `/archivos/editar` | obtener_url_edicion | Obtiene URL para editar con OnlyOffice |
| 22 | GET | `/cuota` ✅ | obtener_cuota | Obtiene información de cuota del usuario |
| 23 | GET | `/status` | verificar_estado | Verifica estado de conexión con Nextcloud |
| 24 | GET | `/drawio/contenido` | obtener_contenido_drawio | Obtiene el contenido XML de un archivo Draw.io para editarlo |
| 25 | POST | `/drawio/guardar` | guardar_contenido_drawio | Body: {"ruta": "/archivo.drawio", "contenido": "<mxfile>...</mxfile>"} Guarda el contenido XML de un archivo D |
| 26 | GET | `/preview` | obtener_preview | Proxy OPTIMIZADO con cache Redis para obtener miniaturas de Nextcloud. |
| 27 | GET | `/onlyoffice/config` | onlyoffice_config | Genera la configuración JWT para embeber OnlyOffice Document Server. |
| 28 | GET | `/onlyoffice/download` | onlyoffice_download | Endpoint para que OnlyOffice Document Server descargue el archivo. No requiere login (OnlyOffice accede direct |
| 29 | POST | `/onlyoffice/callback` | onlyoffice_callback | Callback de OnlyOffice Document Server para guardar cambios. Usa credenciales del usuario para guardar en arch |
| 30 | GET | `/onlyoffice/status` | onlyoffice_status | Verifica el estado del servidor OnlyOffice Document Server. |
| 31 | GET | `/onlyoffice/config-public` | onlyoffice_config_public |  |
| 32 | GET | `/onlyoffice/download-public` | onlyoffice_download_public | Endpoint para que OnlyOffice Document Server descargue archivos de shares públicos. |
| 33 | POST | `/onlyoffice/callback-public` | onlyoffice_callback_public | Callback de OnlyOffice para guardar cambios en archivos compartidos públicamente. |
| 34 | POST | `/archivos/favorito` | toggle_favorito | Body: {"ruta": "/archivo.txt"} Toggle favorito de un archivo o carpeta |
| 35 | POST | `/archivos/crear` | crear_documento | Body: {"ruta": "/documento.docx", "tipo": "documento"} Crea un documento vacío del tipo especificado |
| 36 | GET | `/papelera` | listar_papelera | Lista archivos en la papelera del usuario |
| 37 | POST | `/papelera/restaurar` | restaurar_de_papelera | Body: {"ruta": "/archivo.txt"} Restaura un archivo de la papelera |
| 38 | POST | `/papelera/eliminar` | eliminar_de_papelera | Body: {"ruta": "<ruta del item en la papelera>"} Elimina DEFINITIVAMENTE un solo archivo de la papelera (sin v |
| 39 | POST | `/papelera/vaciar` | vaciar_papelera | Vacía completamente la papelera del usuario |
| 40 | GET | `/favoritos` | listar_favoritos | Lista archivos marcados como favoritos |
| 41 | GET | `/recientes` | listar_recientes | Lista archivos según el historial de interacción del usuario. |
| 42 | GET | `/preferencias` | obtener_preferencias | Obtiene las preferencias del usuario para la interfaz |
| 43 | POST | `/preferencias` | guardar_preferencias | Guarda las preferencias del usuario |
| 44 | POST | `/actividad/registrar` | registrar_actividad | Registra actividad del usuario con un archivo (apertura, edición, etc.) |
| 45 | GET | `/sugeridos` | obtener_sugeridos | Obtiene archivos sugeridos para la página principal (ordenados por relevancia) |
| 46 | GET | `/archivo-autor` | archivo_autor | Devuelve el propietario (autor original) del archivo y si fue compartido. |
| 47 | GET | `/avatar/<path:owner>` | avatar_propietario | Devuelve la foto de perfil (de Nomina) del dueño Nextcloud indicado, redirigiendo a su /static/uploads/... Si  |
| 48 | GET | `/versiones/<file_id>` | listar_versiones | Lista versiones anteriores de un archivo |
| 49 | POST | `/versiones/<file_id>/restaurar` | restaurar_version | Body: {"version_id": "1234567890"} Restaura una versión anterior del archivo |
| 50 | POST | `/cambiar-dueno` | cambiar_dueno | Transfiere la propiedad de un archivo/carpeta PROPIO a otro usuario de la Nube. |

## Formatos clave (verificados en código)

### GET /archivos?ruta=/x — listar
```json
{ "success": true, "ruta_actual": "/x", "breadcrumb": [{"nombre","ruta"}],
  "carpetas": [ITEM], "archivos": [ITEM], "total_carpetas": N, "total_archivos": N }
```
### ITEM (ArchivoResponseDTO.to_dict) — campos mínimos garantizados
`id, file_id, folder_id, nombre, ruta, ruta_completa, es_carpeta, tipo, extension,`
`tamano_bytes, tamano_humano, mime_type, icono, color, es_favorito, es_compartido,`
`es_editable, tiene_preview` (+ fechas y propietario)

### POST /archivos — subir: multipart `archivo` (repetible) + campo `carpeta`
### POST /carpetas — `{nombre, ruta}` · POST /archivos/mover — `{origen, destino}`
### POST /archivos/renombrar — `{ruta, nuevo_nombre}` · DELETE /archivos?ruta= (a papelera)
### POST /compartir — `{ruta, tipo(0=usuario,1=grupo,3=enlace), permisos}` → `{success, compartido:{...}}`
## Descubrimientos de la primera corrida (2026-07-03) — contrato REAL vs supuesto
1. **Códigos de creación:** `POST /carpetas`, `POST /archivos` (subir) y `POST /compartir`
   devuelven **HTTP 201** (creado), no 200. El Almacén debe replicarlo.
2. **Búsqueda:** `GET /buscar?q=` devuelve `{success, resultados: [...], termino, total}`
   (NO una clave "archivos"). Campos de cada resultado: nombre, ruta, ruta_completa,
   es_carpeta, extension, tipo, tamano, tamano_humano, modificado_at.
3. La suite quedó ajustada a este contrato real: **15/15 verde contra el sistema actual**.
   Esa corrida verde ES la especificación ejecutable del Almacén.
