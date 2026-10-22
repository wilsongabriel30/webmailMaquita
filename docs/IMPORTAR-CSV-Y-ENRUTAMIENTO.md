# Importar cuentas desde CSV y enrutamiento de correo

Dos funciones de la v1.11 para quien administra correo de varias organizaciones: dar de alta muchas
cuentas de una vez y decidir, por dominio, que su correo se entregue en otro servidor.

---

## 1. Importar cuentas desde un archivo CSV

Dónde está:

| Panel | Ruta | Alcance |
|---|---|---|
| Panel general (8443) | Buzones → **Importar CSV** | Cualquier dominio del servidor (roles superadmin y admin) |
| Portal del dominio (8444) | Cuentas → **Importar CSV** | Solo los dominios del administrador, dentro de sus topes |

### El archivo

| Columna | Obligatoria | Qué lleva |
|---|---|---|
| `correo` | Sí | La dirección completa: `ana.perez@example.org` |
| `nombre` | Sí | El nombre de la persona |
| `clave` | No | Contraseña inicial. Si falta, se genera una (16 caracteres) |
| `cuota_mb` | No | Cuota del buzón en MB. Si falta, la del dominio |
| `alias` | No | Otras direcciones que entregan en esta cuenta, separadas por `;` |

- El separador puede ser coma o punto y coma (Excel en español guarda con punto y coma). Se admiten
  también los nombres `email`, `contraseña`, `password`, `cuota` y `aliases` en la cabecera.
- Texto en UTF-8 (con o sin BOM); si el archivo viene en Windows-1252, el navegador lo convierte.
- Hasta **2000 filas** y **1 MB**. Las filas vacías se saltan.
- Hay una plantilla para descargar en la misma pantalla.

```csv
correo,nombre,clave,cuota_mb,alias
ana.perez@example.org,Ana Pérez,,1024,ventas@example.org;info@example.org
luis.mora@example.org,Luis Mora,Verde.Monte42,,
```

### Los dos pasos

1. **Revisar archivo** (vista previa): cada fila se comprueba sin crear nada y se muestra su estado.
   Errores posibles:
   - dominio ajeno (en el panel general: no existe en el servidor; en el portal: no es uno de tus dominios,
     sin decir si existe), desactivado o enrutado a otro servidor;
   - la dirección o un alias ya existe (cuenta, alias o grupo), o se repite dentro del archivo;
   - contraseña débil: la política del portal (10 caracteres como mínimo, tres de cuatro clases —
     minúsculas, mayúsculas, números, símbolos— y sin el nombre de la cuenta). El panel general aplica la
     misma, más exigente que su alta manual;
   - cuota excedida (más que la cuota máxima del dominio; en el portal, sin máxima, 5 GB);
   - el dominio llegó a su tope de cuentas o de alias (contando las filas anteriores del archivo).
2. **Crear N cuentas**: el servidor vuelve a revisar todo contra la base de ese momento (no se fía de la
   vista previa) y crea **solo las filas válidas**, cada una con sus alias en una transacción. Al final:
   - un **informe** descargable (`informe-importacion.csv`) con lo que pasó en cada fila;
   - si se generó alguna contraseña, **`contrasenas-generadas.csv`**. Solo se entrega en ese momento: no se
     guarda en ningún sitio ni se anota en la auditoría. Hay que descargarlo y entregarlo por un medio seguro.

Los CSV que se descargan van protegidos contra la inyección de fórmulas: una celda que empieza por `=`,
`+`, `-`, `@`, tabulador o retorno lleva un apóstrofo delante. Las contraseñas generadas empiezan siempre
por letra o número, para no tener que escaparlas.

### Auditoría

- Panel general: acción `mailbox_importar` en Auditoría, con las direcciones creadas y los totales.
- Portal: acción `cuentas_importar` en `pd_auditoria` (el superadministrador la ve en
  Administradores de dominio → Actividad).

Nunca se anota una contraseña.

### Detalles del portal

- Usa las mismas reglas y el mismo usuario de base de permisos mínimos que el alta de una cuenta: no
  necesita privilegios nuevos salvo **leer si un dominio suyo está enrutado** (`permisos-5-enrutamiento.sql`;
  la migración lo concede también al actualizar). Sin ese permiso, la importación funciona igual y no avisa
  del enrutamiento.
- El portal no admite peticiones de más de 64 KB, así que el navegador manda el archivo **por bloques de
  filas** (cada uno con la cabecera). Para que la vista previa cuente bien los topes, cada bloque informa de
  lo que ocupan los anteriores; al crear, cada bloque se revisa de nuevo contra la base, así que lo creado
  por uno cuenta para el siguiente. No hace falta tocar nginx en los servidores ya instalados.

El código común (lectura, reglas y exportación) es `formato_csv.py`, una copia idéntica en
`admin-panel/backend/app/importar_cuentas/` y `panel-dominio/backend/app/importar/`; una prueba comprueba
que no se separen.

---

## 2. Enrutamiento de correo por dominio

Dónde está: panel general → **Dominios → Enrutamiento** (en la fila del dominio). Roles superadmin y admin.

| Modo | Qué hace | Para qué |
|---|---|---|
| Sin enrutamiento | El correo se entrega en los buzones de este servidor | Lo normal |
| **MX de respaldo** | Acepta el correo del dominio y lo guarda en cola; lo entrega al MX principal cuando responde | El dominio vive en otro servidor y este es su respaldo |
| **Reenvío a otro servidor** | Entrega todo el correo del dominio a `smtp:[servidor]:puerto` | Pasarela, migración o un servidor interno detrás de este |

Opciones:

- **Aceptar solo estas direcciones** (recomendado): lista de destinatarios válidos del dominio. Sin lista,
  se acepta cualquier usuario de ese dominio exacto y el servidor de destino decide.
- **Exigir TLS** (solo en el reenvío): `encrypt` en `smtp_tls_policy_maps` para `[servidor]:puerto`. Si el
  destino no ofrece TLS, el correo espera en la cola en vez de viajar sin cifrar. No se verifica el nombre del
  certificado (muchos servidores internos usan uno propio). La política es por destino: si dos dominios
  reenvían al mismo servidor y puerto y uno exige TLS, se exige para los dos.
- **Activo**: desactivarlo devuelve el dominio a los buzones locales sin perder la configuración.

Avisos:

- Con el enrutamiento activo, **los buzones del dominio en este servidor dejan de recibir correo**. El panel
  pide confirmación si el dominio tiene buzones.
- MX de respaldo: el registro MX de este servidor debe tener una preferencia **mayor** (número más alto) que
  el del principal. Si este servidor fuera el MX preferido, Postfix detecta el bucle («mail for … loops back
  to myself») y el correo vuelve con error.
- El destino de un reenvío no puede ser este mismo servidor (`myhostname`), `localhost` ni una dirección de
  bucle local, sin especificar, multidifusión, de enlace local o reservada. Las direcciones privadas sí se
  admiten (un servidor interno).

### Cómo lo lee Postfix

Como el resto del correo, desde la base (`maildb`), sin recargar nada al guardar:

| Parámetro | Mapa | Qué devuelve |
|---|---|---|
| `relay_domains` | `pgsql-enrutamiento-dominios.cf` | El dominio, si tiene enrutamiento activo y el dominio está activo |
| `relay_recipient_maps` | `pgsql-enrutamiento-destinatarios.cf` | `OK` para las direcciones de la lista, o para `@dominio` si no hay verificación |
| `transport_maps` | `pgsql-enrutamiento-transporte.cf` | `smtp:[servidor]:puerto` en el modo reenvío (en el respaldo, nada: va al MX) |
| `smtp_tls_policy_maps` | `pgsql-enrutamiento-tls.cf` | `encrypt` para `[servidor]:puerto` si se pidió TLS |
| `virtual_mailbox_domains` | `pgsql-virtual-domains.cf` | Ya no devuelve los dominios con enrutamiento activo |

Tablas: `enrutamiento_correo` y `enrutamiento_destinatarios` (`migrations/2026-10-21-enrutamiento-correo.sql`).

### Por qué no es un relé abierto

- Solo se aceptan para entregar fuera los dominios **exactos** configurados aquí; la validación no admite
  comodines ni nombres de un solo nivel.
- `relay_recipient_maps` está siempre puesto: aunque Postfix, por `parent_domain_matches_subdomains`, viera
  un subdominio como parte de `relay_domains`, sus destinatarios no están en el mapa (la clave comodín es
  `@dominio` exacto) y se rechazan en la conversación SMTP.
- La lista de destinatarios solo admite direcciones de ese dominio, y con la verificación activa no puede
  estar vacía.
- El ajuste 68 no se aplica si `smtpd_relay_restrictions` no tiene `reject_unauth_destination` o
  `defer_unauth_destination` (o hay un `permit` suelto antes), ni si `mynetworks` abarca todas las
  direcciones.

Las pruebas (`backend/tests/test_enrutamiento_correo.py`) ejecutan las consultas reales de los mapas
sobre SQLite, buscando las claves en el mismo orden que Postfix, y comprueban que ni subdominios, ni
dominios parecidos, ni dominios desactivados o en pausa se acepten para relé.

### Servidores ya instalados: ajuste 68

```bash
sudo bash deploy/ajustes/68-enrutamiento-de-correo.sh --simular   # qué falta, sin tocar nada
sudo bash deploy/ajustes/aplicar-ajustes.sh --aplicar               # todos los ajustes pendientes
```

Lo que hace, solo si falta:

1. Comprueba que el servidor no quedaría como relé abierto (ver arriba); si no, se detiene sin tocar nada.
2. Comprueba que existen las tablas (hay que aplicar antes las migraciones); si no, se detiene.
3. Copia de respaldo de `main.cf` y del mapa de dominios (`*.bak.AAAAMMDD_HHMMSS`).
4. Instala los cuatro mapas con la misma conexión que el mapa de dominios que ya usa el servidor.
5. Añade al final del `WHERE` del mapa de dominios la exclusión de los dominios enrutados. Si la consulta
   tiene una forma distinta de la esperada (`GROUP BY`, `ORDER BY`, `UNION`…), no la toca y explica qué
   añadir a mano.
6. Añade los cuatro parámetros conservando lo que ya hubiera (el mapa propio va delante en
   `transport_maps` y `smtp_tls_policy_maps`, detrás en `relay_domains` y `relay_recipient_maps`).
7. Prueba cada mapa con `postmap -q`, pasa `postfix check` y recarga. Si algo falla, deja todo como estaba.

Las instalaciones nuevas lo traen ya (`deploy/webmail/instalar.sh`).
