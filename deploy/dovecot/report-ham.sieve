# Se ejecuta al SACAR un correo DE Junk → Rspamd lo aprende como HAM (no es spam).
require ["vnd.dovecot.pipe", "copy", "imapsieve", "environment", "variables"];
if environment :matches "imap.mailbox" "*" { set "mailbox" "${1}"; }
# Si lo mueven a la papelera, no se aprende nada.
if string "${mailbox}" "Trash" { stop; }
pipe :copy "learn-ham.sh";
