# Revisiones de seguridad: decisiones de diseño y hallazgos ya resueltos

Este documento existe para que las revisiones externas (Qwen, auditores, pentest) **no vuelvan a
reportar como hallazgo lo que ya es una decisión de diseño documentada**, y para que quien revise
sepa dónde está cada control. Si un revisor cree que una de estas decisiones es incorrecta, debe
aportar evidencia nueva (una petición concreta que la rompa), no repetir el hallazgo.

Última actualización: 17/09/2026 (revisión Qwen sobre la etiqueta v1.7.21).

## Decisiones de diseño que NO son hallazgos

| Tema | Decisión | Dónde está |
|---|---|---|
| **Administradores del panel** | Los roles `superadmin` / `admin` / `viewer` son **globales**: una sola organización administra todos sus dominios. No existen administradores «por dominio», así que no hay que comprobar «tenencia de dominio» en reenvíos, alias, grupos ni buzones. Si algún día se delegan dominios a terceros, habrá que añadir ese modelo (queda anotado como requisito futuro). | `admin-panel/backend/app/auth/dependencies.py` (`get_current_admin`, `require_role`); tabla `admin_users` sin columna de dominios. |
| **Extensiones de archivo bloqueadas** | Se decide por la **última** extensión tras normalizar Unicode (NFKC) y quitar caracteres invisibles o de control. `documento.exe.pdf` **es un PDF** para cualquier sistema y no se bloquea; `script.pdf​.exe` sí (la última extensión es `exe`). Bloquear por la penúltima extensión rechazaría archivos legítimos. El contenido lo revisa además el antimalware de salida. | `backend/app/mail/services/adjuntos_seguros.py` (`extension_de`, `es_peligroso`). |
| **Antimalware de salida (safeattach) en modo *fail-open*** | Si el motor (ClamAV, oletools) falla o no responde, el envío **no se bloquea**; solo se bloquea con veredicto `malicious` y `enforce` activo. Es una decisión operativa: un antivirus caído no debe detener el correo institucional. El fallo del motor queda registrado. | `backend/app/mail/routers/compose.py` (bloque «Anti-malware de adjuntos salientes»), `backend/app/safeattach/`. |
| **Adjuntos de borradores por UID** | `mantener_adjuntos` copia los adjuntos del borrador anterior leyéndolos con la **sesión IMAP del propio usuario** y tras un `SELECT Drafts` explícito: no hay forma de leer borradores de otras cuentas. En sesiones delegadas la sesión IMAP es la de la cuenta delegada, autorizada en `mail_delegation`. | `backend/app/mail/services/adjuntos_borrador.py`, `clients/imap_client.py` (`fetch_raw_message`). |
| **IP en los registros de auditoría** | `X-Real-IP` la fija nginx desde `$remote_addr` (el backend solo escucha en 127.0.0.1) y además se valida como dirección IP antes de guardarla; la columna es `inet`. No hay *log forging* posible por cabecera. | `backend/app/auth/cambio_cuenta.py` (`_ip_valida`), configuración de nginx del servidor. |
| **Consultas IMAP construidas desde la búsqueda** | Todo valor de usuario pasa por `_entrecomillar` (escapa `\` y `"`, elimina caracteres de control); los nombres de carpeta por `_validate_folder` y `_quote_folder`; los operadores `adjunto:` se extraen antes del análisis y su filtro se hace sobre `BODYSTRUCTURE` en tandas acotadas (250 UIDs, tope 4 000). | `backend/app/mail/search_advanced.py`, `services/busqueda_adjuntos.py`, `routers/messages.py`. |
| **Buzón virtual `Virtual.Todo`** | Es un espacio de nombres de Dovecot **por usuario** (no listado): cada persona solo ve su propio buzón virtual. No da acceso a carpetas de otras cuentas. | `dovecot-config/96-virtual.conf`; `frontend/src/lib/busquedaGlobal.ts`. |
| **Impersonación sin TOTP** | Es un interruptor de `security_config` que solo cambian los `superadmin`, queda en `admin_audit`, y el vale de impersonación es de un solo uso y con caducidad corta. La organización lo activó por decisión de jefatura (acta firmada). | `backend/app/auth/politica_impersonacion.py`, `admin-panel/backend/app/security_policies/`. |
| **Contraseña maestra de Dovecot en cuentas delegadas** | El backend usa `<cuenta>*admin` solo tras comprobar en `mail_delegation` que la persona tiene la cuenta delegada; nunca llega al navegador. | `backend/app/mail/services/cuentas_delegadas.py`, `auth/cambio_cuenta.py`. |
| **Milter DLP de salida en modo *fail-open* y lista de remitentes exentos** | El milter es la **segunda** capa (la primera es la comprobación DLP del webmail al redactar, que sí bloquea). Ante un fallo del milter (base, red, análisis) el correo **se entrega** con registro del error: un DLP caído no debe detener el correo institucional de 300 cuentas. Los exentos (`/etc/maquita-mail/dlp-exempt-senders.txt`, solo `root`, 600) son cuentas de sistema que envían a cada persona sus propios datos (por ejemplo, el rol de pagos); hoy la lista está vacía y cada alta se documenta. Pasar a *fail-closed* se evaluará cuando el milter tenga vigilancia propia. | `milter/dlp_outbound.py`, `milter/maquita_milter.py`. |
| **Contactos por parámetros de URL** | `/contacts?email=&nombre=&nuevo=1`: el correo se valida y se acota; el nombre se limpia de caracteres de control e invisibles (sin quitar tildes ni eñes); el formulario de «Nuevo contacto» solo se abre con `nuevo=1` y la persona debe pulsar Guardar. React escapa el texto. | `frontend/src/components/contacts/ContactsView.tsx`. |
| **Preferencias en el navegador** | Al cerrar sesión se borran las preferencias de la persona (`maquita_sig_*`, `maquita_dictado_modo`, `maquita_buscar_en_todo`, `maquita_pinned_msgs`, `maquita_errors`) y `sessionStorage`; se conservan las del equipo (escala, ancho de la lista). El caché cifrado de correo se borra aparte (`limpiarCacheLocal`). | `frontend/src/lib/limpiezaPreferencias.ts`, `store/authStore.ts`. |
| **Tamaño de subidas** | nginx limita `/api/` a 100 MB; además cada punto de entrada acota lo suyo: adjuntos 25 MB, audio de dictado 15 MB, logos del panel por tipo y tamaño. | Configuración de nginx; `routers/compose.py`, `routers/transcribe.py`, `admin-panel/.../portales/router.py`. |

## Hallazgos de revisiones anteriores ya corregidos (no volver a reportar sin evidencia nueva)

| Revisión | Hallazgo | Corregido en |
|---|---|---|
| Andes / auditoría externa (sept. 2026) | Escape de comillas en la consulta IMAP (`dominio:x" ALL "`) | v1.7.19 (PR #110) |
| Qwen v1.7.21 (17/09/2026) | Audio de transcripción sin límite en el backend | PR #154 (15 MB, lectura por trozos) |
| Qwen v1.7.21 | Extensión disfrazada con caracteres invisibles o Unicode de compatibilidad | PR #154 (NFKC + limpieza) |
| Qwen v1.7.21 | IP de auditoría sin validar | PR #154 (`_ip_valida`) |
| Qwen v1.7.21 | «Admin de un dominio crea reenvíos en otro» | No aplica (roles globales; ver arriba) |
| Qwen v1.7.21 | «Adjuntos de borradores ajenos por UID» | Falso (sesión IMAP propia y `SELECT Drafts`; ver arriba) |
| Qwen v1.7.21 | «Log forging por X-Real-IP» | No explotable (nginx fija la cabecera; columna `inet`) |
| Qwen v1.7.22 (ronda 2) | Milter DLP *fail-open* y exentos | Decisión de diseño (ver arriba); permisos del archivo de exentos a 600 |
| Qwen v1.7.22 (ronda 2) | Contactos manipulables por URL | Endurecido (PR #156): validación, `nuevo=1` obligatorio para crear; el parche propuesto (regex sin tildes) habría mutilado nombres |
| Qwen v1.7.22 (ronda 2) | Preferencias en `localStorage` sin limpiar al salir | Corregido (PR #156) |
| Qwen v1.7.22 (ronda 2) | Cifrado de sesión, vista previa de adjuntos | Verificados como correctos por el revisor |
| Qwen v1.7.22 (ronda 3) | Inyección de cabeceras en la notificación de cambio de titular (panel) | **Real**. Corregido (PR #157): mensaje construido con `EmailMessage`, textos sin caracteres de control, destinatario como argumento de `sendmail` (sin `-t`) |
| Qwen v1.7.22 (ronda 3) | `almacen/sync_correo_drive.py` lee `.env` sin comprobar permisos | No aplica: los `.env` de todos los servicios son de `root` con permisos 600/640 y se despliegan así; una comprobación en el script no protege más que el sistema de archivos. Anotado como control operativo (verificar permisos en el despliegue) |

## Cómo se hace una revisión
1. Se etiqueta el estado a revisar (`vX.Y.Z`) y el revisor trabaja sobre la etiqueta, no sobre la rama.
2. El revisor debe leer este documento antes de escribir y declarar qué no pudo verificar.
3. Cada hallazgo se **verifica línea a línea** contra el código antes de aplicar un parche; los parches
   propuestos por el revisor no se aplican tal cual (en dos revisiones, un parche propuesto habría
   causado pérdida de correos o rechazo de adjuntos legítimos).
4. Los informes completos se guardan fuera del repositorio (documentación interna, carpeta de auditorías).
