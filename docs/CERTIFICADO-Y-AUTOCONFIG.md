# Certificado TLS y autoconfiguración del correo

> Resuelve el problema **#15** del reporte externo: los clientes de correo que
> **autoconfiguran probando el dominio pelado** (`dominio.tld:993`) recibían un
> **certificado equivocado**, porque el cert solo cubría `mail.dominio.tld`.

## El problema

Al agregar una cuenta, muchos clientes (Thunderbird, Outlook, iOS) **adivinan** el
servidor probando primero el **dominio pelado**: `dominio.tld:993/465`. Si ahí responde
el mismo servidor pero el certificado **no incluye `dominio.tld`** como nombre, el cliente
muestra **«certificado no válido / nombre no coincide»** y el usuario se traba.

Dos arreglos, complementarios:

1. **Que el certificado cubra los nombres de cliente** que apuntan a este servidor
   (incluido el dominio pelado, si su registro A apunta aquí).
2. **Publicar autoconfig/autodiscover** para que el cliente **no tenga que adivinar**:
   toma la configuración exacta y ni siquiera prueba el dominio pelado.

## La solución (un solo comando)

```bash
bash deploy/webmail/tls/emitir-certificado.sh dominio.tld [correo-admin]
```

El script:

- Averigua la **IP pública** de este servidor.
- Resuelve, contra un **resolver público** (`1.1.1.1`, para no caer en la vista interna
  por *split-horizon*), estos nombres: el **apex** `dominio.tld`, `mail.`, `imap.`,
  `smtp.`, `pop3.`, `autoconfig.`, `autodiscover.`
- Pide a **certbot** solo los que **apuntan a este servidor** (así no falla por un nombre
  inexistente o que apunta a otro lado). Fija el linaje con `--cert-name mail.dominio.tld`,
  de modo que la ruta del cert sea siempre `/etc/letsencrypt/live/mail.dominio.tld/`.
- Publica el **XML de autoconfig** (Thunderbird/Evolution) en
  `https://autoconfig.dominio.tld/mail/config-v1.1.xml` sobre el cert recién emitido.

Correr de nuevo el script **amplía** el certificado si más adelante agregas dominios cuyos
nombres empiecen a apuntar aquí.

## Autodiscover de Outlook

Lo sirve el **backend** (`/autodiscover/autodiscover.xml` y `.json` → puerto 8000): IMAP/SMTP
para Outlook clásico como cuenta IMAP, y **ActiveSync** (esquema `mobilesync` y JSON v2) para el
nuevo Outlook, Outlook clásico como cuenta Exchange, Android e iOS, apuntando a Z-Push
(`deploy/z-push/`). El helper ya incluye `autodiscover.` en el certificado si apunta a este servidor.

## Autodiscover para varios dominios (Outlook, iOS, Android)

Outlook y los celulares buscan `https://autodiscover.<dominio del correo>/autodiscover/autodiscover.xml`
para **cada dominio**, no para el host canónico. Un dominio que aún apunta a otro servidor (el caso
de una migración) no autoconfigura en el nuevo Outlook, que no admite configuración manual. Para
cada dominio de correo del servidor hacen falta, en este orden:

1. **DNS**: `autodiscover.<d>` CNAME al host canónico (`mail.dominio.tld`), `autoconfig.<d>` igual, y
   `_autodiscover._tcp.<d> SRV 0 0 443 mail.dominio.tld.` (Outlook clásico también usa el SRV).
2. **Certificado**: `DOMINIOS_EXTRA="<d> <d2>" emitir-certificado.sh dominio.tld` añade
   `mail./autoconfig./autodiscover.` de cada dominio que ya apunte aquí (un solo linaje, `--expand`).
3. **Respaldo por HTTP** (`deploy/webmail/nginx/autodiscover-dominios.conf`, lo instala el instalador):
   `autodiscover.*` y `autoconfig.*` en el puerto 80 responden **302** al host canónico. Es el método
   que Outlook prueba cuando el TLS del dominio falla, así que un dominio recién apuntado autoconfigura
   **antes** de reemitir el certificado (y el reto ACME de esos nombres sigue sirviéndose).
4. **Comprobar**: `deploy/tools/comprobar-autodiscover.py` (DNS por DoH, certificado, respuesta
   ActiveSync por HTTPS y redirección por HTTP, dominio por dominio, con código de salida).

## Varios dominios de correo en el mismo servidor (SNI)

Si el servidor atiende **más de un dominio** de correo, Postfix/Dovecot deben presentar el
cert correcto según el nombre pedido (**SNI**):

- **Dovecot:** un bloque `local_name mail.otrodominio.tld { ssl_cert = ...; ssl_key = ... }`
  por dominio.
- **Postfix:** `tls_server_sni_maps = hash:/etc/postfix/vmail_sni` y **`postmap -F`** sobre
  ese mapa (¡`-F`!, no el `postmap` normal), luego **`systemctl restart postfix`**
  (con `reload` no relee el mapa SNI).

El validador `deploy/tools/validar-despliegue.sh` comprueba, por cada nombre, que la
conexión TLS presente un cert cuyo nombre **coincide** (detecta el fallo de #15).

## Verificación

```bash
certbot certificates                       # ¿el cert lista el apex + subdominios?
bash deploy/tools/validar-despliegue.sh    # sección TLS/SNI: nombre del cert por puerto
curl -s https://autoconfig.dominio.tld/mail/config-v1.1.xml   # ¿responde el XML?
```

## Nota sobre NUESTRA producción (Maquita)

El cert de `mail.maquita.org` (Let's Encrypt) ya cubre `mail/imap/smtp/pop3/autoconfig/
autodiscover`, y **autoconfig/autodiscover están publicados** → los clientes que
autoconfiguran funcionan. El **apex `maquita.org`** aún **no** está en los SAN; añadirlo es
opcional (solo lo notan clientes que insisten en el dominio pelado en vez de autoconfig).
