# Wazuh y OpenSearch con Maquita (opcional)

Maquita ya trae sus **tableros de seguridad** en el panel general (Seguridad → Tableros: flujo de correo,
inicios de sesión, cumplimiento, anomalías con avisos y escalamiento, informes CSV y PDF). No hace falta
nada más para tenerlos.

Wazuh sirve cuando la organización quiere además un **SIEM central**: juntar los eventos de varios
servidores (correo, sitios, otras máquinas) en un solo sitio, guardarlos más tiempo en OpenSearch,
correlacionarlos y vigilar la integridad de los archivos. Se monta así:

```
 servidor de correo (Maquita)                  otra máquina
 ┌───────────────────────────────┐            ┌──────────────────────────────────────┐
 │ agente Wazuh  ── 1514/TCP ───────────────▶ │ Wazuh manager (análisis y reglas)    │
 │   · /var/log/maquita/*.json   │  1515/TCP  │ Wazuh indexer (OpenSearch)           │
 │   · mail.log / diario         │ (registro) │ Wazuh dashboard (OpenSearch Dashb.)  │
 │   · integridad de archivos    │            └──────────────────────────────────────┘
 └───────────────────────────────┘
```

**El manager no se instala en el servidor de correo**: necesita mucha memoria (el indexador pide 4 GB
como mínimo y 8 GB para ir holgado) y es justo lo que un atacante con acceso al correo querría borrar.

## 1. Montar el manager (todo en uno) en otra máquina

Una VM aparte con Debian 12 o Ubuntu 24.04, 4 vCPU, 8 GB de RAM y 100 GB de disco basta para unos pocos
servidores. Con el asistente oficial de Wazuh (instala manager, indexador OpenSearch y tablero, con
certificados propios):

```bash
curl -sO https://packages.wazuh.com/4.12/wazuh-install.sh
sudo bash wazuh-install.sh -a          # «all-in-one»; al final imprime la clave del usuario admin
```

Guarde la contraseña que imprime al terminar (también queda en `wazuh-install-files.tar`, que conviene
sacar de la máquina y borrar de allí). El tablero queda en `https://<manager>/`.

Abra en el cortafuegos del manager, **solo desde las IP de sus servidores**: 1514/TCP (eventos de los
agentes) y 1515/TCP (registro de agentes). El 443 del tablero, solo desde la red de administración.

### Clave de registro de agentes

Para que no se registre cualquiera que llegue al 1515, active la clave en el manager:

```bash
echo 'una-clave-larga-y-aleatoria' | sudo tee /var/ossec/etc/authd.pass
sudo chmod 640 /var/ossec/etc/authd.pass && sudo chown root:wazuh /var/ossec/etc/authd.pass
# en /var/ossec/etc/ossec.conf, dentro de <auth>:  <use_password>yes</use_password>
sudo systemctl restart wazuh-manager
```

### Reglas y decodificadores de Maquita

Copie la carpeta `deploy/wazuh/manager/` del repositorio al manager y ejecute:

```bash
sudo bash instalar-reglas.sh --simular   # dice qué falta
sudo bash instalar-reglas.sh             # copia, comprueba con wazuh-analysisd -t y reinicia el manager
```

Si Wazuh no acepta la configuración, el guion vuelve a dejar la anterior. Las reglas propias usan los
identificadores **100800-100899**:

| Regla | Nivel | Qué detecta |
|---|---|---|
| 100802 | 8 | `maquita-sudo` rechazó una orden (alguien intentó algo fuera de lo permitido) |
| 100803 | 12 | 5 o más rechazos de `maquita-sudo` en 5 minutos (posible intrusión) |
| 100821 / 100822 / 100823 | 10 / 7 / 4 | Alertas de anomalía de los tableros (alta, media, baja) |
| 100830 / 100831 | 3 / 5 | Inicio de sesión correcto o fallido en el panel general |
| 100832 | 10 | 6 o más inicios de sesión fallidos en el panel en 5 minutos |
| 100834 | 6 | Cambios sensibles en el panel (configuración de seguridad, cortafuegos, claves de respaldo…) |
| 100840 / 100841 | 6 / 4 | Cumplimiento: exportaciones de eDiscovery, búsquedas, custodios, retenciones, lectura de buzones |
| 100845 / 100846 | 4 / 8 | Actividad de cumplimiento desde el webmail (crítica: 8) |
| 100860-100863 | 5-12 | Vigilantes: servicio caído, entrega local fallando, envío masivo anómalo |

Postfix, Dovecot, nginx, sudo y SSH ya vienen con sus propias reglas en Wazuh: fallos de autenticación
SMTP/IMAP, ataques de fuerza bruta, escaneos web, etc.

## 2. Instalar el agente en el servidor de correo

```bash
sudo WAZUH_MANAGER=siem.example.org WAZUH_REGISTRATION_PASSWORD='una-clave-larga-y-aleatoria' \
     bash deploy/webmail/instalar-app.sh wazuh --simular   # qué haría
sudo WAZUH_MANAGER=siem.example.org WAZUH_REGISTRATION_PASSWORD='una-clave-larga-y-aleatoria' \
     bash deploy/webmail/instalar-app.sh wazuh
```

Variables opcionales: `WAZUH_AGENT_NAME` (por omisión, el nombre corto de la máquina), `WAZUH_AGENT_GROUP`
(«maquita»), `WAZUH_VERSION` (versión fija; por omisión la del guion) y `WAZUH_GPG_HUELLA`.

Qué hace (`deploy/wazuh/instalar.sh`, idempotente):

1. Añade el repositorio oficial `packages.wazuh.com/4.x/apt` con su clave, **comprobando la huella**
   de la clave antes de confiar en ella, e instala `wazuh-agent` en la **versión fija** y la retiene
   (`apt-mark hold`): el manager rechaza agentes más nuevos que él, así que una actualización
   automática del agente lo dejaría desconectado. Para subir de versión: primero el manager, luego
   `WAZUH_VERSION=… instalar-app.sh wazuh` en cada servidor.
2. Registra el agente contra el manager indicado (con la clave de registro, si la hay).
3. Añade a `/var/ossec/etc/ossec.conf` un bloque propio entre las marcas `maquita: inicio` y
   `maquita: fin` (lo de fuera no se toca; se respalda antes y se vuelve atrás si Wazuh no lo acepta):
   - **Registros**: `/var/log/maquita/seguridad.json` (alertas de anomalía, auditoría del panel y
     cumplimiento, en JSON), `mail.log` y `auth.log` si existen, el acceso de nginx y de ActiveSync y los
     registros de los vigilantes.
   - **Integridad de archivos (FIM)**: `/etc/postfix`, `/etc/dovecot`, `/etc/nginx`, `/etc/maquita-mail`,
     `/etc/rspamd` y `/etc/sudoers.d` en tiempo real; `/usr/local/sbin` (los ayudantes con privilegios),
     los vigilantes, las unidades de systemd y el código de la aplicación en la revisión periódica (sin
     entornos virtuales, `node_modules` ni `.git`). **Sin `report_changes`**: varios de esos archivos
     llevan claves y Wazuh enviaría su contenido al manager.
4. En los servidores **sin `/var/log/mail.log`** (solo el diario de systemd), activa
   `maquita-diario-wazuh.service`, que copia del diario el correo y la autenticación (donde escribe
   `maquita-sudo`) a `/var/log/maquita/diario.log` en formato syslog. Rota con `/etc/logrotate.d/maquita`.
5. Instala el ayudante `maquita-wazuh estado` (solo lectura, validado en `maquita-sudo`) para la tarjeta
   del panel.

El buzón de correo en sí (`/var/vmail`) **no** se vigila con FIM: cambia con cada mensaje que llega y
llenaría el manager de ruido. Su integridad la cubren los respaldos (`docs/RESPALDOS.md`) y la
retención legal.

El registro JSON lo escribe el recolector de los tableros en cada pasada (cada 5 minutos) cuando hay
agente Wazuh (`/var/ossec`) o `SEG_EXPORTAR_JSON=1` en el `.env` del panel. No lleva contenidos de
correo ni los detalles de la auditoría: quién, qué, sobre qué, cuándo y desde dónde.

## 3. Comprobar

- En el panel: **Seguridad → Tableros → Wazuh** muestra si el agente está conectado, a qué manager, la
  versión y si el bloque de Maquita está en `ossec.conf`.
- En el servidor: `sudo /usr/local/sbin/maquita-wazuh estado` y `/var/ossec/logs/ossec.log`.
- En el manager: `sudo /var/ossec/bin/agent_control -l` y, para probar las reglas sin esperar eventos
  reales, `sudo /var/ossec/bin/wazuh-logtest` con una línea como
  `Oct 21 10:30:01 mail maquita-sudo: MAQUITA_SUDO rechazado usuario=www-data programa=doveadm motivo=prueba args=pw`.

Si no conecta: puertos 1514 y 1515/TCP abiertos desde el servidor de correo, la clave de registro, que la
versión del agente no sea más nueva que la del manager y la hora de las dos máquinas.

## 4. Quitarlo

```bash
sudo systemctl disable --now wazuh-agent maquita-diario-wazuh 2>/dev/null
sudo apt-mark unhold wazuh-agent && sudo apt-get purge -y wazuh-agent
sudo rm -f /etc/apt/sources.list.d/wazuh.list /usr/local/sbin/maquita-wazuh /etc/systemd/system/maquita-diario-wazuh.service
```

Los tableros del panel siguen funcionando igual: no dependen de Wazuh.
