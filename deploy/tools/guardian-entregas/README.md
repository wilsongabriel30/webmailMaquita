# Guardián de entregas

Avisa cuando un correo lleva demasiado tiempo sin poder salir, **antes** de que el servidor lo
devuelva al remitente.

## Por qué existe

El 28/07/2026, en el servidor de correo antiguo, decenas de correos a clientes estuvieron cinco días
reintentando y acabaron rebotando. Nadie se enteró hasta que el rebote llegó al usuario, tres días
tarde. El fallo era un timeout de salida mal configurado, pero lo grave fue **no detectarlo a tiempo**.

Este guardián cubre esa ventana: si algo no sale, avisamos nosotros antes de que lo note el usuario.

## Qué hace

Cada 30 minutos:

1. Revisa la cola de salida y calcula cuánto lleva esperando cada mensaje.
2. Si alguno supera **6 horas**, envía un aviso por correo (el plazo de reintentos son días, así que
   hay margen de sobra para reaccionar).
3. Agrupa los **destinos que más fallan** en el log reciente, para ver de un vistazo si el problema
   es de un dominio concreto o general.
4. Escribe el estado en `/var/lib/maquita-admin/entregas-en-riesgo.json`, para que el panel lo muestre.
5. No repite el mismo aviso antes de 12 horas, para no generar ruido.

El aviso incluye la pista de diagnóstico del incidente que lo originó: si el error menciona
*initial server greeting*, revisar `postconf smtp_helo_timeout`.

## Instalación

```bash
install -m 755 guardian-entregas.sh /usr/local/bin/guardian-entregas.sh
install -m 644 guardian-entregas.service /etc/systemd/system/
install -m 644 guardian-entregas.timer   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now guardian-entregas.timer
```

Comprobar que quedó activo:

```bash
systemctl list-timers guardian-entregas.timer
bash /usr/local/bin/guardian-entregas.sh && tail -3 /var/log/guardian-entregas.log
```

## Ajustes

Variables al inicio de `guardian-entregas.sh`:

| Variable | Por defecto | Qué controla |
|---|---|---|
| `DESTINO_AVISO` | `gestiontecnologia@maquita.com.ec` | A quién se avisa |
| `HORAS_AVISO` | `6` | Antigüedad a partir de la cual un correo en cola preocupa |
| `HORAS_SILENCIO` | `12` | Cada cuánto se puede repetir el mismo aviso |

Tras cambiar la frecuencia del temporizador: `systemctl restart guardian-entregas.timer`.

## Desinstalación

```bash
systemctl disable --now guardian-entregas.timer
rm /etc/systemd/system/guardian-entregas.{timer,service} /usr/local/bin/guardian-entregas.sh
```

## Notas

- Solo lee la cola y el log; no modifica correo ni configuración.
- Es portable a otros servidores con Postfix (usa `postqueue` y `sendmail`); en el correo antiguo
  habría que cambiar la ruta de `sendmail` a `/opt/zimbra/common/sbin/sendmail`.
- Complemento natural: la sección **Correos rebotados** del panel, para reenviar lo que ya rebotó.
