# Configurar el dominio y el DNS (guía para principiantes)

Para que tu servidor de correo **envíe y reciba** correos que **no caigan en spam**,
no basta con instalar el software: hay que decirle al mundo "este servidor es el
correo oficial de mi dominio". Eso se hace con **registros DNS**.

Esta guía explica cada registro desde cero. Si nunca tocaste un DNS, está pensada
para ti. Usaremos `tudominio.com` como ejemplo y `mail.tudominio.com` como el
nombre del servidor.

---

## ¿Qué necesitas antes de empezar?

1. **Un dominio propio** (lo compras en un registrador: Namecheap, GoDaddy,
   Cloudflare, Google Domains, etc.). Ej: `tudominio.com`.
2. **Un servidor con IP pública fija** (un VPS en Hetzner, OVH, DigitalOcean,
   Contabo, etc.). Anota su **IP pública** (ej: `203.0.113.45`).
3. **Acceso al panel de DNS** de tu dominio (normalmente en el mismo sitio donde
   compraste el dominio, o en Cloudflare si lo delegaste ahí).

> El instalador (`deploy/webmail/instalar.sh`) ya dejó el servidor listo y
> **generó tu clave DKIM**. Aquí solo publicas los registros en el DNS.

---

## ¿Dónde configuro estos registros? (elige tu caso)

Los mismos registros (A, MX, SPF, DKIM, DMARC) se publican **igual**, pero el
**lugar** depende de quién administra tu DNS. Identifica tu caso:

- **Caso A — Panel web (lo más común).** Tu dominio usa los nameservers de tu
  registrador (Namecheap, GoDaddy, Google Domains) o de Cloudflare. Entras a su
  panel de DNS y **agregas filas** en una tabla. Las tablas de esta guía son
  exactamente eso.

- **Caso B — DNS gestionado por tu proveedor de VPS.** Algunos proveedores
  (Hetzner, OVH, DigitalOcean) ofrecen su propio panel de DNS, o te piden los
  registros por ticket. Mismos valores, su panel.

- **Caso C — Tu propio servidor DNS (BIND, PowerDNS, etc.) en tu data center.**
  Si tú eres el DNS autoritativo del dominio, **editas el archivo de zona** (o la
  base de datos de PowerDNS) y recargas. Ver el [apéndice de zona BIND](#apéndice-si-gestionas-tu-propio-dns-bind--powerdns)
  al final con todos los registros en formato de archivo de zona.

- **El PTR (registro 6) es aparte en todos los casos:** vive en la **zona inversa**
  de la IP. Si tu IP te la da un proveedor, lo configuras en su panel o por ticket.
  Si tu proveedor te **delegó** el bloque de IPs (tienes tu propia
  `in-addr.arpa`), lo pones en tu zona inversa en BIND.

Si no sabes cuál es tu caso, busca "nameservers" de tu dominio:
`dig +short NS tudominio.com` — si responde algo como `ns1.cloudflare.com` es
Caso A; si responde tus propios `ns1.tudominio.com` apuntando a tu data center,
es Caso C.

---

## ¿Qué es un registro DNS?

El DNS es como la "agenda de teléfonos" de internet: traduce nombres
(`tudominio.com`) a direcciones (IP) y guarda información del dominio. Cada
"registro" es una entrada de esa agenda, con un **tipo** (A, MX, TXT…), un
**nombre** y un **valor**.

En tu panel de DNS verás una tabla donde agregas filas. Vamos uno por uno.

---

## 1. Registro A — "dónde vive el servidor"

Apunta el nombre del servidor a su IP.

| Tipo | Nombre              | Valor (apunta a)        |
|------|---------------------|-------------------------|
| A    | `mail.tudominio.com`| `203.0.113.45` (tu IP)  |

**Para qué sirve:** que `mail.tudominio.com` resuelva a tu servidor. Sin esto,
nadie encuentra tu correo.

---

## 2. Registro MX — "a qué servidor entregar el correo"

Le dice a los demás servidores: "los correos para `@tudominio.com` entrégalos en
`mail.tudominio.com`".

| Tipo | Nombre         | Valor                | Prioridad |
|------|----------------|----------------------|-----------|
| MX   | `tudominio.com`| `mail.tudominio.com` | `10`      |

**Para qué sirve:** recibir correo. La "prioridad" (10) solo importa si tienes
varios servidores; con uno, cualquier número va bien.

---

## 3. Registro SPF — "quién puede enviar en mi nombre"

Es un registro **TXT** que lista qué servidores pueden enviar correo de tu
dominio. Evita que otros se hagan pasar por ti.

| Tipo | Nombre         | Valor              |
|------|----------------|--------------------|
| TXT  | `tudominio.com`| `v=spf1 mx ~all`   |

**Qué significa:** `v=spf1` (es SPF), `mx` (autoriza al servidor del registro MX),
`~all` (los demás, "sospechosos pero no rechazar"). Solo puede haber **un** SPF
por dominio.

---

## 4. Registro DKIM — "la firma digital de tus correos"

Tu servidor **firma** cada correo con una clave privada; el registro DKIM publica
la clave **pública** para que los demás verifiquen que el correo es auténtico y no
fue alterado.

El instalador **ya generó tu clave** y dejó el registro a publicar en
`/tmp/dkim-tudominio.com.txt` (también se muestra al final de la instalación).

| Tipo | Nombre                       | Valor                          |
|------|------------------------------|--------------------------------|
| TXT  | `mail._domainkey.tudominio.com` | `v=DKIM1; k=rsa; p=MIIB...` (lo que generó el instalador) |

**Cómo copiarlo:** abre el archivo y copia TODO lo que está entre comillas (la
clave `p=...` es larga; va completa, sin espacios ni saltos). Algunos paneles de
DNS piden pegar solo el valor; otros aceptan el bloque completo.

```bash
cat /tmp/dkim-tudominio.com.txt
```

**Para qué sirve:** sin DKIM, Gmail y Outlook desconfían y te mandan a spam.

---

## 5. Registro DMARC — "qué hacer si algo no cuadra"

Le dice a los servidores qué hacer con correos que dicen ser tuyos pero fallan SPF
o DKIM, y a dónde enviarte reportes.

| Tipo | Nombre                | Valor                                                      |
|------|-----------------------|-----------------------------------------------------------|
| TXT  | `_dmarc.tudominio.com`| `v=DMARC1; p=quarantine; rua=mailto:postmaster@tudominio.com` |

**Qué significa:** `p=quarantine` (lo sospechoso, a spam), `rua=...` (te llegan
reportes). Más adelante, cuando todo funcione, puedes endurecer a `p=reject`.

---

## 6. PTR (DNS inverso) — "el nombre real de tu IP"

Es el más olvidado y el más importante para no caer en spam. Es la traducción
**inversa**: de tu IP a un nombre. Debe coincidir con `mail.tudominio.com`.

**ESTE NO se configura en el panel de tu dominio.** Lo configura el **proveedor de
tu servidor/VPS** (Hetzner, OVH, DigitalOcean…), normalmente en una opción llamada
"Reverse DNS" o "PTR" de tu IP.

| De (IP)        | A (nombre)            |
|----------------|-----------------------|
| `203.0.113.45` | `mail.tudominio.com`  |

**Para qué sirve:** Gmail/Outlook revisan que tu IP tenga un PTR que coincida con
el nombre del servidor. **Sin PTR, casi seguro tu correo es rechazado.** Si tu
proveedor no te deja configurarlo, considera otro proveedor para correo.

---

## Resumen: todos los registros juntos

Para `tudominio.com` con IP `203.0.113.45`:

| # | Tipo | Nombre                          | Valor                                                        |
|---|------|---------------------------------|--------------------------------------------------------------|
| 1 | A    | `mail.tudominio.com`            | `203.0.113.45`                                               |
| 2 | MX   | `tudominio.com`                 | `mail.tudominio.com` (prioridad 10)                         |
| 3 | TXT  | `tudominio.com`                 | `v=spf1 mx ~all`                                            |
| 4 | TXT  | `mail._domainkey.tudominio.com` | `v=DKIM1; k=rsa; p=...` (lo generó el instalador)          |
| 5 | TXT  | `_dmarc.tudominio.com`          | `v=DMARC1; p=quarantine; rua=mailto:postmaster@tudominio.com` |
| 6 | PTR  | (en tu proveedor de VPS)        | `203.0.113.45` → `mail.tudominio.com`                       |

---

## Comprobar que quedó bien

El DNS tarda en propagarse (de minutos a 24-48 h). Para verificar:

```bash
# ¿Resuelve el servidor?
dig +short A mail.tudominio.com

# ¿El MX apunta bien?
dig +short MX tudominio.com

# ¿SPF, DKIM, DMARC publicados?
dig +short TXT tudominio.com
dig +short TXT mail._domainkey.tudominio.com
dig +short TXT _dmarc.tudominio.com

# ¿El PTR coincide? (debe devolver mail.tudominio.com)
dig +short -x 203.0.113.45
```

Herramientas web útiles (pega tu dominio): **mxtoolbox.com**, **mail-tester.com**
(envía un correo de prueba y te da una nota de 0 a 10 con qué falta).

> **¿Quieres sacar 10/10?** Los 6 registros de arriba son el mínimo. Para la nota
> perfecta en los tests más exigentes hay más piezas (MTA-STS, TLS-RPT, DANE/TLSA,
> BIMI, cuentas `postmaster@`/`abuse@`, salir de listas negras, contenido) — todo
> explicado en **[ENTREGABILIDAD.md](ENTREGABILIDAD.md)**.

---

## Después del DNS

1. Certificado HTTPS:  `certbot --nginx -d mail.tudominio.com`
2. Entra al webmail:   `https://mail.tudominio.com/webmail/`
3. Panel de administración:  `https://mail.tudominio.com:8443`

Crea tus buzones reales desde el panel de administración y ¡listo!

---

## Apéndice: si gestionas tu propio DNS (BIND / PowerDNS)

Si tú eres el servidor DNS autoritativo (Caso C), estos son los mismos registros
en formato de **archivo de zona** (sintaxis BIND), para `tudominio.com` con IP
`203.0.113.45`:

```dns
; ===== Zona directa: tudominio.com =====
$TTL 3600
@       IN  SOA  ns1.tudominio.com. admin.tudominio.com. (
                2026060401 ; serial (súbelo en 1 cada cambio)
                3600       ; refresh
                1800       ; retry
                1209600    ; expire
                3600 )     ; minimum
@               IN  NS    ns1.tudominio.com.
@               IN  NS    ns2.tudominio.com.

; Correo
mail            IN  A     203.0.113.45
@               IN  MX    10 mail.tudominio.com.

; SPF
@               IN  TXT   "v=spf1 mx ~all"

; DKIM (pega aquí el contenido de /tmp/dkim-tudominio.com.txt que generó el instalador)
mail._domainkey IN  TXT   ( "v=DKIM1; k=rsa; "
                            "p=MIIBIjANBgkqhkiG9w0BAQEF...resto_de_la_clave..." )

; DMARC
_dmarc          IN  TXT   "v=DMARC1; p=quarantine; rua=mailto:postmaster@tudominio.com"
```

Recuerda **subir el número de serie** (`serial`) en el SOA cada vez que edites la
zona, y recargar:

```bash
named-checkzone tudominio.com /etc/bind/zones/db.tudominio.com   # validar
rndc reload tudominio.com                                         # recargar (BIND)
```

### PTR en tu propia zona inversa

El PTR solo lo pones tú si tu proveedor te **delegó** el bloque de IPs (tienes la
zona `in-addr.arpa`). La IP se escribe **al revés**:

```dns
; ===== Zona inversa: 113.0.203.in-addr.arpa  (para 203.0.113.x) =====
45      IN  PTR   mail.tudominio.com.
```

Si **no** tienes el bloque delegado (lo normal con un VPS), el PTR lo configura tu
proveedor de la IP en su panel o por ticket. No lo puedes poner tú.

> **PowerDNS, Route53, etc.:** los nombres/valores son idénticos; cambia solo la
> herramienta (interfaz web, API o `pdnsutil`). Lo importante es que existan los 6
> registros con esos valores.

---

## Apéndice: servidores secundarios (maestro oculto, secundario público y HE.net)

Si las zonas las sirve este servidor (Zonas DNS del panel, BIND), otros servidores DNS pueden tener una
copia y responder por ellas: si el principal se cae, los dominios siguen resolviendo. De serie **nadie**
puede pedir las zonas (`allow-transfer { none; }`) y no se avisa a nadie (`notify no`): quien no configure
nada no nota ningún cambio.

La configuración vive en `/etc/maquita-dns/servidor.json` (clave `transferencias`), fuera del
repositorio: las actualizaciones y `instalar-app.sh dns` no la tocan. La clave TSIG, si la hay, va en
`/etc/bind/maquita-tsig.key` (root:bind, 0640).

### Ejemplo: maestro oculto + secundario público + secundario externo

| Servidor | Papel | IP (de ejemplo) |
|---|---|---|
| `hosting-v1` (este servidor: correo, web y Zonas DNS) | maestro **oculto**: solo lo consultan los secundarios | `192.0.2.10` |
| `dns-v2` (BIND propio) | secundario público, `ns1` de cada dominio | `198.51.100.53` |
| HE.net (dns.he.net, servicio gratuito de secundario) | secundario externo, `ns2` de cada dominio | pide la zona desde `203.0.113.2`, responde en `203.0.113.3` |

**1. Servidores de nombres** (panel → Zonas DNS → Ajustes): `ns1` → `198.51.100.53` y `ns2` → `203.0.113.3`.
Con maestro oculto **ninguno** apunta a `192.0.2.10`; el SOA de cada zona nombra a `ns1` (el primero),
así que el maestro tampoco aparece ahí. En el registrador (NIC.EC u otro) se declaran `ns1.tudominio.com`
y `ns2.tudominio.com` con esas IP (registros «glue»).

**2. Transferencias en el maestro** (`hosting-v1`, como root):

```bash
maquita-dns servidor --transferir-a 198.51.100.53,203.0.113.2 \
                     --notificar-a 198.51.100.53,203.0.113.2 \
                     --maestro-oculto si
maquita-dns servidor          # muestra lo configurado (nunca el secreto TSIG)
```

O en el panel: Zonas DNS → Ajustes → «Servidores secundarios». Cada cambio regenera la declaración de
todas las zonas (`/etc/bind/maquita-zonas.conf`), la comprueba con `named-checkconf`, recarga BIND
(`rndc reconfig`) y avisa a los secundarios (`rndc notify`). Si BIND la rechaza, todo vuelve a como estaba.

Con `--maestro-oculto si` se comprueba que haya a quién transferir y avisar y que ningún `ns` apunte a la
IP del correo o de la web de este servidor (si apuntara, el maestro no estaría oculto).

**3. Clave TSIG** (opcional, recomendable con el secundario propio): con clave, el secundario necesita
**la IP de la lista y la clave** a la vez.

```bash
maquita-dns servidor --tsig generar             # hmac-sha256, secreto aleatorio (no se imprime)
maquita-dns servidor --mostrar-secreto           # orden explícita: secreto y bloque para el secundario
maquita-dns servidor --tsig quitar               # vuelve a solo por IP
```

La clave es una sola para todas las zonas y todos los secundarios, y también firma los avisos. Si alguno
de ellos (p. ej. el externo) no puede usarla con `hmac-sha256`, no la active: por ahora no se combina un
secundario con clave y otro solo por IP; la transferencia queda limitada a las IP de la lista.

**4. Secundario público `dns-v2`** (BIND), en su `named.conf.local`:

```
// Pegar lo que da «maquita-dns servidor --mostrar-secreto» (bloque key y server) si usa TSIG.
zone "tudominio.com" {
    type secondary;
    primaries { 192.0.2.10; };
    file "/var/cache/bind/db.tudominio.com";
    allow-notify { 192.0.2.10; };
};
```

**5. HE.net**: en dns.he.net, «Add a new slave», el dominio y como maestro `192.0.2.10`. HE.net pide la
zona desde su propia IP de transferencia (la que muestra su ayuda), que es la que va en `--transferir-a`
y `--notificar-a`.

**6. Cortafuegos**: los secundarios entran al maestro por 53/TCP (transferencias) y 53/UDP (avisos).

### Más opciones

- `--notificar-a 203.0.113.2:5353` o `[2001:db8::53]:5353`: aviso a otro puerto.
- `--transferir-a 2001:db8:53::/64`: una red entera (nunca `0.0.0.0/0`).
- `--transferir-a ninguna`: vacía la lista; `--quitar-transferencias` vacía transferencias, avisos y maestro
  oculto (la clave TSIG se quita aparte, con `--tsig quitar`).
- Una zona distinta de las demás: `maquita-dns servidor --zona tudominio.com --transferir-a 198.51.100.53
  --notificar-a 198.51.100.53`; vuelve a lo general con `maquita-dns servidor --zona tudominio.com --heredar`.
  (Solo desde la consola; el panel muestra qué zonas tienen ajuste propio.)
- Sin `--notificar-a`, los secundarios no reciben aviso y piden los cambios cuando vence el *refresh* del
  SOA (una hora). Los avisos van solo a la lista (`notify explicit`), nunca a los NS de la zona.
- Servidores que parcheaban `zona.py` a mano: el ajuste `deploy/ajustes/67-dns-transferencias.sh` pasa a
  la configuración lo que hoy declara `/etc/bind/maquita-zonas.conf` (con claves TSIG o listas con nombre
  no toca nada y pide hacerlo con las órdenes de arriba).
