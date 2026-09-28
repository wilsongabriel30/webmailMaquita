require ["fileinto", "mailbox"];

# Los remitentes de confianza de cada usuario NO se resuelven aqui. Viven en el filtro personal
# del propio usuario y la clasificacion de spam se movio a after.sieve, que corre despues: asi el
# «stop» del usuario manda y su correo no cae en No deseado. El «include :optional :personal
# "confianza"» que habia aqui tumbaba LMTP con segfault en Pigeonhole 2.4.1 (21/09/2026).

# Adjunto ejecutable o malicioso detectado por el milter Safe Attachments -> cuarentena en Junk
if exists "X-Maquita-Quarantine" {
    fileinto :create "Junk";
    stop;
}

# --- 2026-08-31: correo de sistema a carpetas propias -----------------------
# Los alias postmaster@ y root@ apuntan a tecnologia+<detalle>@example.org.
# El detalle sobrevive hasta Dovecot en la cabecera Delivered-To (comprobado),
# asi que se clasifica aqui SIN activar lmtp_save_to_detail_mailbox, que es
# una opcion GLOBAL y habria cambiado el comportamiento de los 279 buzones.
# El separador de jerarquia es "." -> los dominios van con guiones, no puntos.
if header :contains "Delivered-To" "tecnologia+Postmaster-maquita@" {
    fileinto :create "Postmaster.maquita-com-ec";
    stop;
}
if header :contains "Delivered-To" "tecnologia+Postmaster-mcch@" {
    fileinto :create "Postmaster.mcch-com-ec";
    stop;
}
if header :contains "Delivered-To" "tecnologia+Postmaster-turismo@" {
    fileinto :create "Postmaster.turismo-example";
    stop;
}
if header :contains "Delivered-To" "tecnologia+Postmaster-fundmcch@" {
    fileinto :create "Postmaster.fundacion-example";
    stop;
}
if header :contains "Delivered-To" "tecnologia+Root@" {
    fileinto :create "Root";
    stop;
}
if header :contains "Delivered-To" "tecnologia+Alertas-PVE@" {
    fileinto :create "Alertas-PVE";
    stop;
}
