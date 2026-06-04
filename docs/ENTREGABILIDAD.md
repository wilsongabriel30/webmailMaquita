# Entregabilidad: cómo llegar a 10/10 y no caer en spam

Tener SPF, DKIM y DMARC es el mínimo. Para sacar **10/10 en los tests más
exigentes** (mail-tester.com, learndmarc, internet.nl) y que Gmail/Outlook
confíen, hacen falta varias piezas más que suelen olvidarse. Esta guía las cubre
todas, ordenadas de "imprescindible" a "nivel experto".

> Da por hecho que ya hiciste lo de **[CONFIGURAR-DNS.md](CONFIGURAR-DNS.md)**
> (A, MX, SPF, DKIM, DMARC, PTR). Aquí va lo que falta para el 10/10.

---

## Checklist rápido

| # | Pieza | Nivel | ¿Caes en spam sin esto? |
|---|-------|-------|--------------------------|
| 1 | PTR / rDNS coincidente | Imprescindible | **Sí, casi seguro** |
| 2 | SPF + DKIM + DMARC alineados | Imprescindible | Sí |
| 3 | HELO/EHLO = FQDN = PTR | Imprescindible | A menudo |
| 4 | `postmaster@` y `abuse@` existen | Imprescindible | Penaliza |
| 5 | IP fuera de listas negras (DNSBL) | Imprescindible | **Sí** |
| 6 | Contenido bien formado | Alto | Penaliza |
| 7 | MTA-STS + TLS-RPT | Recomendado | No, pero suma |
| 8 | DANE/TLSA (con DNSSEC) | Experto | No, pero suma |
| 9 | BIMI (logo en el correo) | Experto/marca | No |

---

## 1-3. Lo imprescindible (repaso)

- **PTR coincidente:** `dig -x TU_IP` debe devolver `mail.tudominio.com`, y ese
  nombre debe resolver de vuelta a la IP (esto se llama **FCrDNS**, forward-confirmed).
- **Alineación:** el dominio del `From:` debe coincidir con el de SPF (Return-Path)
  y el de la firma DKIM. DMARC exige esa "alineación". Si envías como
  `algo@tudominio.com`, firma y SPF deben ser de `tudominio.com`.
- **HELO = FQDN:** tu Postfix debe saludar con `mail.tudominio.com` (no `localhost`).
  En este proyecto ya queda así (`myhostname = mail.tudominio.com`,
  `smtp_helo_name = $myhostname`). Verifica: `postconf myhostname`.

---

## 4. Cuentas postmaster@ y abuse@ (RFC 2142)

Los grandes proveedores **penalizan** dominios sin estas direcciones. Crea alias
que reboten a un buzón real (o créalos como buzones):

```sql
-- como alias hacia tu buzón principal (en la BD maildb)
INSERT INTO alias(address, goto, domain, active) VALUES
  ('postmaster@tudominio.com', 'admin@tudominio.com', 'tudominio.com', true),
  ('abuse@tudominio.com',      'admin@tudominio.com', 'tudominio.com', true)
ON CONFLICT (address) DO NOTHING;
```

(También conviene `hostmaster@` para el SOA del DNS.)

---

## 5. Listas negras (DNSBL/RBL)

Si tu IP está en una lista negra, caes en spam por mucho que hagas bien lo demás.
Las IPs nuevas a veces vienen "sucias" del anterior dueño.

- Comprueba: **mxtoolbox.com/blacklists.aspx** (pega tu IP) o
  `dig +short TU_IP_INVERTIDA.zen.spamhaus.org` (si responde, estás listado).
- Si estás listado: pide la **retirada (delisting)** en el sitio de cada lista
  (Spamhaus, Barracuda, SORBS…). Suele ser un formulario.
- Pide a tu proveedor una **IP limpia** si la tuya arrastra mala reputación.
- **Calienta la IP** ("warmup"): empieza enviando poco volumen y súbelo gradual;
  una IP nueva que de golpe manda miles de correos parece spam.

---

## 6. Contenido del correo (lo que revisa SpamAssassin/Rspamd)

mail-tester también puntúa el **mensaje**:

- Incluye versión **texto plano** además de HTML (multipart/alternative). El
  webmail ya lo hace al redactar.
- Evita HTML "sucio" (todo imágenes y sin texto, enlaces acortados, `<font>`
  antiguos), MAYÚSCULAS y "¡¡GRATIS!!".
- Cabeceras válidas: `Message-ID`, `Date`, `From` correctos (el servidor ya las
  pone).
- Para **boletines/listas**: agrega cabecera `List-Unsubscribe` (y
  `List-Unsubscribe-Post` para "un clic"). Sin esto, Gmail penaliza envíos masivos.
- No mezcles muchos dominios de enlaces ni adjuntes ejecutables.

---

## 7. MTA-STS + TLS-RPT (cifrado obligatorio en tránsito)

**MTA-STS** le dice a otros servidores "exígeme TLS válido siempre" (evita ataques
de degradación). Necesita 3 cosas:

**a) Un subdominio `mta-sts.tudominio.com`** (registro A → tu servidor):

```
A   mta-sts.tudominio.com   ->  203.0.113.45
```

**b) Servir la política** en `https://mta-sts.tudominio.com/.well-known/mta-sts.txt`
(con certificado TLS válido — `certbot -d mta-sts.tudominio.com`). Contenido:

```
version: STSv1
mode: enforce
mx: mail.tudominio.com
max_age: 604800
```

Bloque nginx mínimo:

```nginx
server {
    listen 443 ssl;
    server_name mta-sts.tudominio.com;
    ssl_certificate     /etc/letsencrypt/live/mta-sts.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mta-sts.tudominio.com/privkey.pem;
    location = /.well-known/mta-sts.txt {
        default_type text/plain;
        root /var/www/mta-sts;   # coloca el archivo en /var/www/mta-sts/.well-known/mta-sts.txt
    }
}
```

**c) Dos registros TXT:**

```
_mta-sts.tudominio.com   TXT   "v=STSv1; id=2026060401"
_smtp._tls.tudominio.com TXT   "v=TLSRPTv1; rua=mailto:tls-reports@tudominio.com"
```

- El `id` de `_mta-sts` es cualquier texto; **cámbialo cada vez** que edites la
  política (como un número de versión).
- El segundo (`_smtp._tls`) es **TLS-RPT**: te llegan reportes si alguien no pudo
  entregarte por TLS.

---

## 8. DANE / TLSA (nivel experto — requiere DNSSEC)

DANE ancla tu certificado TLS en el DNS. Es más fuerte que MTA-STS pero **exige
que tu dominio tenga DNSSEC**.

1. **Activa DNSSEC** en tu dominio (en el registrador o tu BIND: firma la zona con
   `dnssec-signzone` / habilita la firma automática; publica el registro DS en el
   registrador).
2. Genera el registro **TLSA** del certificado de `mail.tudominio.com` (puerto 25):

```bash
# 3 1 1 = uso DANE-EE, selector SPKI, hash SHA-256 (lo más común)
openssl x509 -in /etc/letsencrypt/live/mail.tudominio.com/cert.pem \
  -noout -pubkey | openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | xxd -p -c256
```

```
_25._tcp.mail.tudominio.com   TLSA   3 1 1 <hash_que_salió_arriba>
```

> Ojo: con Let's Encrypt el certificado **rota** cada ~90 días; usa `3 1 1` sobre
> la **clave pública** (no el cert) y reusa la misma clave al renovar
> (`certbot --reuse-key`), o automatiza la actualización del TLSA. Si no, romperás
> la entrega. Por eso DANE es "experto".

---

## 9. BIMI (tu logo junto al correo)

BIMI muestra el logo de tu marca en Gmail/Apple Mail. **Requiere DMARC en
`p=quarantine` o `p=reject`** (no `none`). Pasos:

1. Logo en **SVG (perfil Tiny PS)**, cuadrado, alojado en HTTPS.
2. Registro: `default._bimi.tudominio.com TXT "v=BIMI1; l=https://tudominio.com/logo.svg; a="`
3. Para que aparezca en Gmail necesitas además un **VMC** (certificado de marca
   verificada, de pago, de DigiCert/Entrust). Sin VMC funciona en algunos clientes,
   no en Gmail.

---

## Cómo probar tu nota

1. **mail-tester.com**: te da una dirección; envíale un correo **desde tu webmail**
   y abre el reporte. Apunta a **10/10**. Te dice exactamente qué resta puntos.
2. **internet.nl/mail**: test exhaustivo (SPF, DKIM, DMARC, DANE, STARTTLS, DNSSEC,
   MTA-STS, RPKI). Apunta a 100%.
3. **learndmarc.com** / **dmarcian**: visualizan tu alineación SPF/DKIM/DMARC.
4. **Gmail "Mostrar original"**: en un correo que te llegue a Gmail, revisa que
   SPF=PASS, DKIM=PASS, DMARC=PASS.

### Si caes en spam, revisa en este orden

1. ¿PTR coincide y hay FCrDNS? (lo #1 de los rechazos)
2. ¿IP en alguna lista negra?
3. ¿SPF/DKIM/DMARC dan PASS **y alineados** en "Mostrar original" de Gmail?
4. ¿HELO es el FQDN, no localhost?
5. ¿Existen `postmaster@`/`abuse@`?
6. ¿El contenido tiene texto plano y no parece spam?
7. Reputación: IP nueva → calentar volumen poco a poco.

---

## Resumen: todos los registros DNS para 10/10

Sobre los 6 básicos de [CONFIGURAR-DNS.md](CONFIGURAR-DNS.md), añade:

| Tipo | Nombre                        | Valor                                                     |
|------|-------------------------------|-----------------------------------------------------------|
| A    | `mta-sts.tudominio.com`       | tu IP                                                     |
| TXT  | `_mta-sts.tudominio.com`      | `v=STSv1; id=2026060401`                                 |
| TXT  | `_smtp._tls.tudominio.com`    | `v=TLSRPTv1; rua=mailto:tls-reports@tudominio.com`       |
| TLSA | `_25._tcp.mail.tudominio.com` | `3 1 1 <hash>` (solo con DNSSEC)                         |
| TXT  | `default._bimi.tudominio.com` | `v=BIMI1; l=https://.../logo.svg; a=` (opcional)        |

Con esto, más los 6 básicos y una IP limpia, llegas al 10/10 de los tests más
exigentes.
