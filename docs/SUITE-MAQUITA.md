# La suite Maquita

**Un ecosistema corporativo libre y soberano — todo en servidores propios.**

Maquita no es solo un correo: es una plataforma completa de trabajo que una
organización puede alojar por su cuenta. Correo, colaboración, gestión, datos e
inteligencia artificial funcionan **en casa**, sobre software libre, sin enviar la
información a terceros y sin pagar una licencia por cada persona.

Este documento describe **qué es cada pieza, qué hace y para qué sirve**. El webmail
de este repositorio es una de ellas; el resto forma el ecosistema del que nace.

> **Por qué existe.** Nació de una necesidad real de la Fundación Maquita (Ecuador):
> tener herramientas de trabajo modernas sin depender de servicios externos, cuidando
> el presupuesto y manteniendo el control y la privacidad de los datos propios y de
> las comunidades con las que se trabaja.

---

## 1. Correo y su seguridad

- **Webmail seguro** — *Qué es:* un correo con interfaz web moderna (carpetas,
  conversaciones, búsqueda, calendario y contactos). *Qué hace:* enviar y recibir
  correo con cifrado en tránsito y en reposo. *Para qué sirve:* la comunicación
  diaria de la organización, sin depender de una casilla externa.
- **Autenticación del remitente (SPF, DKIM, DMARC)** — *Qué hace:* firma y valida
  cada correo para probar que salió de verdad del dominio. *Para qué sirve:* que
  nadie envíe correos falsos en nombre de la institución.
- **Antispam y antivirus** — *Qué hace:* filtra spam y analiza adjuntos y enlaces
  peligrosos. *Para qué sirve:* mantener limpias las bandejas y frenar el malware.
- **Anti-suplantación dirigida** — *Qué hace:* detecta correos externos que se hacen
  pasar por la institución o por un área interna (contabilidad, talento humano,
  soporte, gerencia) en el nombre visible. *Para qué sirve:* frenar el fraude típico
  de la "factura pendiente" o el "pago urgente" pedido por un falso jefe.
- **Prevención de fuga de datos (DLP)** — *Qué hace:* revisa el correo saliente y sus
  adjuntos en busca de datos sensibles (cédula, RUC, cuentas, tarjetas) y bloquea o
  avisa. *Para qué sirve:* evitar que información delicada salga por error o descuido.
- **Etiquetas de sensibilidad** — *Qué hace:* marca cada correo como Público, Interno,
  Confidencial o Restringido, y bloquea la salida a externos de los dos más altos.
  *Para qué sirve:* que cada quien clasifique lo que envía y lo confidencial no se
  escape fuera de la organización.
- **Cifrado de mensajes (portal seguro)** — *Qué hace:* entrega los correos más
  sensibles a través de un portal cifrado. *Para qué sirve:* proteger comunicaciones
  que no deberían viajar en claro.
- **eDiscovery y cumplimiento** — *Qué hace:* busca en todos los buzones por fecha,
  remitente o palabra clave, congela buzones bajo investigación y exporta con firma y
  sello de tiempo. *Para qué sirve:* responder a auditorías o requerimientos legales
  con trazabilidad.
- **Acceso a buzones para soporte, auditado** — *Qué hace:* permite a TI abrir un
  buzón cuando una jefatura lo solicita, dejando registro de quién, qué, cuándo y
  desde dónde. *Para qué sirve:* dar soporte con responsabilidad y sin claves
  compartidas.

## 2. Colaboración

- **Almacén (Drive Maquita)** — *Qué es:* un disco en la nube propio con carpetas,
  compartir por enlace, papelera, versiones, búsqueda de contenido y auditoría.
  *Qué hace:* guardar y compartir archivos, y editar documentos de oficina
  (Word/Excel/PowerPoint) en el navegador con **OnlyOffice** integrado. *Para qué
  sirve:* el archivo compartido de la organización, sin límite por casilla.
- **Formularios** — *Qué es:* un creador de formularios y encuestas dentro del Drive.
  *Qué hace:* publicar un enlace, recoger respuestas y exportarlas a una hoja de
  cálculo. *Para qué sirve:* levantar información (inscripciones, encuestas, campo)
  sin herramientas externas.
- **Chat institucional** — *Qué es:* mensajería en tiempo real, con aplicación para
  Windows además del navegador. *Qué hace:* conversaciones y grupos con notificaciones.
  *Para qué sirve:* la coordinación rápida del día a día.
- **Reuniones (Meet)** — *Qué es:* videollamadas por el navegador. *Qué hace:*
  reuniones con audio, video, pantalla compartida y **grabación**. *Para qué sirve:*
  reunirse con equipos y comunidades sin instalar nada ni pagar por sala.
- **Calendario, contactos y tareas** — *Qué hacen:* agenda compartida, libreta de
  contactos y tableros de tareas estilo Kanban. *Para qué sirven:* organizar el
  trabajo y las citas del equipo.

## 3. Gestión y administración (Raíces)

Raíces es la plataforma de gestión de la organización. Cubre procesos que un correo
no resuelve:

- **Nómina y talento humano** — pago de sueldos, vacaciones, evaluaciones y legajos.
- **Finanzas y contabilidad** — balances, flujo de caja, cuentas por pagar, activos
  fijos.
- **Mesa de ayuda (helpdesk)** — tickets de soporte y bitácora de servidores.
- **Abastecimiento y trazabilidad** — compras y seguimiento de productos.
- **Reclamos y gestión social** — atención de casos, proyectos y cooperación.

*Para qué sirve:* llevar la administración de la organización en la misma casa donde
vive el correo y los archivos, con los mismos usuarios y la misma identidad.

## 4. Datos e inteligencia

- **Tableros e informes (BI)** — *Qué hace:* convierte los datos de la organización en
  tableros y gráficos. *Para qué sirve:* tomar decisiones con información al día.
- **Inteligencia artificial local** — *Qué es:* un asistente de IA que corre en los
  servidores propios. *Qué hace:* sugiere respuestas, redacta y resume. *Para qué
  sirve:* ayudar a escribir **sin que el contenido salga a un tercero** — el dato se
  queda en casa.
- **Formularios de campo (ODK)** — *Qué hace:* recoge datos en terreno, incluso sin
  conexión. *Para qué sirve:* levantar información de proyectos y comunidades.
- **Editor de PDF** — *Qué hace:* anota, firma, rellena formularios y genera/lee
  códigos QR. *Para qué sirve:* trabajar documentos sin software de escritorio.
- **Transcripciones** — *Qué hace:* pasa audio a texto. *Para qué sirve:* dejar por
  escrito reuniones y entrevistas.

## 5. Identidad, red y seguridad

- **Inicio de sesión único (SSO)** — *Qué hace:* una sola cuenta para varias
  herramientas. *Para qué sirve:* menos contraseñas y acceso ordenado.
- **Segundo factor (MFA)** — *Qué hace:* pide un código además de la contraseña.
  *Para qué sirve:* que una clave robada no baste para entrar.
- **VPN y acceso remoto (WireGuard)** — *Qué hace:* conecta sedes y personas de forma
  cifrada. *Para qué sirve:* trabajar a distancia con seguridad.
- **Cortafuegos perimetral y filtrado** — *Qué hace:* bloquea atacantes conocidos con
  un listado de amenazas propio y filtra la red y el DNS. *Para qué sirve:* frenar el
  ataque antes de que llegue a los servicios.
- **Monitoreo de seguridad (SIEM)** — *Qué hace:* vigila los servidores y alerta ante
  actividad sospechosa. *Para qué sirve:* enterarse a tiempo de un incidente.

## 6. Infraestructura

- **Servidores propios (virtualización)** — todo corre sobre máquinas de la
  organización, no en la nube de un tercero.
- **Respaldos y certificados** — copias de seguridad y cifrado (HTTPS) gestionados en
  casa, con renovación automática.
- **DNS propio** — el directorio de nombres de la organización, bajo control interno.

---

## En una frase

La suite Maquita reúne, sobre **software libre y servidores propios**, casi todo lo
que una organización necesita para trabajar: comunicarse, colaborar, gestionarse,
analizar sus datos y apoyarse en IA — **con el dato siempre en casa** y **sin pagar
una licencia por cada persona**. Está hecha por y para una fundación, y se comparte
para que otras comunidades y organizaciones puedan hacer lo mismo.

## Con honestidad

Hoy cubre el **puesto de trabajo colaborativo completo** —correo, ofimática en línea,
archivos en la nube, chat, videollamadas, calendario, formularios e IA— y además
**suma la gestión (ERP): nómina, finanzas, RR.HH. y más**, algo que las suites
comerciales de oficina no traen. Para una organización, **el día a día ya se puede
vivir enteramente aquí**.

Lo que todavía falta para cubrirlo *todo* —y lo decimos sin adornos—:

- **Gestión centralizada de equipos y dispositivos** (portátiles y móviles: políticas,
  inventario, borrado remoto).
- **Telefonía** (llamadas a números de teléfono convencionales).
- **Escala muy grande**: está probada con cientos de usuarios, no con decenas de miles
  concurrentes.

En resumen: para el trabajo colaborativo, **ya es una alternativa completa y soberana**;
para el puesto de trabajo *entero* (incluidos los dispositivos), **está muy cerca**.
