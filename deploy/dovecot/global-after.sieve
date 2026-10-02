require ["fileinto", "mailbox"];

# Clasificacion de correo no deseado. Se ejecuta DESPUES del filtro personal de cada usuario:
# si el remitente esta en su lista de confianza, su script ya hizo «fileinto "INBOX"; stop;» y
# esta parte no llega a ejecutarse, que es justo lo que se busca.
# (Antes vivia en before.sieve junto a un «include :personal» que tumbaba LMTP - 21/09/2026.)

# rspamd (milter_headers, routine spam-header) marca el spam de 6 puntos en adelante con
# «Deliver-To: Junk» y no con X-Spam-Flag: sin esta regla llegaba a la bandeja de entrada
# salvo que el filtro Python tambien lo detectara (02/10/2026).
if header :is "Deliver-To" "Junk" {
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
