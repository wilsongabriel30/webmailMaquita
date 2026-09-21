require ["fileinto", "mailbox"];

# Remitentes de confianza del usuario: se comprueban ANTES de mover a No deseado (opcional por usuario).
# NO ACTIVAR (incidente del 18-21/09/2026): con esta linea LMTP moria con segfault en
# libdovecot-sieve (Dovecot 2.4.1) y una decena de buzones estuvo casi tres dias sin recibir
# correo; 41 mensajes se devolvieron al remitente. Antes de volver a intentarlo, reproducirlo en
# una cuenta de prueba y vigilar `grep "signal 11" /var/log/mail.log`.
# include :optional :personal "confianza";

# Adjunto ejecutable o malicioso detectado por el milter Safe Attachments -> cuarentena en Junk
if exists "X-Maquita-Quarantine" {
    fileinto :create "Junk";
    stop;
}

# Si X-Spam-Flag es YES (puesto por rspamd o filtro custom), mover a Junk
if header :is "X-Spam-Flag" "YES" {
    fileinto :create "Junk";
    stop;
}

if header :contains "X-Spam-Status" "Yes" {
    fileinto :create "Junk";
    stop;
}

# Header custom del filtro Python
if header :is "X-Maquita-Spam" "YES" {
    fileinto :create "Junk";
    stop;
}

# --- 2026-08-31: correo de sistema a carpetas propias -----------------------
# Los alias postmaster@ y root@ apuntan a gestiontecnologia+<detalle>@maquita.org.
# El detalle sobrevive hasta Dovecot en la cabecera Delivered-To (comprobado),
# asi que se clasifica aqui SIN activar lmtp_save_to_detail_mailbox, que es
# una opcion GLOBAL y habria cambiado el comportamiento de los 279 buzones.
# El separador de jerarquia es "." -> los dominios van con guiones, no puntos.
if header :contains "Delivered-To" "gestiontecnologia+Postmaster-maquita@" {
    fileinto :create "Postmaster.maquita-com-ec";
    stop;
}
if header :contains "Delivered-To" "gestiontecnologia+Postmaster-mcch@" {
    fileinto :create "Postmaster.mcch-com-ec";
    stop;
}
if header :contains "Delivered-To" "gestiontecnologia+Postmaster-turismo@" {
    fileinto :create "Postmaster.maquitaturismo-com";
    stop;
}
if header :contains "Delivered-To" "gestiontecnologia+Postmaster-fundmcch@" {
    fileinto :create "Postmaster.fundmcch-com-ec";
    stop;
}
if header :contains "Delivered-To" "gestiontecnologia+Root@" {
    fileinto :create "Root";
    stop;
}
if header :contains "Delivered-To" "gestiontecnologia+Alertas-PVE@" {
    fileinto :create "Alertas-PVE";
    stop;
}
