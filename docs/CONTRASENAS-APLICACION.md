# Contraseñas de aplicación: cómo conectar Outlook, el celular o Thunderbird

Para el personal. Tu contraseña principal sirve para entrar al webmail y a la app. Para cualquier
otro programa de correo (Outlook nuevo o clásico, el correo del iPhone o de Android, Thunderbird)
usas una **contraseña de aplicación**: una distinta por cada programa, que puedes anular sola sin
cambiar tu contraseña.

## Por qué
El webmail te pide el segundo factor (el código del teléfono). Los programas de correo no saben
pedirlo: entran solo con contraseña. Si esa fuera tu contraseña principal, quien la consiguiera
entraría por ahí saltándose el segundo factor. Con una contraseña por programa, lo que se filtra
se anula en un clic y el resto sigue funcionando.

## Cómo se crea (un minuto)
1. Webmail → **Configuración** (engranaje) → pestaña **Seguridad** → **Contraseñas de aplicación**.
2. Escribe el nombre del programa («Outlook del trabajo», «iPhone») y tu contraseña actual →
   **Crear contraseña**.
3. Aparece una contraseña de 16 letras y números en cuatro grupos (`abcd-efgh-jkmn-pqrs`).
   **Cópiala en ese momento**: no se vuelve a mostrar. Se puede escribir con o sin guiones.
4. En el programa: usuario = tu correo completo, contraseña = la que acabas de crear, servidor =
   el de siempre (`mail.maquita.org`). Nada más cambia.

Máximo diez por cuenta. En la lista ves cuándo se usó cada una por última vez y desde qué dirección:
si una que no reconoces aparece usada, revócala y avisa a tecnología.

## Cuándo se anulan solas
- Al **cambiar tu contraseña principal** se revocan todas: vuelve a crear una por programa. Es a
  propósito: si cambias la contraseña porque sospechas algo, ningún programa viejo sigue entrando.
- Si un administrador desactiva tu cuenta.

## Preguntas frecuentes
- **¿Puedo usar la misma en dos programas?** Puedes, pero entonces al perder uno tienes que
  reconfigurar el otro. Mejor una por programa.
- **¿Sirve para entrar al webmail?** No. El webmail y la app van con tu contraseña principal y el
  segundo factor.
- **Outlook me dice «contraseña incorrecta» con la principal.** Es lo esperado cuando la política
  está activa: crea una contraseña de aplicación y úsala ahí.

## Para tecnología
Detalles, política (`auth_politica`), verificación en Dovecot y diagnóstico en `OPERACION.md`,
sección «Contraseñas de aplicación».
