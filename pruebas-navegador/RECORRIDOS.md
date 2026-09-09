# Recorridos de interfaz

Tres tandas, además de las pruebas de regresión de `pruebas/`. Cada una responde a una pregunta
distinta y se corre por separado.

| Tanda | Para qué | ¿Cambia algo? |
|---|---|---|
| `exploracion/` | **Buscar** fallos: recorre las secciones y pulsa lo que encuentra | no |
| `detallada/` | **Comprobar** que lo que usa una persona funciona, sobre un buzón con correo | no |
| `ciclo-correo/` | El camino completo del correo: enviar, deshacer, borrar, recuperar | **sí: envía correo de verdad** |

Todas se configuran por variables de entorno, como las de `pruebas/`: nada de direcciones ni
cuentas dentro del código.

```
cd pruebas-navegador
npm install && npx playwright install chromium     # solo la primera vez

WEBMAIL_URL=https://correo.ejemplo.org \
PRUEBAS_USUARIO=buzon.pruebas@ejemplo.org PRUEBAS_CLAVE='...' \
  npx playwright test -c playwright.detallada.config.js
```

---

## `exploracion/` — buscar fallos

Recorre las siete secciones y **pulsa uno a uno** todos los controles que encuentra, mirando en
cada paso la consola, la red y las excepciones. Escribe un informe (`informe-exploracion.json`)
ordenado por gravedad.

- `mapa.js` — las secciones, sacadas del enrutador real.
- `seguridad.js` — **la frontera de lo que no se pulsa**: nada que envíe, borre, vacíe, cierre la
  sesión o cambie configuración. Está escrita aparte para que se pueda revisar de un vistazo.
- `observador.js` — lo que la página hace por detrás, ya sin el ruido conocido.
- `informe.js` — recoge los hallazgos y los ordena.
- `10-secciones` — cada sección abre, no se queda en blanco y no expulsa a la pantalla de entrada.
- `20-botones` — pulsa lo seguro y avisa de lo que no responde.
- `50-verificar` — **segunda pasada sobre lo que levantó la primera**: mira si el control está
  deshabilitado (y si se nota), si algo lo tapa, o si al forzar la pulsación sí responde.

**Cómo se leen sus avisos.** Una exploración automática señala de más: el elemento del menú de la
sección en la que ya estás no hace nada porque no tiene que hacerlo, y un diálogo nativo del
navegador (`prompt`, elegir fichero) el navegador automatizado lo descarta solo. En la primera
tanda, de 49 avisos **4 eran fallos**. Por eso existe `50-verificar`, y por eso ningún aviso vale
sin mirarlo de cerca.

## `detallada/` — lo que hace una persona

Sobre un buzón con correo dentro. No envía, no borra y no guarda nada: los formularios se abren,
se miran y se cierran.

- `01-correo-lectura` — abrir varios correos, verlos enteros, responder, responder a todos,
  reenviar y ver el origen del mensaje.
- `02-carpetas-y-busqueda` — todas las carpetas del buzón, buscar algo que sí existe, limpiar la
  búsqueda y los filtros de la bandeja.
- `03-calendario-contactos-tareas` — las cinco vistas del calendario, navegar por los meses,
  abrir el formulario de evento, la agenda y las tareas.
- `04-ajustes-y-archivos` — cada pestaña de ajustes, el Drive y el acceso «Archivos» del menú.
- `05-redactor-formato` — negrita, cursiva, subrayado, tachado, color, resaltado: se comprueba
  **el resultado en el cuerpo del mensaje**, no que el botón responda.
- `06-textos-y-color` — que no haya escapes sin interpretar a la vista (se encontraron dos) y que
  la paleta de color aplique el color elegido.
- `07-destinatarios` — que no salga un correo hacia una dirección que no existe. Lo que importa no
  es que aparezca el aviso, sino que **no arranque la cuenta atrás**: el fallo original avisaba de
  nada y mandaba igual.
- `08-busqueda` — el panel de búsqueda avanzada y el rango de fechas, con el tiempo que tarda. Dos
  cosas que esta prueba aprendió a la fuerza y conviene no perder:
  - El rango se compone **con coma** (`entre:2026-09-08,2026-09-10`). Con `..` el proxy devuelve
    403 —bloquea cualquier `..` en la URL como defensa contra path traversal— y la búsqueda ni
    siquiera llega al correo. La prueba comprueba que no se cuele un `..`.
  - El rango de fechas **incluye hoy** a propósito. Con un rango de meses atrás, un buzón de
    pruebas recién hecho devuelve «sin resultados» y la prueba pasa sin haber demostrado nada:
    solo que no revienta. Hay que exigir que **devuelva** el correo.

## `ciclo-correo/` — **envía correo de verdad**

Aparte de las demás a propósito. Usar un **buzón dedicado**, nunca la cuenta de una persona.

- `01-enviar` — a la propia cuenta (llega, se guarda en Enviados, se lee) y, si se indican
  `DESTINO_INTERNO` y `DESTINO_EXTERNO`, a otra cuenta del servidor y a una dirección de fuera.
- `02-tres-finales` — los tres finales de la cuenta atrás: dejar que termine, deshacer, o irse.
- `03-deshacer` — el «Deshacer» **del aviso de envío**, no el del portapapeles: en el redactor hay
  dos botones con ese nombre, y pulsar el que no era hacía acusar al producto de algo que no hace.
- `04-papelera` — eliminar un correo de prueba y recuperarlo. Acepta los diálogos del navegador:
  sin eso, el navegador automatizado responde «cancelar» y parece que el botón no hace nada.
- `05-no-se-pierde` — cerrar la pestaña mientras corre la cuenta atrás. El correo tiene que salir
  igual al volver a abrir.

**El juez es el servidor, no la pantalla.** Cada correo lleva un asunto único; después se
comprueba en el registro, y contando las veces se ve además si algo se envió por duplicado:

```
grep -c "Mailbox Sent: save.*PRUEBA-1788964195217" /var/log/mail.log
```

---

## Reglas para lo que se añada aquí

1. Ninguna dirección, cuenta ni identificador de una instalación dentro del código.
2. Nada que escriba en buzones ajenos ni envíe a personas reales.
3. Si una prueba puede pasar sin que ocurra lo que dice, está mal hecha.
4. **Un aviso sin comprobar no vale nada.** Antes de dar algo por roto, mirarlo de cerca: en
   estas tandas, la mayoría de los avisos automáticos eran de la propia prueba, no del producto.
