# Lecciones de OnlyOffice en producción (y cómo este proyecto las aplica)

> Este proyecto no es la primera integración de OnlyOffice que opera el equipo.
> Una instancia anterior (conectada a otro gestor de archivos) sufrió pérdida
> de datos y cortes que costaron días de diagnóstico. Cada error se documentó
> y AQUÍ están las protecciones para que no se repitan. Si vas a operar esta
> instalación, lee esto una vez: te ahorrará los mismos golpes.

## 1. La "key" del documento ES la sala de co-edición (el error más caro)

**Qué pasó:** la key se generaba con datos que CAMBIAN (el etag del archivo,
un timestamp, o la ruta que ve cada usuario). Resultado: usuarios que abrían
el mismo archivo entraban a SALAS DISTINTAS; al guardar, una sala pisaba a la
otra → **pérdida de datos** con 4-5 usuarios ("con 2-3 va bien, con más se
borra"). Se llegó a sospechar de la licencia y de migrar de editor: era la key.

**Cómo lo aplica este proyecto (por diseño, no lo toques):**
- La key se construye con el DUEÑO + RUTA + una VERSIÓN DE SESIÓN guardada en
  BD (`onlyoffice_sesion`), nunca con etag/mtime/timestamp.
- La versión solo sube cuando la sala se CIERRA (callback status=2, ya no queda
  nadie). Durante la edición la key es constante e idéntica para todos:
  internos, invitados por enlace y miembros de unidades entran a UNA sala.
- En unidades compartidas la key no depende del usuario; en el espacio
  personal se usa siempre la identidad del dueño (también para los enlaces).

**Regla:** si alguna vez tocas la generación de la key, dos usuarios abriendo
el mismo archivo DEBEN obtener la misma key (verifícalo con curl antes de
desplegar). Key distinta = salas separadas = datos pisados.

## 2. El callback de guardado NUNCA puede morir por timeout

**Qué pasó:** el callback final de guardado pasaba por un bloque nginx con
`proxy_read_timeout 30s`. Con archivos grandes o el servidor ocupado, nginx
respondía 504 al Document Server, este reintentaba 2 veces y luego
**descartaba el documento ensamblado**: se perdía TODO el trabajo de la
sesión. En el log del DS se ve como `handleDeadLetter end: requeue = false`.

**Cómo lo aplica este proyecto:**
- Los bloques nginx provistos (`deploy/nginx-almacen.conf`) llevan
  `proxy_read_timeout 600s` en `/api/almacen/` — más largo que el timeout
  interno del DS (300s), que es la relación correcta.
- Si publicas la API por OTRO proxy/dominio, replica esos timeouts. El
  síntoma de que lo olvidaste: "editaba bien y al cerrar se perdió todo".

## 3. Autoguardado periódico al almacenamiento (durabilidad tipo Drive)

**Qué pasó:** sin ensamblado periódico, el archivo real solo se escribía al
CERRAR la sesión. Si ese único guardado fallaba, se perdía la sesión entera.

**Cómo aplicarlo (requiere shell en la VM del Document Server):**
```bash
docker exec onlyoffice bash -c "
  cp /etc/onlyoffice/documentserver/local.json /etc/onlyoffice/documentserver/local.json.bak
  python3 - <<'PY'
import json
p = '/etc/onlyoffice/documentserver/local.json'
d = json.load(open(p))
d.setdefault('services', {}).setdefault('CoAuthoring', {})['autoAssembly'] = {
    'enable': True, 'interval': '5m'}
json.dump(d, open(p, 'w'), indent=2)
PY
  supervisorctl restart ds:docservice ds:converter"
# Guardar además una copia FUERA del contenedor (local.json se pierde al recrearlo):
docker cp onlyoffice:/etc/onlyoffice/documentserver/local.json /opt/onlyoffice/data/local.json.respaldo
```
Con esto el DS escribe el documento al Almacén CADA 5 MINUTOS durante la
edición: lo máximo que se puede perder son 5 minutos, no la sesión. El botón
Guardar ya persiste al instante (`forcesave: true` viene en la config).

## 4. El límite de 20 conexiones de la edición Community

El Document Server Community (gratuito, AGPL) admite **20 conexiones de
edición simultáneas** (suman todas las pestañas de todos los documentos). Al
llegar al límite, los siguientes entran como lectores — NO pierde datos, pero
"no deja entrar". El DS avisa en su log al llegar al 70%:

```bash
docker logs onlyoffice 2>&1 | grep -i "connections limit"
```

Si tu organización va a tener más de ~15 personas EDITANDO a la vez (leer no
cuenta), planifica: otra VM con un segundo Document Server (mismo secreto) —
los documentos deben repartirse de forma FIJA entre servidores para no partir
salas — o la licencia comercial de OnlyOffice.

## 5. AppArmor puede impedir que el contenedor arranque tras un reinicio

**Qué pasó:** en Debian con `apparmor-profiles` instalado, tras un reinicio el
perfil `runc` en modo enforce bloqueó al runtime de docker
(`libseccomp.so.2 ... Permission denied` / `runc ... exit status 127`) y el
Document Server no arrancó.

**Prevención (una vez, en la VM del DS):**
```bash
ln -sf /etc/apparmor.d/runc /etc/apparmor.d/disable/runc 2>/dev/null
ln -sf /etc/apparmor.d/crun /etc/apparmor.d/disable/crun 2>/dev/null
apparmor_parser -R /etc/apparmor.d/runc 2>/dev/null
apparmor_parser -R /etc/apparmor.d/crun 2>/dev/null
```
(Se regenera si se actualiza `apparmor-profiles`: revisar tras `apt upgrade`.)

## 6. Las vistas previas pueden tumbar el servidor ("tormenta de conversiones")

**Qué pasó:** abrir una carpeta con muchos documentos disparaba TODAS las
miniaturas a la vez → decenas de conversiones simultáneas → el servidor de
archivos se quedó sin memoria y dejó de responder.

**Cómo lo aplica este proyecto (por diseño):**
- Máximo 2 conversiones de miniatura simultáneas por worker; el resto espera.
- Un documento cuya miniatura falló no se reintenta por 5 minutos.
- Las miniaturas se cachean en disco (clave ruta+fecha) y en el navegador
  (24h): cada documento se convierte UNA vez en su vida útil.

## 7. No midas websockets con curl

Un handshake websocket probado con curl "tarda 15 segundos" porque curl nunca
manda la autenticación y el servidor cierra por timeout. Eso NO es una avería.
Prueba los websockets con un cliente real (el propio webmail) antes de
diagnosticar lentitud.
