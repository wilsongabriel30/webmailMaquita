# La suite Maquita

**Correo, Drive y aplicaciones de trabajo — autoalojado y libre.**

Este repositorio es una **plataforma de trabajo que se aloja en servidores propios**:
un correo seguro y un **Drive propio (Almacén)** con sus aplicaciones —documentos,
formularios y más—, junto con la colaboración del día a día (chat, calendario,
tareas). Todo sobre **software libre**, con el dato **en casa** y **sin pagar una
licencia por cada persona**.

Este documento describe **qué es cada pieza, qué hace y para qué sirve**.

> **Alcance de este repositorio.** Aquí publicamos el **correo** y el **Drive Maquita
> con sus aplicaciones**. Fundación Maquita opera además una plataforma de gestión
> (ERP: nómina, finanzas, RR. HH. y más) que **no forma parte de este repositorio**.

---

## 1. Correo y su seguridad

- **Webmail seguro** — *Qué es:* un correo con interfaz web moderna (carpetas,
  conversaciones, búsqueda, calendario y contactos). *Qué hace:* enviar y recibir
  correo con cifrado en tránsito y en reposo. *Para qué sirve:* la comunicación
  diaria de la organización, sin depender de una casilla externa.
- **Autenticación del remitente (SPF, DKIM, DMARC)** — prueba que cada correo salió
  de verdad del dominio; frena los correos falsos en nombre de la institución.
- **Antispam y antivirus** — filtra spam y analiza adjuntos y enlaces peligrosos.
- **Anti-suplantación dirigida** — detecta correos externos que se hacen pasar por la
  institución o por un área interna (contabilidad, talento humano, soporte, gerencia)
  en el nombre visible; frena el fraude de la "factura pendiente" o el "pago urgente".
- **Prevención de fuga de datos (DLP)** — revisa el correo saliente y sus adjuntos en
  busca de datos sensibles (cédula, RUC, cuentas, tarjetas) y bloquea o avisa.
- **Etiquetas de sensibilidad** — marca cada correo como Público, Interno,
  Confidencial o Restringido, y bloquea la salida a externos de los dos más altos.
- **Cifrado de mensajes (portal seguro)** — entrega los correos más sensibles por un
  portal cifrado.
- **eDiscovery y cumplimiento** — búsqueda forense en todos los buzones, retenciones
  legales, exportación firmada con sello de tiempo; para auditorías y requerimientos.
- **Acceso a buzones para soporte, auditado** — TI puede abrir un buzón bajo
  solicitud, con registro de quién, qué, cuándo y desde dónde.
- **Adjuntos grandes en el Drive** — los archivos que superan el límite se suben al
  Drive Maquita y se envían como enlace de descarga, no como adjunto pesado.

## 2. El Drive Maquita (Almacén)

*Qué es:* un disco en la nube **propio** —el equivalente a un Drive comercial, pero en
casa. *Qué hace:* guardar, organizar y compartir archivos. *Para qué sirve:* el
archivo compartido de la organización, sin límite por casilla.

- Unidades y carpetas, con permisos.
- Compartir por enlace público (con clave y caducidad opcionales) o con personas.
- Papelera, **versiones**, búsqueda por contenido y **auditoría** de accesos.
- Aplicación de escritorio para sincronizar como una carpeta más del equipo.

## 3. Las Aplicaciones del Drive Maquita

Las **Aplicaciones del Drive Maquita** son herramientas que **se abren desde el Drive**
y trabajan sus archivos —igual que un documento se abre desde el Drive. Cada archivo
hereda gratis los permisos, el compartir, la papelera, las versiones y la búsqueda
del Drive.

- **Documentos (OnlyOffice)** — *disponible.* Edita Word/Excel/PowerPoint en el
  navegador, en línea y en colaboración, sobre los archivos del Drive.
- **Formularios** — *disponible.* Crea formularios y encuestas (estilo Google Forms);
  el formulario es un archivo más del Drive. Publica un enlace, recoge respuestas y
  las exporta a una hoja de cálculo en la misma carpeta.
- **Tableros / BI** — *en preparación* (motor ya en `almacen/aplicaciones/bi/`). Convierte
  datos en tableros y gráficos, abriéndolos desde el Drive.
- **Editor de PDF** — *instalable* (app autónoma en `almacen/aplicaciones/pdf_editor/`).
  Anota, firma, rellena formularios y genera o lee códigos QR, sobre PDF del Drive.

> Las aplicaciones marcadas *en preparación* ya funcionan dentro de Maquita; se están
> empaquetando para que cualquiera pueda instalarlas y abrirlas desde su propio Drive.

## 4. Colaboración incluida

Viene con el webmail, en el mismo repositorio:

- **Chat institucional** — mensajería en tiempo real, con aplicación para Windows.
- **Calendario y contactos** — agenda y libreta compartidas.
- **Tareas** — tableros estilo Kanban.
- **Reuniones** — el webmail integra videollamadas; el servidor de video (Jitsi) se
  aloja aparte y es opcional.

## 5. Identidad y acceso

- **Segundo factor (MFA)** — pide un código además de la contraseña; una clave robada
  no basta para entrar.
- **Inicio de sesión único (SSO)** — se integra con un Keycloak corporativo para tener
  una sola cuenta entre las herramientas.

---

## En una frase

Este repositorio ofrece, sobre **software libre y servidores propios**, el **correo**
y un **Drive con sus aplicaciones** (documentos, formularios y más), más la
colaboración del día a día —**con el dato en casa** y **sin licencia por usuario**.
Está hecho por y para una fundación, y se comparte para que otras comunidades y
organizaciones puedan hacer lo mismo.

## Con honestidad

Para el **trabajo colaborativo** —correo, ofimática en línea, archivos, chat,
calendario y tareas— es ya una **alternativa completa y soberana** a una suite de
oficina comercial. Lo que este repositorio **no** incluye (y lo decimos sin adornos):

- La plataforma de **gestión (ERP)** que Maquita usa internamente.
- **Gestión centralizada de equipos y dispositivos** (portátiles y móviles).
- **Telefonía** (llamadas a números convencionales).
- **Escala muy grande**: probado con cientos de usuarios, no con decenas de miles
  concurrentes.
