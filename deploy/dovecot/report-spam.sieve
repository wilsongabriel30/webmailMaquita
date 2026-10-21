# Se ejecuta al MOVER un correo A la carpeta Junk → Rspamd lo aprende como SPAM.
require ["vnd.dovecot.pipe", "copy", "imapsieve"];
pipe :copy "learn-spam.sh";
