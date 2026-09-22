# Teléfonos institucionales: qué significa cada color y qué hacer ante cada alerta

Guía para personas **no técnicas** (dirección, administración). Escrita el 22/09/2026 para el portal
de telemetría del panel de administración del correo: `https://mail.maquita.org:8443/dispositivos`
(solo desde la red de la oficina o la VPN), pestañas **«Telemetría»** y **«Alertas»**.

El portal muestra el estado **del teléfono como equipo** (si reporta, batería, espacio, versión de la
app, si sigue protegido). **No muestra** mensajes, fotos, llamadas, apps que usa la persona ni por
dónde navega. La ubicación tampoco está aquí: solo se consulta desde la ficha del equipo, con motivo,
si la persona firmó la política o si el equipo se declaró perdido.

## 1. Los colores de «Último contacto»

| Color | Significa | Qué hacer |
|---|---|---|
| 🟢 Verde | El teléfono reportó hace menos de 1 hora. | Nada. Todo en orden. |
| 🟡 Amarillo | Reportó hace entre 1 y 24 horas. | Normal si el teléfono estuvo apagado, sin señal o de viaje. Si es de lunes a viernes en horario de oficina, preguntar a la persona si el teléfono está encendido y con internet. |
| 🔴 Rojo | No reporta desde hace más de 24 horas, o nunca reportó. | Ver el punto «Sin reportar» más abajo. Si el rojo dura más de 3 días sin explicación, tratarlo como posible pérdida. |

Otros avisos en la tabla: la **versión de la app en color ámbar con ↓** significa que el teléfono
tiene una app más vieja que la publicada (se actualiza sola al abrirla con internet); **«NO»** en
Admin. o **«APAGADO»** en Play Protect en rojo significa que quitaron una protección.

## 2. Qué hacer ante cada alerta

Las alertas llegan **solas por correo** a Tecnología (y, si está configurado, un resumen diario a
dirección a la hora indicada). Cada alerta se avisa **una sola vez**; se cierra sola cuando el equipo
vuelve a la normalidad. No hace falta «revisar» nada para que se cierre, salvo los eventos de seguridad.

| Alerta | Qué pasa | Qué hacer | A quién llamar |
|---|---|---|---|
| **Sin reportar** (más de 24 h) | El teléfono no se comunica: apagado, sin internet, sin batería, o la app fue desinstalada. | 1) Llamar a la persona: ¿tiene el teléfono, está encendido, tiene datos o wifi? 2) Si lo tiene: pedirle que abra la app Maquita Mail con internet; en minutos pasa a verde. 3) Si no sabe dónde está: **declararlo perdido** desde la ficha del equipo (pestaña «Equipos» → abrir el equipo → «Pérdida o robo»). | Custodio del equipo; si no responde en el día, su jefe directo. |
| **Batería baja sostenida** | Menos de 15 % durante más de 6 horas sin cargar. Suele anunciar un teléfono olvidado o un cargador roto. | Avisar a la persona que lo cargue. Si se repite cada semana, revisar el cargador o la batería (equipos de más de 3 años). | Custodio. |
| **Almacenamiento casi lleno** | Menos del 10 % de espacio libre: la app puede dejar de guardar correos y el respaldo nocturno falla. | Pedir a la persona que borre videos y descargas, y que revise WhatsApp (Ajustes → Almacenamiento). El respaldo nocturno ya guarda sus fotos en el servidor: puede borrarlas del teléfono con confianza si el respaldo de anoche salió completo (pestaña «Equipos» → ficha → Respaldos). | Custodio; Tecnología si no logra liberar espacio. |
| **App desactualizada** (más de 7 días) | El teléfono no tomó la actualización automática: lleva más de una semana con una versión vieja. | Pedir a la persona que abra la app con wifi y acepte la actualización cuando se la ofrezca. Si no aparece, que entre al correo web y use «Descargar app para Android». | Custodio; Tecnología si sigue sin actualizar. |
| **Quitaron a la app como administradora** | Alguien entró a los ajustes del teléfono y quitó ese permiso. Es el paso previo para desinstalar la app. | Llamar a la persona ese mismo día y preguntar por qué. Si fue sin querer: que vuelva a activarlo (la app se lo pide al abrirla). Si fue a propósito y el teléfono es institucional, informar a su jefe. En el panel, marcar el evento como «revisado» en la ficha del equipo: eso cierra la alerta. | Custodio y su jefe. |
| **Intento de desinstalar la app** | La persona (o quien tenga el teléfono) intentó borrar la app de gestión. | Igual que la anterior. Si el teléfono además dejó de reportar, tratarlo como pérdida o como retiro indebido del equipo. | Custodio, jefe, Tecnología. |
| **Cambio de SIM** | El teléfono arrancó con otra tarjeta SIM. Puede ser un cambio de plan… o un robo. | Confirmar con la persona el mismo día. Si no fue ella, **declarar perdido** de inmediato. Marcar revisado cuando esté aclarado. | Custodio; Tecnología. |
| **Play Protect apagado** | Se apagó la protección de Google contra apps maliciosas. | Pedir a la persona que lo encienda: Play Store → su foto → Play Protect → activar. | Custodio. |
| **Mensaje urgente sin acuse** (más de 2 h) | Se mandó un mensaje urgente y la persona no tocó «Leído». | Si el teléfono está en verde, la persona no lo ha visto: llamarla. Si está en rojo, no le ha llegado: ver «Sin reportar». | Custodio. |

## 3. Cuándo declarar un equipo perdido
- La persona dice que no lo encuentra, o hubo robo, o nadie sabe de él **y** el equipo lleva más de
  un día en rojo, o hubo cambio de SIM que la persona no reconoce.
- Se hace desde la pestaña «Equipos» → abrir el equipo → «Pérdida o robo», escribiendo el motivo. El
  teléfono pasa a reportar cada 5 minutos con su posición; si tiene control completo, se bloquea con un
  mensaje y un teléfono de contacto en pantalla. Los demás teléfonos de la organización avisan si lo
  detectan cerca. Esto solo lo hace un administrador (no el rol lector).
- Si aparece, se le quita el modo perdido desde la misma ficha.
- **Bloqueo en la operadora:** en la ficha del equipo, el recuadro «IMEI para la operadora» tiene los
  números (2 a 4 en teléfonos con doble SIM o eSIM) y un botón Copiar. La persona también los ve en su
  correo web → «Mi teléfono». Con ellos, la operadora (CNT, Claro, Movistar) bloquea el teléfono aunque
  le cambien la SIM. Si el recuadro está vacío, pedir a la persona que los registre desde su correo
  (*#06# o la caja) o cargarlos en «Todos los IMEI» de la ficha.

## 3b. La ubicación de un celular es SIEMPRE aproximada
Cuando el panel muestra una posición (ficha del equipo → Ubicación), encima del mapa aparece un aviso
con el **margen de error** y enlaces «Ver en mapa» (OpenStreetMap, Google Maps, Google Earth). Léalo
antes de actuar: el equipo puede estar en **cualquier punto del círculo**, no en el punto exacto.
- Verde (margen de hasta 30 m): GPS al aire libre; aun así, revise la zona completa.
- Ámbar (hasta 200 m): wifi o GPS bajo techo; es una manzana, no una casa.
- Rojo (más de 200 m, a veces kilómetros): por antena de celular; solo indica el sector.
- Morado: otro teléfono de la organización lo detectó cerca por Bluetooth.
- Azul: el teléfono está conectado a la red de una sede de Maquita (ancla de red): está en esa sede, con el margen indicado. Las sedes fuera de Quito tienen coordenadas provisionales (3 km) hasta que Tecnología cargue la ubicación exacta de cada oficina.
La posición solo se vuelve más fiable cuando **varios teléfonos** de la organización lo detectan
(avistamientos por Bluetooth, que se activan al declarar el equipo perdido) y sus zonas coinciden.
Nunca dé por exacta una posición para acusar a alguien o entrar a un domicilio.

## 4. Cuándo pedir el respaldo de cierre
Antes de **reasignar** un teléfono a otra persona, de **restablecerlo de fábrica** o de darlo de
**baja**: pestaña «Equipos» → ficha → Respaldos → «Pedir respaldo de cierre». Esperar a que salga
«completo» (la app lo hace con wifi y cargando). Con eso, las fotos, contactos y WhatsApp de la
persona quedan guardados cifrados en el servidor y se pueden restaurar en el teléfono nuevo con
autorización de Tecnología.

## 5. Dar acceso de solo lectura a alguien de dirección
1. Un superadministrador entra al panel → **Administradores** → «Nuevo administrador».
2. Rol: **viewer** (lector). Con ese rol la persona ve todo (equipos, telemetría, alertas, gráficas,
   exportar CSV) pero **no puede** mandar comandos, declarar perdidos, retirar equipos, crear códigos
   ni cambiar umbrales. El panel responde «Tu rol es de solo lectura» si lo intenta.
3. La persona entra a `https://mail.maquita.org:8443` desde la red de la oficina o la VPN y activa su
   verificación en dos pasos (el panel se lo pide).
4. Para que le llegue el **resumen diario por correo**: pestaña «Alertas» → «Umbrales y
   destinatarios» → «Resumen diario a» (un administrador escribe su correo y la hora).

## 6. Exportar y privacidad
- «Exportar CSV» en la pestaña «Telemetría» descarga la tabla de la flota para Excel. Cada
  exportación queda registrada en la auditoría del panel con quién la hizo.
- La información del teléfono no sale del panel por ningún otro camino. Los datos de cada reporte se
  guardan 30 días; el resumen diario por equipo (batería, espacio, versión) se conserva 12 meses.

## 7. Si el portal no muestra nada nuevo o no llegan alertas
- Si **todos** los equipos pasan a rojo a la vez, el problema es del servidor o del internet de la
  oficina, no de los teléfonos: avisar a Tecnología.
- Si no llegan correos de alerta en una semana, aunque haya equipos en rojo: en la pestaña «Alertas»
  revisar que «Alertas activas» esté marcado y que el correo de Tecnología sea correcto. Si sigue
  igual, Tecnología revisa el trabajo programado (`maquita-disp-alertas.timer`, ver OPERACION.md).
