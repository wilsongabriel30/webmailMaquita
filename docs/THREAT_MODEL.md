# Modelo de Amenazas

Este documento describe el modelo de amenazas de Maquita Webmail, incluyendo las amenazas principales, las mitigaciones aplicadas y los riesgos residuales.

## Fronteras de Confianza

```
                            INTERNET
                               |
              +----------------+----------------+
              |          NGINX (TLS)            |
              |         (frontera de confianza) |
              +------+------------------+-------+
                     |                  |
              +------+------+   +------+------+
              |  Frontend   |   |   Backend   |
              |  (estático) |   |  (FastAPI)  |
              +-------------+   +------+------+
                                       |
                     +---------+-------+---------+
                     |         |                 |
              +------+--+  +--+------+  +-------+------+
              |PostgreSQL|  |  Redis  |  | Pila de Correo|
              |  (datos) |  |(sesión) |  | Postfix       |
              +----------+  +---------+  | Dovecot       |
                                         | Rspamd        |
                                         | ClamAV        |
                                         +------+-------+
                                                |
                                         +------+-------+
                                         | Almacenamiento|
                                         | de Correo     |
                                         | /var/vmail    |
                                         +--------------+
```

**Fronteras de confianza:**

1. **Internet → Nginx** -- el tráfico no confiable de red ingresa al sistema
2. **Nginx → Backend** -- el proxy inverso valida TLS y reenvía al aplicativo
3. **Backend → Base de datos/Redis** -- el aplicativo accede a los almacenes de datos en localhost
4. **Backend → Pila de correo** -- el aplicativo emite comandos a Dovecot/Postfix a través de sockets
5. **Pila de correo → Almacenamiento** -- Dovecot lee y escribe maildir en el sistema de archivos

## Flujo de Datos: Operaciones de Compliance

```
  Admin/Oficial                    Backend                      Dovecot
       |                             |                            |
       |-- POST /api/compliance/ --> |                            |
       |   (JWT + verificación RBAC) |                            |
       |                             |-- doveadm search --------> |
       |                             |<-- lista de mensajes ----- |
       |                             |-- doveadm fetch ---------> |
       |                             |<-- contenido del mensaje-- |
       |                             |                            |
       |                             |-- INSERT audit_log ------> PostgreSQL
       |                             |-- firma GPG exportación -> |
       |                             |                            |
       |<-- paquete exportado ------- |                            |
       |   (firmado, con checksum)   |                            |
```

## Catálogo de Amenazas

### T1: Acceso No Autorizado a Buzones

**Descripción:** Un atacante obtiene acceso al buzón de otro usuario mediante secuestro de sesión, robo de credenciales o evasión de la autenticación.

**Mitigaciones:**
- Tokens de sesión almacenados en Redis con TTL configurable
- Autenticación de dos factores basada en TOTP
- Limitación de tasa en los endpoints de autenticación
- Invalidación de sesión al cambiar la contraseña
- Atributos de cookie `HttpOnly`, `Secure`, `SameSite=Strict`
- Registro y alertas por intentos de inicio de sesión fallidos

**Riesgo residual:** Medio. Un dispositivo TOTP comprometido combinado con una contraseña obtenida por phishing podría aún otorgar acceso. Se mitiga con monitoreo de sesiones y detección de anomalías (planificado).

---

### T2: Suplantación / Spoofing de Correo

**Descripción:** Un atacante envía correos que aparentan provenir del dominio de la organización.

**Mitigaciones:**
- Registro SPF con política `-all`
- Firma DKIM a través de Rspamd para todo el correo saliente
- Política DMARC configurada en `reject`
- MTA-STS que impone TLS para las conexiones entrantes
- Registros DANE/TLSA para la seguridad del transporte

**Riesgo residual:** Bajo. Una configuración correcta de SPF/DKIM/DMARC previene la suplantación del dominio. La suplantación del nombre visible sigue siendo posible, pero es un problema del lado del cliente.

---

### T3: Exportación No Autorizada de eDiscovery

**Descripción:** Un usuario con acceso parcial exporta datos de buzones que no está autorizado a consultar, exfiltrando comunicaciones sensibles.

**Mitigaciones:**
- Aplicación de RBAC: solo los roles `compliance_officer` y `compliance_admin` pueden iniciar exportaciones
- Todas las operaciones de exportación quedan registradas en el audit trail con actor, alcance, marca temporal e IP
- Paquetes de exportación firmados con GPG y checksums SHA-256 para verificación de integridad
- Permisos del directorio de exportación restringidos al usuario del servicio de la aplicación
- Limitación de tasa en los endpoints de exportación

**Riesgo residual:** Medio. Una cuenta de oficial de compliance comprometida podría exportar datos dentro del alcance autorizado. Se mitiga con revisión del audit trail y separación de funciones.

---

### T4: Manipulación de Evidencia

**Descripción:** Un atacante modifica o elimina evidencia de compliance (logs de auditoría, datos exportados, registros de legal hold) para encubrir actividades o socavar procesos legales.

**Mitigaciones:**
- Las entradas del audit log son de solo adición (no se otorgan permisos UPDATE/DELETE sobre la tabla `audit_log`)
- Firmas GPG en todos los paquetes de exportación
- Checksums SHA-256 para los archivos exportados
- Los registros de legal hold son inmutables una vez activados (solo eliminación lógica, con entrada en el audit trail)
- Copias de seguridad de la base de datos con verificación de integridad

**Riesgo residual:** Medio. Un administrador de base de datos con acceso directo a PostgreSQL podría teóricamente modificar registros. Se mitiga con comparación de respaldos y reenvío externo de logs (planificado mediante Wazuh).

---

### T5: Eliminación de Correos Bajo Legal Hold

**Descripción:** Un usuario o proceso automatizado elimina correos sujetos a un legal hold, destruyendo evidencia potencialmente relevante.

**Mitigaciones:**
- La bandera de legal hold impide la eliminación de mensajes a nivel de Dovecot
- El backend verifica el estado del hold antes de cualquier operación de eliminación
- Los mensajes retenidos quedan excluidos de las políticas automáticas de retención y depuración
- El audit trail registra todos los intentos de eliminación, incluidos los bloqueados

**Riesgo residual:** Bajo. El acceso directo al sistema de archivos en `/var/vmail` podría eludir los controles del aplicativo. Se mitiga con permisos de sistema de archivos y monitoreo de integridad (planificado).

---

### T6: Filtración de Secretos

**Descripción:** Los secretos (claves JWT, contraseñas de base de datos, API keys) quedan expuestos a través de logs, mensajes de error, código fuente o volcados de variables de entorno.

**Mitigaciones:**
- Validación estricta al arrancar: el sistema se niega a ejecutarse con un `ADMIN_JWT_SECRET` débil o por defecto
- Los valores de secretos son eliminados de todos los logs y respuestas de error
- Permisos del archivo `.env` restringidos a `600` (solo lectura/escritura del propietario)
- `gitleaks` se ejecuta en CI para evitar que los secretos ingresen al repositorio
- Los secretos nunca se pasan como argumentos de línea de comandos (visibles en `/proc`)

**Riesgo residual:** Bajo. Los volcados de memoria o archivos core podrían teóricamente contener secretos. Se mitiga deshabilitando los core dumps en producción (`MemoryDenyWriteExecute` en systemd).

---

### T7: Manipulación de Logs

**Descripción:** Un atacante con acceso al sistema modifica o elimina logs de la aplicación o del sistema operativo para ocultar actividad maliciosa.

**Mitigaciones:**
- Los logs de la aplicación se reenvían a syslog (configurable)
- El journal de systemd captura stdout/stderr con almacenamiento resistente a manipulaciones
- El audit trail se almacena en PostgreSQL (separado de los logs en archivos)
- La rotación de logs preserva datos históricos con retención configurable

**Riesgo residual:** Alto. Un atacante con acceso root puede modificar cualquier log local. Se mitiga reenviando los logs a un sistema externo de solo adición (integración Wazuh/OpenSearch planificada para v1.3).

---

### T8: Abuso de Rol de Administrador

**Descripción:** Un administrador utiliza sus privilegios elevados para acceder a buzones, modificar datos de compliance u otorgar accesos no autorizados sin supervisión.

**Mitigaciones:**
- Todas las acciones de administración quedan registradas en el audit trail (sin operaciones silenciosas)
- RBAC separa los roles de administración: `mail_admin`, `compliance_officer`, `compliance_admin`, `system_admin`
- Las operaciones de compliance requieren roles específicos de compliance (los administradores de correo no pueden acceder a eDiscovery)
- La actividad de las sesiones de administración es visible en el panel de administración

**Riesgo residual:** Medio. Un `system_admin` con acceso a la base de datos podría eludir RBAC. Se mitiga con revisión del audit trail y separación planificada de credenciales de base de datos por rol.

---

### T9: Escalada de Privilegios mediante Doveadm

**Descripción:** La herramienta de línea de comandos `doveadm` se ejecuta con privilegios elevados y puede acceder a cualquier buzón. El compromiso del socket o las credenciales de doveadm otorga acceso completo a todos los buzones.

**Mitigaciones:**
- Permisos del socket de doveadm restringidos al usuario del servicio de la aplicación
- API HTTP de doveadm protegida con una contraseña robusta
- El backend valida la autorización antes de emitir comandos doveadm
- Todas las operaciones de doveadm quedan registradas en el audit trail
- El endurecimiento con systemd impide que el backend escale privilegios (`NoNewPrivileges=yes`)

**Riesgo residual:** Medio. El usuario del servicio de la aplicación tiene inherentemente acceso amplio a los buzones vía doveadm. Se mitiga con audit logging y sandboxing de systemd. Se está evaluando un proxy de doveadm dedicado con autorización por operación.

---

### T10: Agotamiento de Recursos del Sistema

**Descripción:** Un atacante satura el sistema mediante adjuntos de gran tamaño, llamadas masivas a la API, bombardeo de correos o consultas de búsqueda que consumen excesiva CPU o memoria.

**Mitigaciones:**
- `MAX_UPLOAD_SIZE_MB` limita el tamaño de los adjuntos (por defecto: 25 MB)
- Limitación de tasa por usuario por minuto en la API
- `message_size_limit` y `smtpd_recipient_limit` en Postfix
- Limitación de tasa y greylisting de Rspamd para el correo entrante
- Límites del pool de conexiones a la base de datos (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`)
- Controles de recursos de systemd disponibles (`MemoryMax`, `CPUQuota`)

**Riesgo residual:** Bajo. Los ataques distribuidos podrían aún provocar degradación. Se mitiga con reglas de firewall en capa superior y alertas de monitoreo.

---

## Matriz Resumen

| ID  | Amenaza                                  | Severidad | Probabilidad | Riesgo Residual |
|-----|------------------------------------------|-----------|--------------|-----------------|
| T1  | Acceso no autorizado a buzones           | Alta      | Media        | Medio           |
| T2  | Suplantación de correo                   | Alta      | Baja         | Bajo            |
| T3  | Exportación no autorizada                | Alta      | Baja         | Medio           |
| T4  | Manipulación de evidencia                | Crítica   | Baja         | Medio           |
| T5  | Eliminación bajo legal hold              | Crítica   | Baja         | Bajo            |
| T6  | Filtración de secretos                   | Alta      | Baja         | Bajo            |
| T7  | Manipulación de logs                     | Media     | Media        | Alto            |
| T8  | Abuso de rol de administrador            | Alta      | Baja         | Medio           |
| T9  | Escalada de privilegios por doveadm      | Alta      | Baja         | Medio           |
| T10 | Agotamiento de recursos del sistema      | Media     | Media        | Bajo            |

## Calendario de Revisión

Este modelo de amenazas debe revisarse:

- Antes de cada versión mayor (vX.0.0)
- Después de cualquier incidente de seguridad
- Cuando nuevas funcionalidades introduzcan nuevas fronteras de confianza o flujos de datos
- Como mínimo, anualmente
