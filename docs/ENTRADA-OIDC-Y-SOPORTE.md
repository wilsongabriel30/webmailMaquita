# Entrada al panel con OpenID Connect, vale de entrada y soporte «como el cliente»

Tres formas nuevas de entrar, pensadas para quien administra el servidor:

1. **Panel general (8443) con OpenID Connect**: el superadministrador entra con la cuenta de un
   proveedor de identidad de la organización (Authelia, Keycloak, Authentik…) en lugar de, o además
   de, su usuario y contraseña.
2. **Vale de entrada por consola**: `maquita-panel vale-entrada <admin>` da un enlace de un solo uso
   que abre la sesión de ese administrador del panel. Para cuando no hay otra forma de entrar.
3. **Soporte en el portal de dominio (8444)**: desde la ficha del dominio en el panel, o por consola
   con `maquita-panel-dominio vale-soporte <dominio>`, el superadministrador abre el portal del
   cliente tal como él lo ve, sin conocer su contraseña ni su segundo factor.

Nada de esto toca la entrada de las personas al correo (`backend/app/sso`, SAML y el OIDC del
webmail con Keycloak): son entradas al panel y al portal, con sus propias tablas y reglas.

## 1. Panel general con OpenID Connect

### Cómo funciona

- Flujo *authorization code* con **PKCE S256**, `state` y `nonce`. El `state` va además en una
  galleta `HttpOnly`, `Secure`, `SameSite=Lax`, limitada a `/api/auth/oidc`: la vuelta solo vale en el
  mismo navegador que salió (nadie puede colar su propia entrada en el navegador de otro).
- El emisor se descubre en `<emisor>/.well-known/openid-configuration`; el `issuer` publicado debe
  coincidir con el configurado y todos los puntos (autorización, token, claves, userinfo) deben ser
  HTTPS. Se guarda en memoria 10 minutos.
- El `id_token` se valida entero: firma con las claves del JWKS del proveedor (solo algoritmos
  asimétricos: RS*, PS*, ES*, EdDSA; `none` y HS256 se rechazan siempre), `iss`, `aud` (y `azp` si
  hay varios destinatarios), `exp`, `iat` (60 s de margen) y `nonce`. Si el proveedor rota sus claves,
  se vuelven a pedir una vez. Librería: PyJWT (ya estaba en `requirements.txt`); no se añadió ninguna.
- Si al `id_token` le faltan el claim de usuario o el de grupos (Authelia 4.39 solo pone los mínimos),
  se piden a `userinfo` con el token de acceso, comprobando que el `sub` sea el mismo.
- La cuenta se busca en `admin_users` por el claim elegido (`preferred_username` o `email`, sin
  distinguir mayúsculas). **No se crean administradores** salvo que se active «Crear la cuenta si no
  existe» (apagado por defecto); entonces se crean con el rol elegido (`viewer` por defecto) y una
  contraseña al azar que nadie conoce. Con `email` como claim, un correo con `email_verified: false`
  no entra.
- Si se configura un **grupo requerido**, la persona tiene que traerlo en el claim de grupos.
- Si la cuenta del panel tiene **segundo factor**, se le sigue pidiendo: la vuelta del proveedor no
  abre la sesión, emite un vale de 120 s y la pantalla `/entrar` pide el código antes de canjearlo.
  Los fallos cuentan para el bloqueo de la cuenta (5 fallos, 15 minutos), como en la entrada normal.
- La entrada con usuario y contraseña sigue igual: el proveedor es una opción más, no la única.

### Configuración desde el panel

**SSO / Identidad → Entrada al panel con OpenID Connect** (solo superadmin):

| Campo | Ejemplo | Notas |
|---|---|---|
| Emisor (issuer) | `https://auth.example.org` | `https://`, sin espacios |
| client_id | `panel-correo` | |
| client_secret | (el valor en claro que dio el proveedor) | Se guarda **cifrado** con la llave de credenciales; no vuelve nunca a la pantalla |
| Claim de usuario | `preferred_username` o `email` | Debe coincidir con el usuario del panel |
| Claim de grupos | `groups` | Opcional |
| Grupo requerido | `admins-correo` | Opcional; exige el claim de grupos |
| Crear la cuenta si no existe | apagado | Y el rol de las cuentas nuevas |
| Texto del botón | `Entrar con Identidad` | Hasta 60 caracteres |

La pantalla muestra la **dirección de vuelta** que hay que registrar en el proveedor, normalmente
`https://mail.example.org:8443/api/auth/oidc/vuelta`. Sale de `ORG_URL_PANEL`
(`/etc/maquita-mail/organizacion.env`) o, si no está, del nombre por el que se entra y el puerto 8443.
«Probar el emisor» descarga el descubrimiento y las claves sin guardar nada.

El botón aparece en la pantalla de entrada solo con la entrada activada y con emisor, client_id y
secreto guardados.

**Cifrado del secreto.** Se usa la llave dedicada del proyecto, `CREDENTIAL_ENCRYPTION_KEY` (Fernet),
que el panel recibe como `WEBMAIL_CREDENTIAL_ENCRYPTION_KEY` en `admin-panel/backend/.env` (ya está en
las instalaciones hechas con `instalar.sh`). Si se rota la llave, se puede declarar la anterior como
`WEBMAIL_CREDENTIAL_ENCRYPTION_KEY_ANTERIOR` o volver a guardar el secreto.

**Acceso de nginx.** El puerto 8443 sigue protegido como antes (red interna o clave básica de nginx).
Desde fuera, la vuelta del proveedor pasa por esa misma clave básica, que el navegador ya recuerda.

### Ejemplo genérico: Authelia

En `configuration.yml` de Authelia (4.38 o posterior), un cliente confidencial con PKCE:

```yaml
identity_providers:
  oidc:
    hmac_secret: 'cadena-larga-al-azar'
    jwks:
      - key_id: 'principal'
        algorithm: 'RS256'
        use: 'sig'
        key: {{ secret "/config/secrets/oidc/jwks/rsa.2048.key" | mindent 10 "|" | msquote }}
    # Opcional (Authelia 4.39 o posterior): que el id_token traiga ya el usuario, el correo y los
    # grupos. Authelia 4.38 no conoce claims_policies: quite este bloque y la línea claims_policy del
    # cliente; el panel pide esos datos a userinfo y entra igual.
    claims_policies:
      panel:
        id_token: ['preferred_username', 'email', 'email_verified', 'groups']
    clients:
      - client_id: 'panel-correo'
        client_name: 'Panel de administración del correo'
        # Hash del secreto. El valor en claro va al campo client_secret del panel.
        client_secret: '$pbkdf2-sha512$310000$...'
        public: false
        authorization_policy: 'two_factor'
        claims_policy: 'panel'          # solo con el bloque claims_policies (4.39 o posterior)
        require_pkce: true
        pkce_challenge_method: 'S256'
        redirect_uris:
          - 'https://mail.example.org:8443/api/auth/oidc/vuelta'
        scopes: ['openid', 'profile', 'email', 'groups']
        response_types: ['code']
        grant_types: ['authorization_code']
        token_endpoint_auth_method: 'client_secret_basic'
        id_token_signed_response_alg: 'RS256'
        userinfo_signed_response_alg: 'none'
```

El secreto y su hash se generan con:

```bash
authelia crypto hash generate pbkdf2 --variant sha512 --random --random.length 72 --random.charset rfc3986
```

En el panel: emisor `https://auth.example.org`, client_id `panel-correo`, el secreto en claro, claim de
usuario `preferred_username`, claim de grupos `groups` y, si se quiere, grupo requerido
`admins-correo`. El usuario de Authelia debe llamarse igual que el administrador del panel.

Con Keycloak es lo mismo: cliente confidencial, «Standard flow», PKCE S256 y la dirección de vuelta
anterior; el claim de grupos lo da un *mapper* «Group Membership» con nombre `groups`.

## 2. Vale de entrada por consola

```bash
sudo maquita-panel vale-entrada admin --vida 120
# Vale de entrada para «admin» (superadmin): un solo uso, válido 120 s.
# https://mail.example.org:8443/entrar?vale=…
```

- Un solo uso, guardado como hash (`admin_vales_entrada`), caduca en `--vida` segundos (de 10 a 900;
  120 por defecto). Opciones: `--host servidor[:puerto]` y `--json`.
- Abre la sesión sin contraseña ni segundo factor (lo emite root en el propio servidor), pero esa
  sesión **no cuenta como abierta con segundo factor**: con `IMPERSONAR_EXIGE_TOTP` (lo normal) no
  sirve para impersonar buzones ni para entrar como soporte. Para eso hay que salir y entrar con el
  código.
- La cuenta tiene que existir y estar activa (si está bloqueada: `maquita-admin-recovery unlock`).
- Auditoría del panel: `vale_entrada_emitido` (quién lo pidió: `consola:<usuario de sudo>`) y
  `login_vale` al usarlo.

## 3. Soporte «como el cliente» en el portal de dominio

Desde el panel: **Dominios → Entrar como soporte** (solo superadmin, con la sesión abierta con
segundo factor, igual que para impersonar un buzón). Se elige el modo, se escribe el motivo (p. ej. el
número de incidencia) y se abre el enlace. Por consola:

```bash
sudo maquita-panel-dominio vale-soporte example.com                    # solo lectura
sudo maquita-panel-dominio vale-soporte example.com --con-acciones --vida 300 --motivo "incidencia 42"
```

- El vale (`pd_vales_soporte`, solo el hash) es de un solo uso y caduca en `--vida` segundos (300 por
  defecto, 900 como mucho). El enlace es el del portal propio de la empresa si lo tiene, si no
  `ORG_URL_PORTAL_DOMINIO` o el servidor del correo con el puerto 8444.
- El portal lo canjea por una **sesión de soporte** (`pd_sesiones_soporte`) que alcanza solo ese
  dominio y dura `PD_MINUTOS_SOPORTE` minutos (60 por defecto, de 5 a 240). No usa la contraseña ni el
  segundo factor del cliente y no le cierra sus sesiones.
- **Solo lectura** (lo normal): el backend del portal responde 403 a toda petición POST, PUT, PATCH o
  DELETE, salvo cerrar la sesión. El intermediario de los sitios web (`maquita-sitios-portal`)
  vuelve a comprobarlo con su propia lista cerrada de órdenes de lectura: aunque el portal fallara,
  no modificaría nada. Descargar archivos o copias también queda fuera (son POST).
- **Con acciones**: se puede hacer lo mismo que el administrador del dominio, y cada acción queda en
  `pd_auditoria` con el usuario `soporte:<superadmin>` y la marca
  `"soporte": {"superadmin": …, "modo": "con_acciones"}`.
- Nunca, ni con acciones: cambiar la contraseña ni el segundo factor del cliente («Mi cuenta» no
  aparece).
- En el portal se ve una franja fija: «Sesión de soporte (solo lectura)» o «con acciones», con quién
  entra y hasta qué hora.
- Auditoría: en el panel, `soporte_vale_emitido` (dominio, modo, motivo); en `pd_auditoria`, al
  entrar, `soporte_entrada` con el texto «el superadmin X entró como soporte de example.com». Se ve en
  **Administradores de dominio → Auditoría**.

## Instalación y servidores ya instalados

- Tablas del panel: `migrations/2026-10-21-entrada-oidc-y-vales.sql` (la aplica `maquita-actualizar`
  como el resto de migraciones).
- Tablas y permisos del portal: `panel-dominio/deploy/esquema-5-soporte.sql` y `permisos-5-soporte.sql`.
  El portal solo puede leer los vales y marcarlos usados, nunca crearlos.
- Órdenes de consola: `deploy/panel/instalar.sh` (`/usr/local/sbin/maquita-panel`,
  `/usr/local/sbin/maquita-panel-dominio` y `/usr/local/lib/maquita-panel`, solo root).

En un servidor ya instalado lo deja todo el **ajuste 66**:

```bash
sudo bash deploy/ajustes/66-entrada-oidc-y-soporte.sh --simular   # qué falta
sudo bash deploy/ajustes/aplicar-ajustes.sh --aplicar             # o todos los ajustes
```

Si la base está en otro equipo, el ajuste lo avisa: hay que aplicar allí la migración (como el usuario
del panel) y `esquema-5`/`permisos-5-soporte.sql` (como el dueño de la base).

## Variables

| Variable | Dónde | Para qué |
|---|---|---|
| `WEBMAIL_CREDENTIAL_ENCRYPTION_KEY` | `admin-panel/backend/.env` | Cifra el client_secret (ya existe) |
| `WEBMAIL_CREDENTIAL_ENCRYPTION_KEY_ANTERIOR` | `admin-panel/backend/.env` | Opcional, para rotar la llave |
| `ORG_URL_PANEL` | `organizacion.env` | Dirección del panel para la vuelta OIDC y los vales |
| `ORG_URL_PORTAL_DOMINIO` | `organizacion.env` | Dirección del portal para los vales de soporte |
| `PD_MINUTOS_SOPORTE` | `/etc/maquita-mail/panel-dominio.env` | Duración de la sesión de soporte (60) |

## Pruebas

```bash
cd admin-panel/backend && PYTHONPATH=. pytest tests          # OIDC con proveedor simulado, vales, soporte
cd panel-dominio/backend && PYTHONPATH=. pytest tests        # canje, solo lectura en todas las rutas
cd backend && pytest tests/test_panel_consola.py tests/test_sitios_portal_soporte.py
```

## Límites conocidos

- Solo clientes confidenciales (`client_secret_basic` o `client_secret_post`); no `private_key_jwt`.
- `userinfo` firmado (respuesta JWT) no se admite: se espera JSON (`userinfo_signed_response_alg: none`).
- El cierre de sesión en el panel no cierra la del proveedor (no hay *RP-initiated logout*).
- El vale viaja en la dirección (`?vale=`): puede quedar en el registro de nginx, pero es de un solo
  uso y caduca en segundos; la página lo quita de la barra de direcciones al leerlo.
