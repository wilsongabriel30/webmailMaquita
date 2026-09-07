# Cómo crear tu firma de correo

Para el personal. Tu firma se guarda en el servidor y sale igual en el webmail, en Outlook, en el
celular y en el destinatario, sin que tengas que tocar nada: al guardarla, el sistema la revisa y
la deja en un formato que todos los programas de correo respetan.

## Dónde se crea
1. Webmail → **Configuración** (engranaje) → **Firmas**.
2. **Nueva firma**: ponle un nombre («Principal», «Corta»…), escribe el contenido en el editor y
   pulsa **Guardar**. Marca **Predeterminada** en la que quieras usar siempre.
3. Al redactar, la firma se añade sola al final del mensaje. Puedes cambiarla por otra desde el
   botón de firma de la barra de redacción.

Si usas varias direcciones (identidades), cada identidad puede tener su propia firma en
**Configuración → Identidades**.

## Qué poner
- **Nombre y cargo**, teléfono con extensión, correo, sitio web, dirección. Corto: la firma se lee
  en un teléfono.
- **Logo**: pégalo desde el editor (botón de imagen) o pega directamente la imagen. Cualquier
  tamaño vale: el sistema la guarda al tamaño en que la muestras (máximo 600 px de ancho) y la
  incrusta en cada correo, así se ve aunque el destinatario tenga bloqueadas las imágenes externas.
- **Enlaces**: escribe el correo tal cual (`persona@dominio`); el editor lo convierte en enlace.
  Si el enlace de correo apunta a una dirección distinta de la que se ve, al guardar te lo avisa.

## Si traes una firma de otro sistema (Zimbra, Outlook, un diseñador)
Pega el HTML en el editor y guarda. El sistema, solo:
- descarga las imágenes que estaban en internet y las guarda en el servidor al tamaño correcto
  (esto arregla los logos «gigantes» que se veían en algunos clientes);
- pone la tabla a un ancho fijo (máximo 600 px) y quita lo que Outlook no entiende;
- deja el `mailto:` coherente o te avisa.

Si una imagen no se pudo traer (la dirección ya no existe, pesa más de 2 MB o tarda más de 5 s),
la firma se guarda **sin esa imagen** y verás un aviso: vuelve a insertarla desde tu computadora.

## Cómo comprobar que se ve bien
Envíate un correo a ti mismo y ábrelo en el webmail y en el celular; si además usas Outlook,
mírala ahí. El logo debe verse del mismo tamaño en los tres. Si no, avisa a tecnología con una
captura: el problema está en el servidor, no en tu firma.

## Para tecnología
La normalización es automática al guardar (webmail, identidades y plantillas del panel) y al
enviar (bloque `email-signature` del mensaje). Detalles, migración y diagnóstico en
`OPERACION.md`, sección «Firmas».
