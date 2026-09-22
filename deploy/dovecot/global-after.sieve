require ["fileinto", "mailbox"];

# Clasificacion de correo no deseado. Se ejecuta DESPUES del filtro personal de cada usuario:
# si el remitente esta en su lista de confianza, su script ya hizo «fileinto "INBOX"; stop;» y
# esta parte no llega a ejecutarse, que es justo lo que se busca.
# (Antes vivia en before.sieve junto a un «include :personal» que tumbaba LMTP - 21/09/2026.)

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
