# Portal de administradores de dominio

Un servidor de correo suele alojar varios dominios de organizaciones distintas. Este portal
permite que cada organización administre **sus** cuentas y alias sin ver nada de las demás,
y sin entrar al panel general del servidor.

## Qué puede hacer un administrador de dominio

| Sí | No |
|---|---|
| Ver las cuentas y alias de sus dominios | Ver o tocar otros dominios |
| Crear cuentas | Eliminar cuentas |
| Editar nombre, teléfono, correo alterno y cuota | Leer correo de nadie |
| Cambiar contraseñas | Reenviar correo fuera de sus dominios |
| Activar y desactivar cuentas | Tocar la configuración del servidor |
| Crear, editar, pausar y eliminar alias | Crear administradores o asignarse dominios |

Quién administra qué lo decide el superadministrador en el panel general:
**Administración → Administradores de dominio**.

## Por qué es un servicio aparte

Es la parte más expuesta del sistema: la usan personas de fuera. Por eso es la que menos puede.

- **Otro proceso y otro puerto.** Si el portal cae, el panel general y el correo siguen.
- **Otro usuario del sistema**, sin `sudo`, sin escritura en disco y sin acceso a los buzones
  (ver el confinamiento en `deploy/maquita-panel-dominio.service`).
- **Otro usuario de base de datos** con permisos mínimos (`deploy/permisos.sql`): no puede leer
  las contraseñas guardadas, ni borrar buzones, ni leer la configuración ni la auditoría.
- **Sin secretos compartidos.** Las sesiones son fichas al azar guardadas como hash; una sesión
  del portal no sirve en el panel general ni en el webmail.
- **Sin dependencias en el navegador.** La pantalla es HTML, CSS y JavaScript a mano (unos 25 KB),
  sin paso de compilación: carga bien en conexiones lentas y no hay cadena de suministro que vigilar.

Aun si alguien tomara el control del portal, lo más que alcanzaría es lo que ya puede hacer un
administrador de dominio, y todo queda en `pd_auditoria`, que el portal puede escribir pero no
leer ni borrar.

## Instalación

Requisitos: el esquema de correo ya instalado (tablas `domain`, `mailbox`, `alias`), Python 3.11+,
`openssl`, nginx y PostgreSQL. Se asume el repositorio en `/opt/webmail`.

```bash
# 1. Usuario del sistema, sin shell ni directorio propio
useradd --system --no-create-home --shell /usr/sbin/nologin maquita-dominio

# 2. Entorno de Python
cd /opt/webmail/panel-dominio/backend
python3 -m venv venv && venv/bin/pip install -r requirements.txt

# 3. Base de datos: tablas (como dueño de la base), usuario del portal y permisos
psql -d maildb -f ../deploy/esquema.sql
psql -d maildb -c "CREATE ROLE panel_dominio LOGIN PASSWORD 'una-clave-larga-al-azar'"
psql -d maildb -f ../deploy/permisos.sql

# 4. Entorno del servicio (solo lo lee root; systemd se lo pasa al proceso)
install -m 600 /dev/null /etc/maquita-mail/panel-dominio.env
echo "PD_DB_PASS=una-clave-larga-al-azar" > /etc/maquita-mail/panel-dominio.env

# 5. Servicio y nginx
cp ../deploy/maquita-panel-dominio.service /etc/systemd/system/
cp ../deploy/panel-dominio-proxy.conf /etc/nginx/snippets/
cp ../deploy/nginx-panel-dominio.conf /etc/nginx/sites-enabled/panel-dominio   # ajusta nombre y certificado
systemctl daemon-reload && systemctl enable --now maquita-panel-dominio
nginx -t && systemctl reload nginx
```

El portal queda en `https://<tu-servidor>:8444/`. Abre ese puerto en el cortafuegos solo a quien
deba llegar.

## Variables de entorno

| Variable | Por defecto | Para qué |
|---|---|---|
| `PD_DB_PASS` | (obligatoria) | Clave del usuario `panel_dominio` |
| `PD_DB_HOST`, `PD_DB_PORT`, `PD_DB_NAME`, `PD_DB_USER` | `127.0.0.1`, `5432`, `maildb`, `panel_dominio` | Conexión |
| `PD_DB_SSL` | (vacío) | `require` si la base de datos está en otro equipo |
| `PD_HORAS_SESION` | `8` | Duración de una sesión |

## Reglas que conviene conocer

- **Cuota.** El tope por cuenta es el `maxquota` del dominio; si el dominio no tiene, 5 GB. Una
  cuenta que ya tenía más la conserva, pero desde el portal no se puede subir por encima del tope.
- **Límites del dominio.** Se respetan `mailboxes` y `aliases` de la tabla `domain` (0 = sin límite).
- **Alias.** Los destinos deben ser cuentas existentes de los dominios propios. Las direcciones de
  los grupos de distribución no aparecen: se gestionan en su propia sección del panel general.
- **Contraseñas.** Mínimo 10 caracteres con tres clases de carácter. La contraseña inicial de un
  administrador de dominio es temporal: hasta que la cambia, el portal no le deja hacer nada más.
- **Bloqueo.** Cinco intentos fallidos bloquean la cuenta 15 minutos; nginx limita además los
  intentos por dirección IP.

## Pruebas

```bash
cd panel-dominio/backend && venv/bin/pip install pytest && venv/bin/python -m pytest tests -q
```

## Pendiente (se agradecen opiniones)

- Segundo factor (TOTP) para los administradores de dominio.
- Respuestas automáticas y reenvíos dentro del dominio.
- Uso de espacio por cuenta (hoy exigiría dar al portal acceso a Dovecot).
- Que el administrador de dominio vea su propia actividad.
