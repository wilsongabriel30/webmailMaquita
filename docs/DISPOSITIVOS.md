# Teléfonos institucionales (gestión de dispositivos) — fase 1

Gestión propia de los celulares de la organización: inventario y asignación, estado que reporta
cada equipo, mensajes urgentes con acuse de lectura y eventos de seguridad. Las fases siguientes
(ubicación y modo perdido, respaldos, control de aplicaciones) se apoyan en estas mismas tablas.

| Pieza | Dónde | Qué hace |
|---|---|---|
| API de los teléfonos | `backend/app/dispositivos/` (`/api/dispositivos/*` del webmail) | Enrolamiento con código, latidos, entrega de comandos y mensajes, acuses, eventos |
| Administración | `admin-panel/backend/app/dispositivos/` y `admin-panel/frontend/src/pages/Dispositivos.tsx` | Equipos, ficha de inventario y depreciación, códigos de enrolamiento, mensajes urgentes |
| Datos | `migrations/2026-09-18-dispositivos.sql` (tablas `disp_*`) | — |

## Seguridad
- **Código de enrolamiento** = contraseña de instalación. Lo crea un administrador del panel, se
  muestra una sola vez, caduca y tiene usos limitados; en la base solo queda su SHA-256. Sin código
  vigente la app no activa la gestión. El **modo** (control completo o limitado) lo fija el código,
  no el teléfono.
- **Token del equipo**: 48 bytes aleatorios, se entrega una vez al enrolar y se guarda solo su
  SHA-256. Es independiente de la sesión de correo. «Quitar de la gestión» lo invalida.
- Cada equipo solo ve sus propios comandos y mensajes (todas las consultas filtran por el equipo
  dueño del token). Límites de ritmo en Redis para enrolar, latidos y eventos.
- El panel exige rol `admin`/`superadmin` para escribir y audita cada acción en `admin_audit`.
- Privacidad: en la fase 1 no se guarda contenido del teléfono. Si la app envía `ubicacion` en el
  latido, queda solo dentro del JSON del latido; su uso se activa en la fase 2, tras la política de
  uso firmada por el custodio.

## Contrato de la API (v1) — `Authorization: Bearer <token_equipo>` salvo `enrolar`
| Ruta | Cuerpo | Respuesta |
|---|---|---|
| `POST /api/dispositivos/enrolar` | `{codigo, id_instalacion, modo?, fabricante?, modelo?, serie?, imei?, android?, version_app?}`. Si llega con la cookie de sesión del correo, esa persona queda como custodia. | `{id_equipo, token_equipo, modo, politica, push}` · 403 si el código no vale · 429 tras 10 intentos por hora e IP |
| `POST /api/dispositivos/latido` | `{bateria?, cargando?, almacenamiento_libre?, almacenamiento_total?, red?, version_app?, android?, play_protect?, ubicacion?}` | `{comandos:[{id,tipo,parametros}], mensajes:[{id,titulo,texto,nivel,requiere_acuse,creado_en}], politica_version, latido_minutos}`. Un mensaje se repite en cada latido hasta que llega su acuse. |
| `POST /api/dispositivos/mensajes/{id}/acuse` | `{leido_en?}` | `{ok}` |
| `POST /api/dispositivos/comandos/{id}/resultado` | `{estado: "hecho"\|"fallido", detalle?}` | `{ok}` |
| `POST /api/dispositivos/evento` | `{tipo, detalle?}` con tipo en `arranque`, `admin_desactivado`, `desinstalacion_intento`, `permiso_revocado`, `sim_cambiada`, `otro` | `{ok}` |
| `GET /api/dispositivos/yo` | — | Nombre del equipo, custodio, contacto de Tecnología y aviso de privacidad |
| `GET /api/dispositivos/politica` | — | `{version, latido_minutos, contacto_ti, telefono_ti, aviso_privacidad}` |

401 = token desconocido o equipo retirado de la gestión desde el panel (al retirarlo, su token se
destruye): la app debe apagar el módulo, avisar a la persona y pedir un código nuevo para volver a
enrolarse. 403 = equipo dado de baja del inventario.

## Instalar y desinstalar con contraseña
- Instalar: el código de enrolamiento cumple esa función.
- Desinstalar: en equipos enrolados de fábrica (control completo) la app bloquea su propia
  desinstalación y solo Tecnología la libera. En modo limitado Android no permite exigir una
  contraseña para desinstalar: la app se registra como administradora del dispositivo (hay que
  desactivarla antes de poder desinstalar), avisa a la persona y envía el evento
  `admin_desactivado` / `desinstalacion_intento`, que el panel resalta para revisión.
