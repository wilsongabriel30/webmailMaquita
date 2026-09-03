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

Lo sirve **z-push** (`deploy/z-push/`): instálalo para responder
`https://autodiscover.dominio.tld/autodiscover/autodiscover.xml`. El helper ya incluye
`autodiscover.` en el certificado si apunta a este servidor.

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
