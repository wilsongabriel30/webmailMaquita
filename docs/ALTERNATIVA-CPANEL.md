# Alternativa libre a cPanel

**[English](CPANEL-ALTERNATIVE.md) | Español**

Maquita convierte un servidor Debian en un **servidor de hospedaje completo**: correo, sitios web, bases de
datos, DNS, certificados y copias de seguridad, con un **panel para quien administra el servidor** y un
**portal para cada cliente**. Es software libre (AGPL-3.0), sin licencias por cuenta ni por dominio, y corre en
tus propios servidores.

Pensado para organizaciones, cooperativas, gobiernos locales y proveedores pequeños que quieren dejar de
pagar paneles y nubes extranjeras sin perder funciones.

---

## Dos paneles, como en cPanel/WHM

| | Panel general (puerto 8443) | Portal del cliente (puerto 8444) |
|---|---|---|
| **Para quién** | Quien administra el servidor (equivalente a WHM) | Cada organización o cliente (equivalente a cPanel) |
| **Alcance** | Todo el servidor | Solo sus dominios, dentro de sus cuotas |
| **Seguridad** | Doble autenticación y segundo factor | Segundo factor; sin privilegios: cada orden la valida un intermediario que vuelve a comprobar la sesión y el dominio |

## Funciones

✅ disponible · ⏳ en camino (versión indicada)

### Archivos

| Función | Estado |
|---|---|
| Administrador de archivos web (subir, descargar, mover, copiar, comprimir, descomprimir, permisos, papelera de 30 días) | ✅ |
| Cuentas FTP/SFTP: una por sitio y cuentas adicionales encerradas en una subcarpeta | ✅ |
| Uso de disco por sitio, bases y copias, con cuotas por dominio | ✅ |
| Carpetas con contraseña | ✅ |
| Copias de seguridad: el cliente crea, descarga y restaura su sitio y sus bases | ✅ |
| Despliegue desde git | ✅ aplicaciones propias · ⏳ sitios PHP (v1.11) |

### Dominios y DNS

| Función | Estado |
|---|---|
| Dominios, subdominios y alias de dominio | ✅ (alias desde el portal: ⏳ v1.11) |
| Redirecciones 301/302 de una ruta o de todo el dominio | ✅ |
| Editor de zona DNS (servidor DNS propio), con los registros del correo protegidos | ✅ |
| DNS dinámico | ⏳ v1.11 |

### Correo

| Función | Estado |
|---|---|
| Cuentas, webmail tipo Outlook, reenvíos y respuestas automáticas | ✅ |
| Filtros (Sieve) y antispam con aprendizaje (Rspamd) | ✅ |
| SPF, DKIM, DMARC y MTA-STS | ✅ |
| Listas y grupos de distribución | ✅ |
| Celulares por ActiveSync 16.1 (correo, calendario, contactos, borradores y libreta de la organización) | ✅ |
| Importar cuentas desde un archivo CSV | ✅ panel y portal ([guía](IMPORTAR-CSV-Y-ENRUTAMIENTO.md)) |
| Enrutamiento de correo (MX de respaldo, reenvío a otro servidor) | ✅ panel general ([guía](IMPORTAR-CSV-Y-ENRUTAMIENTO.md)) |

### Bases de datos

| Función | Estado |
|---|---|
| MariaDB y PostgreSQL, con asistente | ✅ |
| phpMyAdmin y Adminer con entrada directa desde el panel | ✅ |
| Usuarios de base con permisos a medida | ⏳ v1.11 |
| Acceso remoto a bases (por IP y con TLS) | ⏳ v1.11 |

### Seguridad

| Función | Estado |
|---|---|
| Certificados Let's Encrypt automáticos y renovación | ✅ |
| Bloqueo de IP del servidor (cortafuegos, fail2ban, países) y por sitio | ✅ |
| Protección contra hotlinking | ✅ |
| Protección contra ataques de contraseña y segundo factor | ✅ |
| Cortafuegos de aplicaciones web (reglas OWASP) | Parcial: reglas para WordPress · ⏳ v1.11 |
| Claves SSH y fichas de API | ⏳ v1.11 |

### Software

| Función | Estado |
|---|---|
| Versiones de PHP por sitio y sus ajustes | ✅ |
| Catálogo de aplicaciones (WordPress, Joomla, Drupal, Moodle y más) | ✅ |
| WordPress: instalar, entrar con un clic, actualizar núcleo, complementos, temas e idioma | ✅ |
| Tareas programadas (cron) | ✅ |
| Páginas de error propias (403, 404, 500, 502, 503) | ✅ |
| Compresión gzip/brotli y caché, pensadas para conexiones rurales y satelitales | ✅ |
| Aplicaciones Node.js y Python | ✅ panel general · ⏳ portal (v1.11) |
| Migración desde otro hosting (paquete y respaldo .sql) | ✅ |
| Editor visual de páginas | Fase posterior: alternativa libre (GrapesJS); Sitejet es de pago y no entra |

### Métricas y monitoreo

| Función | Estado |
|---|---|
| Estadísticas de visitas y ancho de banda (GoAccess, sin rastreo en el navegador) | ✅ |
| Visor de errores y accesos del sitio y de PHP | ✅ |
| Aviso de caída del sitio por correo (comprobación cada 5 minutos, con días restantes del certificado) | ✅ |
| CPU y memoria por sitio | ⏳ v1.11 |
| Información del servidor en el portal | ⏳ v1.11 |

## Lo que cPanel no trae

- **Webmail tipo Outlook** con seguridad de nivel Microsoft 365 E5: DLP, eDiscovery, retención legal, anti-suplantación.
- **Chat, calendario, tareas y Drive** (Almacén) en el mismo servidor.
- **Servidor DNS propio** y certificados automáticos para todos los nombres del correo y de los sitios.
- **Actualizaciones firmadas**: cada servidor solo instala versiones con la firma del proyecto, desde el panel o solas cada noche.
- **Sitios para conexiones lentas**: compresión y caché de serie para ADSL rural y satélite.
- **Sin costo por cuenta**: el precio no crece con cada dominio, buzón o sitio.

## Instalación

En un Debian 13 limpio (o Debian 12 / Ubuntu 22.04+), como root:

```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita
sudo bash deploy/webmail/instalar.sh                     # correo, webmail y panel general
sudo bash deploy/webmail/instalar-app.sh sitios          # sitios web, bases y aplicaciones
sudo bash deploy/webmail/instalar-app.sh dns             # servidor DNS propio
sudo bash deploy/webmail/instalar-app.sh portal-dominio  # portal del cliente (puerto 8444)
sudo bash deploy/webmail/instalar-app.sh actualizar      # actualizaciones firmadas
```

Otras secciones opcionales: `activesync`, `cortafuegos`, `identidad`, `respaldos`, `chat`, `bi`, `pdf`, `onlyoffice`.
La guía completa está en [INSTALL-NATIVE.md](INSTALL-NATIVE.md) y la configuración del DNS, paso a paso, en
[CONFIGURAR-DNS.md](CONFIGURAR-DNS.md).

**Requisitos orientativos:** 4 núcleos, 8 GB de RAM y 80 GB de disco para una organización mediana con
sus sitios; una IP pública con el puerto 25 abierto para recibir correo.

## Versiones y hoja de ruta

Las notas de cada versión están en [Releases](https://github.com/wilsongabriel30/webmailMaquita/releases) y en
[CHANGELOG.md](../CHANGELOG.md); lo que viene, en [ROADMAP.md](../ROADMAP.md).
