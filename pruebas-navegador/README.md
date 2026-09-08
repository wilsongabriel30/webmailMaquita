# Pruebas con navegador de verdad

Recorridos de persona sobre una instalación real, con Chromium: entrar, mirar la bandeja, abrir
el redactor, abrir el Drive. Lo que no se ve con `curl`: avisos que tapan la pantalla, errores en
la consola, peticiones que fallan por detrás mientras la página «parece» funcionar.

Encontraron cosas de verdad el primer día: el Drive rechazando todas las sesiones del correo
porque el servicio llevaba en memoria un secreto anterior a una rotación, y ruido de peticiones
401 en cada carga.

## Cómo se corren

Nada está cableado a una instalación concreta: todo llega por variables de entorno.

```
cd pruebas-navegador
npm install
npx playwright install chromium          # solo la primera vez

WEBMAIL_URL=https://correo.ejemplo.org \
PRUEBAS_USUARIO=buzon.pruebas@ejemplo.org \
PRUEBAS_CLAVE='...' \
npx playwright test
```

Conviene un **buzón dedicado a las pruebas**, no la cuenta de una persona. No hace falta que
tenga correo dentro ni que esté vinculado a nadie en el directorio: las pruebas lo tienen en
cuenta y lo dicen por pantalla.

Para ver el navegador mientras trabaja: `npx playwright test --headed`.
Para una sola prueba: `npx playwright test pruebas/02-correo.spec.js`.

## Cómo están hechas

- **Una sola sesión para toda la tanda** (`pruebas/base.js`). Entrar en cada prueba chocaba
  contra dos cosas del producto que funcionan bien: el límite de intentos de entrada (429 tras
  varios seguidos) y la renovación del vale, que invalida el anterior.
- **Nunca dar por buena una entrada que no ocurrió** (`pruebas/apoyo.js`). La primera versión
  esperaba una URL que ya coincidía con la pantalla de entrada, así que una prueba pasaba sin
  haber iniciado sesión. Ahora se comprueba la respuesta del servidor y que la pantalla cambió.
- **Se apartan los avisos que tapan la interfaz**, como haría una persona (la campaña de
  verificación en dos pasos sale encima de todo y bloquea los clics).
- **El ruido conocido se anota, no se esconde**: las peticiones fallidas del chat se cuentan
  aparte para que no tapen un fallo nuevo, y salen por pantalla.

## Qué se comprueba hoy

| Prueba | Qué protege |
|---|---|
| La pantalla de entrada carga limpia | sin errores de consola ni peticiones fallidas antes de entrar |
| La bandeja trae las carpetas | la sesión sirve y la interfaz pinta lo esencial |
| El redactor se abre y acepta un destinatario | el camino de escribir un correo no está roto |
| Usar el correo no deja peticiones con error | detecta ruido nuevo en cada carga |
| El Drive acepta la sesión del correo | que no mande a la pantalla de entrada teniendo sesión válida |

## Reglas para lo que se añada aquí

1. Nada de direcciones, cuentas ni identificadores de una instalación en el código.
2. Ninguna prueba envía correo a personas reales ni escribe en buzones ajenos.
3. Si una prueba puede pasar sin que ocurra lo que dice, está mal hecha: hay que comprobar la
   respuesta del servidor, no solo lo que se ve.
