"""Casos compartidos de reglas y cálculos: el motor de Python (servicio/encuestas_reglas.py).
Uso: python3 pruebas/prueba_reglas.py   (desde la raíz de almacen-maquita)"""
import json, math, os, sys
from datetime import date
AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AQUI, '..', 'servicio'))
import encuestas_reglas as r

datos = json.load(open(os.path.join(AQUI, 'reglas-casos.json'), encoding='utf-8'))
hoy = date.fromisoformat(datos['hoy'])
fallas = 0
for c in datos['casos']:
    r.validar(c['regla'])
    obtenido = r.evaluar(c['regla'], c['valores'], c.get('actual'), hoy)
    esp = c['esperado']
    ok = (obtenido is None and esp is None) or (
        isinstance(esp, float) and isinstance(obtenido, float) and obtenido == esp) or (
        not isinstance(esp, float) and obtenido == esp and type(obtenido) is type(esp))
    if not ok:
        fallas += 1
        print('FALLA', c['nombre'], '→', repr(obtenido), 'esperado', repr(esp))
for mala in ({'op': 'xor', 'args': []}, {'fn': 'eval', 'args': []}, {'fn': 'si', 'args': [{'num': 1}]},
             {'fn': 'patron', 'args': [{'ref': 'a'}, {'ref': 'b'}]}, {'num': float('inf')}, {'otra': 1}):
    try:
        r.validar(mala); fallas += 1; print('FALLA: aceptó', mala)
    except r.ReglaInvalida:
        pass
print(f"{len(datos['casos'])} casos, {fallas} fallas")
sys.exit(1 if fallas else 0)
