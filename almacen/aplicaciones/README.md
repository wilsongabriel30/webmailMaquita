# Aplicaciones del Drive Maquita

Herramientas que **se abren desde el [Drive Maquita (Almacén)](../README.md)** y
trabajan sus archivos — igual que un documento se abre desde el Drive. Cada archivo
hereda los permisos, el compartir, la papelera, las versiones y la búsqueda del Drive.

| Aplicación | Qué hace | Estado |
|---|---|---|
| **Documentos** (OnlyOffice) | Editar Word/Excel/PowerPoint en el navegador | Disponible (integrado en el Almacén) |
| **Formularios** (`.forma`) | Crear formularios y encuestas, estilo Google Forms | Disponible (integrado en el Almacén) |
| [**Editor de PDF**](pdf_editor/) | Anotar, firmar y rellenar PDF | **Instalable** — app autónoma, arranque validado |
| [**Tableros / BI**](bi/) | Convertir datos del Drive en tableros y gráficos | **Instalable** — app de tableros, arranque validado |

**Fase 2** (común a las dos últimas): configuración propia, autenticación por el
token del usuario del Drive, y abrir/guardar archivos directamente del Drive.

## Archivos comunes (copias idénticas)

Cada aplicación se instala por separado, así que no comparten un paquete. Estos archivos
son **idénticos** en `pdf_editor/` y `bi/`; si cambias uno, copia el otro (la prueba
`almacen/tests/test_auth_drive_aplicaciones.py` falla si divergen):

- `auth_drive.py` — valida el token del Drive y la sesión viva en Redis: con `sid`, solo
  `imap_pass:<usuario>:<sid>`; sin `sid`, la clave antigua `imap_pass:<usuario>` o
  cualquier `imap_pass:<usuario>:*` (SCAN acotado, nunca KEYS).
- `marca_drive.py` — nombre visible del Drive: lo publica el Almacén en
  `GET /api/almacen/marca` (perilla `config_kv['drive_name']`); si no responde, la
  variable `DRIVE_NAME`; si tampoco, «Nube». Ningún texto lleva el nombre escrito: lo
  vigila `deploy/tools/comprobar-textos-marca.py`.
