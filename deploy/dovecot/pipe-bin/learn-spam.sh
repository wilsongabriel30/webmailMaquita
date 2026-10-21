#!/bin/bash
# Llamado por report-spam.sieve con el correo por la entrada estándar.
exec /usr/bin/rspamc learn_spam
