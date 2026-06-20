# SSO / OIDC — Maquita (identidad unificada del ecosistema)

Login único para correo, Nextcloud, Jitsi y Matrix sobre el **Keycloak existente**.

## Arquitectura
```
maildb (tabla mailbox, ~488 usuarios, hashes Dovecot)
  └─► OpenLDAP (VM181, ou=people,dc=maquita,dc=org)   ← cierra el gap LDAP
        · {SHA512-CRYPT} → {CRYPT}  · {SSHA512} (módulo pw-sha2)  · {SSHA}
        · valida las contraseñas EXISTENTES sin migrar nada
        └─► Keycloak (VM181, realm 'maquita') — User Federation LDAP (READ_ONLY)
              └─► clientes OIDC: Webmail · Nextcloud · Jitsi · Matrix · Wazuh · Centinela
```

## Componentes
- **OpenLDAP** en VM181 (`193.16.0.181`), base `dc=maquita,dc=org`, `ou=people`.
  Módulo `pw-sha2` cargado (valida `{SSHA512}` de Dovecot).
- **Sincronización** `deploy/sso/sync-ldap-from-maildb.sh` (corre en VM130):
  lee `mailbox` activos y los carga/actualiza en LDAP reusando los hashes.
  Config/credenciales en `/etc/maquita/ldap-sync.env` (FUERA del repo).
  Conviene un cron diario + ejecutarlo tras cambios de contraseña.
- **Keycloak** realm `maquita`: federación LDAP `ldap-maildb` (READ_ONLY, importEnabled),
  mappers `mail→email` y `cn→firstName`. Los buzones aparecen como usuarios del realm.

## Política de contraseñas
Las contraseñas NO se migran ni duplican: la verdad sigue en `maildb`; LDAP valida
los mismos hashes; Keycloak hace bind LDAP. Un cambio de clave en el webmail/panel
debe re-sincronizarse a LDAP (re-correr el sync o añadir el hook).

## Cómo conectar una app nueva al SSO
1. En Keycloak (realm maquita) crear un **client OIDC** para la app (redirectUris).
2. Configurar la app como cliente OIDC apuntando a
   `https://auth.maquita.org/realms/maquita/.well-known/openid-configuration`.
3. La app recibe `email`/`preferred_username`; se matchea con el buzón.

## Estado
- [x] LDAP desde maildb (488 usuarios) — gap LDAP cerrado
- [x] Federación LDAP en Keycloak (realm maquita)
- [ ] Webmail como cliente OIDC (flujo add-on, login local = break-glass)
- [ ] Nextcloud / Jitsi / Matrix como clientes OIDC
- [ ] XOAUTH2 en Dovecot/Postfix (clientes de escritorio con token)
