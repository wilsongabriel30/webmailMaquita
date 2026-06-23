# Política de Seguridad

> **Versión:** 2.0
> **Última actualización:** 2026-05-13
> **Responsable:** Fundación Maquita — Equipo de Tecnología

## Versiones con Soporte

| Versión | Con soporte |
|---------|-------------|
| 1.0.x   | Sí          |
| < 1.0   | No          |

## Reporte de Vulnerabilidades

**NO abras un issue público en GitHub para reportar vulnerabilidades de seguridad.**

En su lugar, reporta las vulnerabilidades por correo electrónico:

- **Correo:** security@maquita.org
- **Asunto:** `[SECURITY] Descripción breve`
- **Cifrado PGP:** Solicita nuestra clave pública a través de la misma dirección de correo

### Qué incluir

- Descripción de la vulnerabilidad y su impacto potencial
- Pasos para reproducirla (versiones, configuraciones, payloads)
- Código de prueba de concepto (solo no destructivo)
- Tu nombre e información de contacto (para crédito, si lo deseas)

### Tiempos de respuesta

| Etapa | Plazo objetivo |
|-------|----------------|
| Acuse de recibo del reporte | 48 horas |
| Triage inicial y evaluación de severidad | 5 días hábiles |
| Actualización de estado al reportante | 10 días hábiles |
| Parche para severidad crítica/alta | 15 días hábiles |
| Parche para severidad media/baja | 30 días hábiles |
| Divulgación pública coordinada | 90 días tras el reporte, o al publicar el parche |

### Términos de divulgación responsable

- No iniciaremos acciones legales contra investigadores que sigan esta política.
- No accedas, modifiques ni elimines datos de otros usuarios.
- No degradues la disponibilidad del servicio durante las pruebas.
- Acreditaremos a los reportantes en las notas de versión, salvo que se solicite anonimato.

## Alcance

### Dentro del alcance

- La aplicación frontend del webmail
- La API del backend (FastAPI)
- Autenticación y gestión de sesiones (JWT, 2FA/TOTP)
- Módulo de compliance (eDiscovery, retenciones legales, trazabilidad de auditoría)
- Pipeline de procesamiento de correo (integración con Postfix, Dovecot, Rspamd)
- Integración CalDAV/CardDAV (Radicale)
- Imágenes Docker y configuraciones de despliegue
- Flujos de CI/CD

### Fuera del alcance

- Errores en software de terceros (repórtalos directamente al proveedor)
- Ataques de ingeniería social
- Seguridad física de la infraestructura de alojamiento
- Ataques de denegación de servicio que requieran ancho de banda significativo
- Problemas en dependencias (repórtalos al mantenedor de la dependencia)

## Qué NO reportar mediante issues públicos

- Evasión de autenticación o exposición de credenciales
- Vulnerabilidades de inyección (SQL, comandos, plantillas)
- Rutas de escalación de privilegios
- Vectores de exposición o exfiltración de datos
- Debilidades criptográficas
- Cualquier problema que pueda ser explotado antes de que haya un parche disponible

Estos deben enviarse por el canal de reporte privado indicado arriba.

## Resumen de la arquitectura de seguridad

- **Autenticación:** Tokens JWT en cookies HttpOnly/Secure/SameSite=Strict + 2FA/TOTP opcional
- **Autorización:** Control de acceso basado en roles (RBAC) con 5 roles de compliance
- **Cifrado en reposo:** Plugin `mail_crypt` de Dovecot (secp521r1)
- **Cifrado en tránsito:** TLS 1.2+ en todas las conexiones
- **Seguridad de correo:** SPF, DKIM, DMARC (reject), MTA-STS, DANE
- **Almacenamiento de sesiones:** Redis con campos sensibles cifrados con Fernet
- **Antispam / antivirus:** Rspamd como **milter** (scoring propio) + **ClamAV** integrado (módulo `antivirus` de Rspamd) + milter propio anti-suplantación
- **Auditoría:** 39 eventos auditados, registro de auditoría de solo anexo
- **Integridad de evidencia:** Firmas GPG separadas + sellado de marca de tiempo
- **Endurecimiento con systemd:** ProtectSystem=strict, PrivateTmp, MemoryMax, TasksMax

> **Nota para técnicos acostumbrados a amavis / SpamAssassin.** Este sistema **no
> usa amavis ni SpamAssassin**. Rspamd reemplaza a ambos en un único demonio
> moderno (Hyperscan + LuaJIT) y filtra por **protocolo milter** —inline en la
> sesión SMTP (`smtpd_milters`)— en lugar del `content_filter` por re-inyección
> que usa amavis (más lento). Equivalencias para ubicarte:
>
> | Mundo amavis (clásico) | Aquí (Rspamd) |
> |---|---|
> | `amavisd-new` (pegamento `content_filter`) | **Rspamd milter** en `localhost:11332` |
> | SpamAssassin (reglas + Bayes) | **Rspamd**: reglas Lua, red neuronal, RBL/SURBL, greylisting, phishing |
> | `clamd` invocado por amavis | **ClamAV** invocado por el módulo `antivirus` de Rspamd |
> | opendkim / firma vía amavis | firma nativa de Rspamd (`dkim_signing`, `arc`) |
>
> **ClamAV no desapareció:** sigue corriendo, solo que ahora lo llama Rspamd y no
> amavis. Hay además un milter propio (`milter/maquita_milter.py`, puerto 11335)
> para anti-suplantación/políticas y un `content_filter` propio con heurísticas
> extra. Si buscas amavis en el servidor no lo vas a encontrar: es intencional.

## Funciones de seguridad de GitHub

Recomendamos habilitar lo siguiente en tu fork o despliegue:

- **Escaneo de secretos:** Detecta credenciales comprometidas en todo el historial
- **Dependabot:** PRs automáticos de actualización de dependencias
- **Escaneo de código:** CodeQL u otra herramienta SAST similar
- **Avisos de seguridad:** Para divulgación coordinada de vulnerabilidades

## Limitaciones conocidas

Consulta [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) para el modelo de amenazas completo, incluyendo riesgos residuales y límites del sistema.

Limitaciones principales:
- La rotación de tokens de actualización JWT está implementada (los tokens antiguos se revocan al renovar); sin embargo, la revocación no se propaga a los tokens de acceso ya emitidos hasta que expiran
- Los perfiles de AppArmor/SELinux aún no están desplegados
- El módulo de compliance requiere acceso `sudo doveadm` para operaciones de eDiscovery
- El saneamiento de correo HTML depende de DOMPurify (carrera continua contra técnicas de evasión)

---

*Esta política sigue las directrices de la documentación de políticas de seguridad de GitHub y las Mejores Prácticas de OpenSSF.*
