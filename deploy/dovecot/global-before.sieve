require ["fileinto", "mailbox"];

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
