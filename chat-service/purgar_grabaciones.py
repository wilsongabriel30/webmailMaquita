#!/opt/maquita-webmail/chat-service/venv/bin/python3
# -*- coding: utf-8 -*-
"""Retención de grabaciones (12 meses): las vencidas y no marcadas «conservar» pasan a la papelera del Drive del creador. Cron mensual."""
import os, sys
BASE = '/opt/maquita-webmail/chat-service'
sys.path.insert(0, os.path.join(BASE, 'app'))
for l in open(os.path.join(BASE, '.env'), encoding='utf-8'):
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
from interfaces.api.grabaciones_drive import purgar_grabaciones
print(f'{purgar_grabaciones()} grabaciones vencidas enviadas a la papelera')
