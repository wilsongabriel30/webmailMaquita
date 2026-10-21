#!/bin/bash
# Llamado por report-ham.sieve con el correo por la entrada estándar.
exec /usr/bin/rspamc learn_ham
