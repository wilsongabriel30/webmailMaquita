# Gran escala: de 300 a 5000 buzones

La instalación de serie es **una sola máquina** (`deploy/webmail/instalar.sh`): Postfix, Dovecot,
PostgreSQL, Redis, nginx y el webmail con 4 workers de uvicorn. Sirve sin cambios hasta unos 150
buzones activos a la vez y nada de lo que describe esta guía la cambia: todo es opcional y se activa
con variables del `.env`.

Esta guía es para organizaciones de **300 a 5000 buzones** que necesitan más capacidad, poder
actualizar sin cortar el servicio o que la caída de una máquina no deje a todos sin correo.

> **Estado (v1.11.0).** El backend del webmail ya puede correr en 2+ réplicas detrás de un
> balanceador (probado con varios workers y varios procesos sobre el mismo Redis). PgBouncer y Redis
> Sentinel están soportados en la configuración del cliente y probados con pruebas automáticas (Sentinel
> con un centinela real; PgBouncer, sin un PgBouncer real en las pruebas). La topología completa de
> varias máquinas **no se ha probado todavía en producción**: los números de dimensionamiento son
> estimaciones a validar con `deploy/escala/prueba-carga-webmail.py` antes de comprometerse a ellos.

## 1. Topología recomendada

```
                      Internet
                         │
              ┌──────────┴──────────┐
              │  Balanceador (2, con │   HAProxy + keepalived (IP flotante), o nginx.
              │  IP flotante)        │   Comprueba GET /api/listo en cada nodo.
              └──────────┬──────────┘
          ┌──────────────┼──────────────┐
   ┌──────┴─────┐ ┌──────┴─────┐ ┌──────┴─────┐
   │  app1      │ │  app2      │ │  app3      │   nginx del proyecto + webmail (uvicorn)
   │  webmail   │ │  webmail   │ │  webmail   │   + Drive (almacen) + panel opcional.
   └──────┬─────┘ └──────┬─────┘ └──────┬─────┘   Sin estado: se añaden o quitan sin más.
          └───────┬──────┴───────┬──────┘
        ┌─────────┴───┐   ┌──────┴──────────────┐
        │ PgBouncer   │   │ Redis + Sentinel ×3  │  sesiones, límites, bloqueos, pub/sub
        │ (transaction)│  └─────────────────────┘
        └─────┬───────┘
   ┌──────────┴───────────┐
   │ PostgreSQL principal │──réplica en streaming──▶ PostgreSQL réplica (lectura y relevo)
   └──────────────────────┘
          ┌───────────────────────────────┐
          │ Dovecot proxy (IMAP/Sieve)    │  cada usuario siempre al mismo backend
          └───────┬───────────────┬───────┘
          ┌───────┴─────┐  ┌──────┴──────┐
          │ Dovecot +   │  │ Dovecot +   │   almacenamiento de correo LOCAL de cada
          │ buzones A-M │  │ buzones N-Z │   backend (o compartido, ver §5)
          └─────────────┘  └─────────────┘
          Postfix (2+, MX con la misma prioridad) → LMTP al backend de cada usuario
```

Mínimo útil para alta disponibilidad: **2 nodos de aplicación**, 1 PostgreSQL con réplica, 3 Redis
con Sentinel (pueden compartir máquina con otros servicios) y el balanceador. Hasta unos 1500 buzones,
Dovecot puede seguir en una sola máquina (con buen disco y respaldos); es la pieza que más cuesta
duplicar.

## 2. Backend sin estado: qué había en memoria y cómo quedó

Para que dos réplicas sean intercambiables, nada que importe puede vivir solo en la memoria de un
proceso. Inventario hecho sobre el código (octubre de 2026):

| Estado | Dónde vive ahora | Notas |
|---|---|---|
| Sesiones (credencial IMAP cifrada por sesión, sid, generación) | Redis | Ya estaba (F-01). Cualquier réplica atiende cualquier petición: no hace falta afinidad. |
| Límites de tasa (lectura, escritura, envío, búsqueda en el cuerpo) | Redis | Ya estaba. Si Redis cae, cada proceso limita con un contador propio a la cuarta parte (fallo cerrado). |
| Límite de intentos de inicio de sesión (IP y usuario) | Redis | Ya estaba. **Requiere la IP real**: ver §4. |
| Notificaciones en tiempo real (WebSocket) | Redis pub/sub | Cada réplica tiene sus conexiones y se suscribe a Redis: un evento publicado desde cualquier proceso llega al navegador conectado a cualquier réplica. |
| Progreso de «Sincronizar mi bandeja» (asistente RAG) | Redis (antes en memoria) | Antes, con 4 workers, /status caía en otro proceso, mostraba «nada en curso» y dejaba lanzar otra sincronización a la vez. |
| DDL de arranque | Bloqueo de transacción de PostgreSQL (`app/escala/ddl.py`) | Antes, bloqueo de sesión: se quedaba colgado detrás de PgBouncer y, en `tasks/router.py`, se pedía con `pool.execute()` y podía quedar prendido de otra conexión. |
| Correos programados | Reclamo atómico en PostgreSQL | Ya estaba (pending → sending). |
| Recordatorios de tareas y eventos | Reclamo atómico en PostgreSQL | Ya estaba. |
| Lector de `/var/log/mail.log` | **Un líder por máquina** (`Lider`, bloqueo en Redis) | Antes cada worker leía el archivo y cada línea entraba **4 veces** en `mail_trace`. |
| Detector de fraude (cada 5 min) | `una_vez_por_intervalo` | Antes corría en cada worker: consultas ×4 y alertas duplicadas en carrera. |
| Listas de amenazas (cada 12 h) | `una_vez_por_intervalo` | Antes, 4 descargas idénticas por máquina y otra en cada reinicio. |
| Restaurar correos pospuestos (cada minuto) | `una_vez_por_intervalo` | Ver «Pendiente» (§9): la restauración en sí no funciona hoy. |
| Pool de conexiones IMAP | Memoria de cada proceso | Es una caché de conexiones abiertas: correcto que sea por proceso. |
| Cachés de marca, DLP, portales, anclas | Memoria de cada proceso | Datos de PostgreSQL con caducidad corta o recarga al arrancar. Un cambio de la marca se ve en todas las réplicas tras reiniciarlas (el despliegue escalonado lo hace). |
| Archivos en disco local | `/var/lib/maquita-webmail/` (firmas, adjuntos de calendario, GNSS, nombres.json), `/opt/maquita-webmail/uploads/branding`, `/var/lib/maquita-compliance`, exportaciones de cumplimiento | **Tienen que estar en almacenamiento compartido** (NFS o similar) montado en todas las réplicas. Ver §9. |
| Registro de seguridad | `/var/log/webmail/security.log` de cada nodo | Centralizarlo (rsyslog/journald remoto) si hay varias réplicas. |

### El bloqueo distribuido (`backend/app/escala/bloqueo.py`)

- `SET clave testigo NX PX ttl` para tomarlo; renovar y liberar con un script Lua que compara el
  testigo: nadie suelta ni alarga el bloqueo de otro proceso.
- Caduca solo: si el proceso muere, otro lo toma al vencer el ttl.
- Si Redis no responde, **no se concede**: es preferible saltarse una vuelta de una tarea de fondo que
  repetirla N veces.
- `una_vez_por_intervalo(redis, nombre, segundos)`: la tarea corre una vez por intervalo en todo el
  clúster y nunca dos a la vez (mientras corre se renueva).
- `Lider(redis, nombre, arrancar, parar)`: para tareas continuas; si el líder cae, otro proceso la
  retoma en ≤ 10 s tras vencer el bloqueo (30 s).

**Regla para tareas nuevas:** toda tarea de fondo que se arranque en `lifespan` corre en cada worker
de cada réplica. Si no es idempotente, protégela con un reclamo atómico en PostgreSQL
(`UPDATE … WHERE estado = 'pendiente' RETURNING`) o con `una_vez_por_intervalo`. El inventario está en
`backend/app/escala/tareas_fondo.py`.

## 3. Configuración (todo opcional; lo de serie no cambia)

| Variable | De serie | Para qué |
|---|---|---|
| `PGBOUNCER` | `false` | `true` si `DATABASE_URL` apunta a PgBouncer en modo transaction: apaga la caché de sentencias preparadas de asyncpg. Lo leen también el panel y el Drive. |
| `DB_POOL_MIN` / `DB_POOL_MAX` | `2` / `10` | Conexiones por worker. Con PgBouncer se puede subir `DB_POOL_MAX` (son conexiones baratas al pooler). |
| `DATABASE_URL_LECTURA` | vacío | Réplica de lectura. Crea `app.state.db_pool_lectura`; `app.database.pool_lectura(app.state)` la devuelve (o la principal si no hay). |
| `REDIS_URL` | `redis://…` | Admite `redis+sentinel://[:clave@]c1:26379,c2:26379/<grupo>/<db>[?sentinel_password=…]`. |
| `REDIS_SENTINELS` | vacío | Alternativa: `c1:26379,c2:26379`, con `REDIS_SENTINEL_MASTER` (de serie `mymaster`) y `REDIS_SENTINEL_PASSWORD`. La clave y la base del Redis principal se toman de `REDIS_URL`. |
| `NODO_ID` | nombre de la máquina | Nombre del nodo en los bloqueos (el lector de `mail.log` es «uno por nodo»). |
| `ESCALA_ARCHIVO_DRENAJE` | `/run/maquita-webmail/drenar` | Si existe, `/api/listo` responde 503. |
| `ESCALA_LISTO_ESPERA_S` | `2` | Tiempo máximo de cada comprobación de `/api/listo`. |

Ejemplos de configuración en `deploy/escala/`: `haproxy.cfg.ejemplo`, `nginx-balanceador.conf.ejemplo`,
`pgbouncer.ini.ejemplo`, `sentinel.conf.ejemplo` y `maquita-webmail@.service` (varias instancias en una
máquina).

### PgBouncer: qué se comprobó en el código

En modo **transaction** cada transacción puede ir a otra conexión del servidor. Lo incompatible es:
sentencias preparadas con nombre, `SET` de sesión, `LISTEN/NOTIFY`, tablas temporales entre
transacciones y bloqueos consultivos de sesión. En el backend:

- asyncpg prepara sentencias con nombre para su caché → con `PGBOUNCER=true` se pasa
  `statement_cache_size=0` en el pool del servicio, en los programas de `app/*/run.py`, en las
  conexiones sueltas (`app.database.connect_db`) y en la tarea de alertas de dispositivos.
- Los tres bloqueos consultivos de sesión (arranque, recordatorios, pasos de tareas) pasaron a
  `pg_advisory_xact_lock` dentro de una transacción. Funcionan igual con y sin PgBouncer.
- No hay `LISTEN`, `SET` de sesión ni `PREPARE` explícitos. Una prueba
  (`test_nada_del_backend_usa_sentencias_incompatibles`) falla si alguien los añade.
- El panel (`admin-panel`) usa asyncpg con la misma regla; el Drive usa psycopg2 (sin sentencias
  preparadas en el servidor) y su bloqueo de DDL pasa a uno de transacción con `PGBOUNCER=true`.
- Las migraciones (`migrations/*.sql`) conviene lanzarlas contra PostgreSQL directo.

## 4. Balanceador

- **Comprobación:** `GET /api/listo` (200 = base y Redis accesibles; 503 = fuera). `GET /api/salud`
  solo dice que el proceso vive: úsala para el «liveness» de un orquestador, nunca para sacar nodos
  por un fallo de la base (los reiniciaría todos a la vez sin arreglar nada).
  - Panel: `/api/salud` y `/api/listo` (solo base). Drive: `/api/almacen/salud` y
    `/api/almacen/listo`. Chat: `/healthz` (ya comprobaba la base).
- **Sin afinidad de sesión**: las sesiones están en Redis. `leastconn` reparte mejor que `roundrobin`
  porque hay peticiones largas.
- **WebSocket** (`/api/ws`): tiempo de túnel largo (1 h).
- **IP real del cliente**: el balanceador añade `X-Forwarded-For` y el nginx de cada nodo debe
  fiarse de él (`set_real_ip_from <balanceador>; real_ip_header X-Forwarded-For;`). Sin esto todos
  los inicios de sesión parecen venir de la IP del balanceador y el límite de 20 intentos cada 5 min
  por IP bloquea a toda la organización.
- `/api/v1/...` es un alias estable de `/api/...` (misma API; ver `docs/SOPORTE-Y-VERSIONES.md`).

## 5. Correo: Dovecot y el almacenamiento

El webmail habla IMAP con Dovecot (`IMAP_HOST`), envía por Postfix (`SMTP_HOST`) y gestiona filtros
por ManageSieve (`SIEVE_HOST`). En un clúster esas variables apuntan al **proxy de Dovecot** y al
relé de envío, no a `127.0.0.1`.

Dos formas de repartir los buzones, de más a menos recomendable:

1. **Dovecot proxy + almacenamiento local por backend.** El proxy (Dovecot con `proxy=y` y el campo
   `host` del passdb) manda a cada usuario siempre a su backend. Es lo más robusto: los índices de
   Dovecot nunca se escriben desde dos máquinas a la vez. Dovecot 2.3 tenía *director* para esto; en
   2.4 se eliminó y se usa el proxy con el backend del usuario en la base de datos (una columna en la
   tabla de buzones). El usuario maestro que usa el webmail (`usuario*admin`) tiene que estar permitido
   en el proxy.
2. **Almacenamiento compartido (NFS) para todos los Dovecot.** Más simple de montar, pero Dovecot
   exige que un mismo buzón no se abra a la vez desde dos servidores (`mail_nfs_index`,
   `mail_fsync = always`, y afinidad por usuario en el balanceador de IMAP). Sin afinidad, se corrompen
   índices. Úsese solo si ya hay un NAS fiable y siempre con afinidad.

Postfix: 2+ servidores MX con la misma prioridad, entregando por LMTP al backend del usuario (el proxy
de Dovecot también hace de proxy LMTP). El lector de `mail.log` del webmail corre en cada máquina que
tenga ese archivo (un worker por máquina) y deja el seguimiento en `mail_trace`.

`mail_max_userip_connections`: cada worker guarda hasta 2 conexiones IMAP ociosas por usuario y abre
como mucho 5 a la vez. Con varias réplicas detrás de un proxy, Dovecot ve todas las conexiones de un
usuario desde la IP del proxy: súbase el límite a `réplicas × workers × 5` o más.

## 6. Dimensionamiento (estimado, a validar)

Base empírica: la instalación de serie (4 workers) atiende **unos 150 buzones activos a la vez** en
producción. Un worker ocupa ~1 núcleo en hora punta y 250-400 MB de memoria. «Activo» = con el
webmail abierto; en una organización típica, en hora punta está abierto el 30-40 % de los buzones.

| Buzones | Activos en punta | Nodos de aplicación | Workers totales | PostgreSQL | Redis | Dovecot |
|---|---|---|---|---|---|---|
| 300 | ~120 | 1 (o 2 para HA) × 4 vCPU, 8 GB | 4-6 | 2 vCPU, 4 GB, el mismo nodo | el mismo nodo | 1 máquina |
| 1000 | ~400 | 2 × 8 vCPU, 16 GB | 12-16 | 4 vCPU, 8 GB + réplica | Sentinel ×3 (1 GB) | 1 máquina, SSD, 8 vCPU |
| 2500 | ~1000 | 3 × 8 vCPU, 16 GB | 24-30 | 8 vCPU, 16 GB + réplica + PgBouncer | Sentinel ×3 (2 GB) | proxy + 2 backends |
| 5000 | ~2000 | 4-5 × 8 vCPU, 16 GB | 40-50 | 8-16 vCPU, 32 GB + réplica + PgBouncer | Sentinel ×3 (4 GB) | proxy + 3-4 backends |

- Workers por nodo ≈ núcleos (no más: el trabajo pesado es IMAP y descifrar, no esperar).
- Conexiones a PostgreSQL sin PgBouncer = nodos × workers × `DB_POOL_MAX` (con 5 nodos × 10 × 10 son
  500: demasiadas). Con PgBouncer, 50-80 conexiones reales bastan.
- El almacenamiento de correo manda: calcule 1-5 GB por buzón según la política de cuotas, más
  respaldos, y IOPS suficientes (SSD) para la búsqueda en el texto (índice Flatcurve/Xapian).
- El cuello de botella habitual a partir de 1000 buzones es **Dovecot**, no el webmail.

## 7. Objetivos de rendimiento y cómo medirlos

`deploy/escala/prueba-carga-webmail.py` (solo biblioteca estándar) inicia sesión con una o varias
cuentas de prueba y mezcla «bandeja» (página 1 de INBOX, 50 mensajes) y «búsqueda» en cabeceras.

```bash
# cuentas.txt: «usuario@dominio:clave» por línea, cuentas de prueba SIN segundo factor
python3 deploy/escala/prueba-carga-webmail.py --url https://mail.example.org \
    --cuentas cuentas.txt --concurrencia 40 --duracion 120 --busqueda factura
```

Objetivos (medidos desde la red interna, servidor dimensionado según §6, buzones de prueba de unos
5000 mensajes):

| Operación | p50 | p95 |
|---|---|---|
| Inicio de sesión | ≤ 600 ms | ≤ 1500 ms |
| Bandeja (página 1, 50 mensajes) | ≤ 300 ms | ≤ 800 ms |
| Búsqueda en cabeceras | ≤ 800 ms | ≤ 2500 ms |
| Errores (5xx o sin respuesta) | — | < 1 % |

El script termina con código 1 si no se cumplen. Tenga en cuenta los límites del propio webmail:
300 lecturas por minuto y usuario (los 429 se cuentan aparte; reparta entre varias cuentas o suba
`RATE_LIMIT_READ_PER_MIN` en el entorno de pruebas) y 20 intentos de inicio de sesión cada 5 minutos
por IP. La búsqueda dentro del cuerpo (6 por minuto y usuario) no entra en esta prueba.

**Objetivo de disponibilidad** con la topología de §1: 99,9 % mensual (≈ 43 min). Con una sola
máquina no hay compromiso: cada actualización corta el webmail unos segundos y una avería lo corta
hasta repararla.

## 8. Actualizar sin corte

`deploy/escala/actualizar-sin-corte.sh` reinicia las réplicas **una a una**: drena (crea el archivo
de drenaje → `/api/listo` 503 → el balanceador deja de mandarle tráfico), espera, reinicia, espera
`/api/salud`, quita el drenaje, espera `/api/listo` = 200 y solo entonces pasa a la siguiente. Si una
no vuelve, se detiene y deja las demás como estaban. Antes de empezar comprueba que todas están
listas.

```bash
REPLICAS="app1.example.org app2.example.org" PASO_PREVIO="cd /opt/maquita-webmail && git fetch && git checkout v1.11.0 && backend/venv/bin/pip install -q -r backend/requirements.txt" \
    deploy/escala/actualizar-sin-corte.sh
deploy/escala/actualizar-sin-corte.sh --simular     # solo enseña lo que haría
```

- Cada destino: `host[:puerto[:servicio[:archivo_drenaje]]]`; `local` = esta máquina, el resto por
  SSH como root.
- **Migraciones de base**: tienen que ser compatibles con la versión anterior (añadir columnas o
  tablas, nunca renombrar ni borrar en la misma versión), porque durante el reinicio conviven las dos.
  Las de `migrations/` ya siguen la regla de ser idempotentes; se lanzan una vez, antes del primer nodo.
- Con una sola réplica, el script avisa: no hay a quién pasar el tráfico.
- En una sola máquina también se puede: `maquita-webmail@.service` con dos instancias y nginx
  repartiendo entre ellas (instrucciones en el propio archivo).
- El actualizador automático firmado (`deploy/actualizar`) sigue pensado para una sola máquina; en un
  clúster se usa este script (ver `docs/SOPORTE-Y-VERSIONES.md`).

## 9. Límites honestos y lo que falta

- **No probado aún en un clúster real.** Las piezas tienen pruebas automáticas (bloqueos con Redis
  real y varios procesos, Sentinel con un centinela real, reinicio escalonado con réplicas simuladas,
  salud y alias v1); falta una prueba de varias máquinas con carga de verdad.
- **PgBouncer** no se probó contra un PgBouncer real (el CI no lo tiene); sí la configuración del
  cliente y la ausencia de sentencias incompatibles.
- **Archivos locales** (§2): firmas, adjuntos de calendario, marca subida, evidencias de cumplimiento.
  Hoy hace falta almacenamiento compartido montado en todas las réplicas; moverlos a PostgreSQL o a
  almacenamiento de objetos queda pendiente.
- **Réplica de lectura:** el pool existe, pero ninguna consulta lo usa todavía. Migrar informes y
  directorio a `pool_lectura()` es trabajo pendiente (cuidado con leer lo que se acaba de escribir).
- **Panel de administración** y **portal de dominio**: ejecutan órdenes del sistema en la máquina de
  correo (colas de Postfix, sitios web, cortafuegos), así que siguen siendo de un solo nodo. Tienen
  `/api/salud` y `/api/listo`, pero no se reparten entre máquinas.
- **Sentinel** solo lo entiende el backend del webmail. El panel, el Drive y el chat usan `redis://`:
  con Sentinel, apúntelos a un HAProxy que mande siempre al principal (ejemplo comentado en
  `haproxy.cfg.ejemplo`).
- **Correos pospuestos:** el bucle de restauración busca la contraseña en una clave de Redis que ya no
  existe (las credenciales son por sesión desde F-01) y mueve el primer mensaje de la carpeta, no el
  pospuesto. Se protegió para que no se duplique, pero la restauración automática no funciona; está
  apuntado para corregir aparte.
- **Redis Cluster** (no Sentinel) no está soportado: el código usa pub/sub y claves sin etiquetas de
  ranura. Para 5000 buzones un Redis con Sentinel sobra.
- **Procesamiento asíncrono por colas** (ROADMAP): las tareas pesadas siguen en el proceso web
  (sincronización RAG, exportaciones). Con varias réplicas funcionan, pero una cola dedicada
  (p. ej. con Redis Streams) queda para una versión posterior.
- **Sistema de complementos** para reglas de cumplimiento propias: no empezado.
