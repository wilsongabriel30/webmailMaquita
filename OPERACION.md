# OPERACIÓN — Maquita Mail

Cómo se vigila la plataforma y qué hacer cuando algo avisa. Documento vivo.

---

## Canal de alertas

**Destino:** `gestiontecnologia@maquita.org` y `gestiontecnologia@maquita.com.ec`
**Vía:** correo local con `sendmail`, sin depender de servicios externos.

### Por qué el correo y no otra cosa

No hay sistema de alertas montado. El correo local funciona siempre que Postfix
esté vivo, y Postfix es justo lo que queremos vigilar desde dentro. Tiene un
límite conocido: **si Postfix cae del todo, esta vía no avisa**. Para eso hace
falta vigilancia desde fuera del servidor, que hoy no existe y conviene añadir.

Lo que sí está cubierto es el caso frecuente: los servicios que rodean al correo
fallan mientras Postfix sigue entregando.

---

## Vigilancia del milter DLP

**Qué:** `/usr/local/sbin/vigilar-milter.sh`
**Cuándo:** cada 3 minutos, `vigilar-milter.timer`
**Instalado:** 2026-09-04 (hallazgo A-15, decisión D-1)

### El punto ciego que cierra

Postfix tiene `milter_default_action = accept`: si el milter no responde, **el
correo se entrega igual, sin inspeccionar**. Bueno para la disponibilidad, malo
para enterarse. Antes de esto, la protección contra fugas de datos podía estar
caída durante horas sin que nadie lo notara.

### Qué comprueba

1. Que el servicio `maquita-milter` esté activo.
2. Que el puerto 11335 acepte conexiones. **Activo no es lo mismo que
   respondiendo**: un proceso colgado sigue apareciendo como activo.
3. Que Postfix siga apuntando al milter y que `milter_default_action` no haya
   cambiado sin que nadie lo decidiera.
4. Que la cola de evidencia diferida (hallazgo B2) no acumule marcadores. Cuando
   la base no está disponible, el milter deja un marcador y un cron los reinserta
   cada 7 minutos. Ese cron **solo avisa si la base sigue caída**; si el marcador
   se queda por otro motivo, hasta hoy no lo miraba nadie. Umbral: 5 marcadores.

### Cómo avisa

Un correo cuando aparece la incidencia y otro cuando se recupera. **No repite**
mientras el problema sigue: una caída de una hora serían veinte correos y el
aviso dejaría de leerse. El estado se guarda en
`/var/lib/maquita-admin/estado-vigilancia-milter`.

El correo de recuperación dice **desde cuándo y hasta cuándo** estuvo sin
inspección, para poder revisar el tráfico de esa franja.

### Probado el 2026-09-04

Se detuvo el milter de verdad. Se recibió la alerta en las dos direcciones, la
segunda pasada no generó correo nuevo, y al arrancarlo llegó el aviso de
recuperación. Cuatro correos entregados, dos por dirección.

### Si llega una alerta

```
systemctl status maquita-milter
journalctl -u maquita-milter -n 50
systemctl restart maquita-milter
```

Si el aviso es por marcadores acumulados, el problema está en la base:

```
ls -la /var/lib/maquita-admin/cola-cuarentena/
journalctl -t reconciliar-cuarentena -n 30
```

### Falso positivo conocido

Ninguno hasta la fecha. Si se reinicia el milter a mano, la comprobación puede
coincidir con la ventana de arranque y avisar; el aviso de recuperación llega
tres minutos después.

---

## Lo que NO está vigilado todavía

Escrito para que no se olvide:

- **Postfix, Dovecot y la base de datos.** Si caen, esta vía no avisa porque
  depende de ellos. Necesita vigilancia externa al servidor.
- **El filtro en tubería** (`maquita-filter`, hallazgo N-15). Es el único
  componente que **sí puede detener la entrega**, y no tiene ninguna vigilancia.
  Debería avisar si la cola de Postfix crece o si el filtro tarda de más.
- **La cola de Postfix.** Hoy nadie avisa si se acumulan mensajes.
- **Certificados.** El comodín vence en marzo de 2027 y requiere renovación
  manual anual. El de `mta-sts.maquita.com.ec` vencía en pocos días al momento
  de escribir esto: conviene comprobarlo.
- **Espacio en disco.** El correo ocupa 2,1 TB de 5 TB (44 %).

---

## Umbrales de capacidad conocidos

| Componente | Medida | Techo |
|---|---|---|
| Filtro en tubería | 2,16 s de media, 8,70 s de máximo, 10 procesos | 278 mensajes/minuto en el caso medio; **69 en el peor caso** |
| Pico real observado | 47 mensajes/minuto (2026-09-03) | el 68 % del techo del peor caso |

El filtro en tubería es el cuello de botella del sistema. Subir el número de
procesos en `master.cf` es barato porque cada uno pasa la mayor parte del tiempo
esperando al descompresor y al antivirus, no consumiendo procesador.

## Segundo factor (2FA) del panel de administración

Desde 2026-09-04 la impersonación de buzones exige que quien la use sea **superadministrador** y
haya **iniciado sesión con segundo factor**. El vale que emite el panel dura 5 minutos, nombra un
solo buzón y no se puede reutilizar.

### Activar el 2FA de la propia cuenta
1. Entrar al panel desde la red interna o la VPN (fuera de ahí nginx no deja pasar).
2. Arriba a la derecha, el icono de la persona («Mi cuenta»).
3. En «Verificación en dos pasos», escribir la contraseña actual y pulsar **Activar 2FA**.
4. Escanear el código QR con la aplicación de autenticación (o copiar la clave que aparece debajo).
5. Escribir el código de 6 dígitos y pulsar **Verificar y activar**.
6. **Cerrar sesión y volver a entrar con el código.** La marca de segundo factor se pone al iniciar
   sesión: sin este paso la sesión abierta sigue sin ella y la impersonación responderá 403.

### Si alguien pierde su segundo factor
No hay códigos de respaldo. La cuenta no puede entrar sola: otra persona con acceso tiene que
desactivarle el 2FA.

- **Camino normal (preferido):** otro superadministrador entra al panel, va a «Administradores»,
  edita esa cuenta y le cambia la contraseña. Eso cierra sus sesiones. El 2FA se desactiva desde la
  base (abajo), porque la pantalla de desactivar solo actúa sobre la propia cuenta.
- **Camino de rescate (como root en la VM 130):**

  ```bash
  maquita-admin-2fa estado              # quien tiene 2FA y cuantas sesiones abiertas
  maquita-admin-2fa rescatar <cuenta>   # quita el 2FA y cierra sus sesiones (pide confirmacion)
  ```

  La persona vuelve a entrar solo con contraseña y **debe activar el 2FA de nuevo el mismo día**.
  Queda registrado en `admin_audit` como `totp_rescate`. La herramienta vive en el repositorio
  (`deploy/tools/maquita-admin-2fa`) y lee la contraseña de la base del `.env` del panel.

- **Ojo con la recuperación por correo alternativo** (`/api/admin-recovery`): solo restablece la
  **contraseña**, no toca el segundo factor. Si se perdió el teléfono, ese camino NO alcanza para
  entrar; hay que usar el rescate de arriba.

### Reglas de continuidad
- Debe haber **al menos dos** cuentas de superadministrador con 2FA activo, de personas distintas.
  Con una sola, la impersonación (y con ella el soporte a los buzones) depende de un solo teléfono.
- El secreto del 2FA se genera en el panel y vive en la aplicación del teléfono de cada persona.
  No se comparte, no se guarda en documentos ni se envía por correo o chat.
- Al dar de baja a una persona: desactivar su cuenta en «Administradores» (eso revoca sus sesiones
  al instante) y borrar su secreto con la sentencia de arriba.
