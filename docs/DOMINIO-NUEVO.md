# Dar de alta un dominio nuevo

Un mismo servidor atiende a varias organizaciones. Cada una tiene su dominio de correo y,
si quiere, su propio portal: un nombre (`mail.<empresa>`) por el que su gente entra, ve su
marca y solo puede usar cuentas de su dominio.

## Qué se entrega por dominio

| Qué | Depende de |
|---|---|
| Solo entran cuentas de ese dominio | portal activo |
| Logo, nombre y colores en la pantalla de entrada | marca de la empresa |
| Servidor que recibe Outlook (IMAP, SMTP, ActiveSync) | portal activo |
| Servidor que reciben las aplicaciones móviles | portal activo |
| Alta de cuenta en Android | portal activo |
| Enlaces de los avisos (correo nuevo, tareas) | portal activo |
| Enlaces seguros al leer un mensaje | portal por el que se entra |
| Enlace de un mensaje seguro | portal de quien lo envía |

Una cuenta cuyo dominio **no** tiene portal recibe en todo el servidor general
(`ORG_URL_CORREO`). Nada se rompe por no tener portal.

Sigue siendo general, a propósito:

- Los enlaces seguros que se reescriben **al recibir** el correo (filtro): un mensaje puede ir
  a personas de varias empresas.
- Las llamadas entre servicios (avisos al chat, editor de documentos).

## Pasos

### 1. Infraestructura (fuera del correo)

1. DNS: `MX`, `SPF`, `DKIM`, `DMARC` del dominio; registro `A` o `CNAME` de `mail.<empresa>`;
   `autodiscover.<empresa>` (`CNAME`) o el registro `SRV _autodiscover._tcp`.
2. Certificado con `mail.<empresa>` (y `autodiscover.<empresa>` si se usa `CNAME`) en la web
   **y en IMAP (993) y SMTP (465)**.
3. Servidor web: bloque para `mail.<empresa>` con la misma configuración que el general.

Comprueba que está listo:

```bash
python3 deploy/tools/comprobar-portal.py mail.empresa.example
```

### 2. En el correo

1. Crear el dominio y sus buzones (panel → Dominios, Buzones).
2. Clave DKIM: `rspamadm dkim_keygen -s mail -b 2048 -d empresa.example -k /var/lib/rspamd/dkim/empresa.example.mail.key`
   y publicar el registro que devuelve.
3. **Portal**: panel → Portales por empresa → asociar `mail.empresa.example` con
   `empresa.example`. Es lo que activa todo lo de la tabla de arriba.
4. **Marca**: en la misma pantalla, o desde el portal de administradores de dominio.
5. Agregar el dominio a `/etc/maquita-mail/dominios-propios.txt` (o a `ORG_DOMINIOS`): lo
   protege contra suplantación y lo trata como de casa en enlaces y grupos.

El portal surte efecto en un minuto, sin reiniciar. El paso 5 se lee al arrancar: hay que
reiniciar el correo y el filtro.

### Por línea de órdenes

```bash
psql -d maildb <<'SQL'
INSERT INTO domain (domain, description) VALUES ('empresa.example', 'Empresa de ejemplo');
INSERT INTO portal_empresa (host, dominio) VALUES ('mail.empresa.example', 'empresa.example');
INSERT INTO branding_empresa (dominio, clave, valor) VALUES ('empresa.example', 'org_name', 'Empresa de ejemplo');
SQL
echo empresa.example >> /etc/maquita-mail/dominios-propios.txt
```

## Comprobar

```bash
# Qué servidor recibe una cuenta
curl -s -X POST https://mail.example.org/autodiscover/autodiscover.xml -H 'content-type: text/xml' \
  -d '<Autodiscover><Request><EMailAddress>ana@empresa.example</EMailAddress></Request></Autodiscover>' | grep Server

curl -s 'https://mail.example.org/api/cuenta/descubrir?correo=ana@empresa.example'
curl -s 'https://mail.example.org/api/mobile/config?correo=ana@empresa.example'
```

## Apagarlo

`DIRECCIONES_POR_DOMINIO=0` en el `.env` del correo devuelve todo al servidor general. El
aislamiento de entrada y la marca no dependen de esta variable.
