require ["fileinto", "mailbox"];

# Filtro global que corre ANTES del filtro personal de cada usuario (instalación nueva).
# Adjunto ejecutable o malicioso detectado por el milter Safe Attachments -> cuarentena en Junk
if exists "X-Maquita-Quarantine" {
    fileinto :create "Junk";
    stop;
}
