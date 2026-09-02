# -*- coding: utf-8 -*-
"""¿Un enlace interno que apunta a contenido de otra persona acaba donde debe?

Se ejecuta con:
    cd /home/sistemas/almacen-maquita/servicio
    sudo -u sistemas python3 ../pruebas/prueba-resolver-enlace.py
"""
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

from resolver_enlace import resolver, existe_para

CASOS = [
    # (quien, ruta, que se espera, por que)
    (104, '/Trazabilidad proyecto GO12', 'nada',
     'su duena entra normal'),
    (17, '/Trazabilidad proyecto GO12', 'pedir_acceso',
     'a quien no se lo comparten se le ofrece pedirlo'),
    (140, '/M&E Maquita Cacao/Levantamiento', 'ir_a',
     'a quien SI se lo comparten se le lleva alli'),
    (53, '/M&E Maquita Cacao/Levantamiento', 'nada',
     'su dueno entra normal'),
    (44, '/M&E Maquita Cacao/Levantamiento', 'pedir_acceso',
     'a un ajeno se le ofrece pedirlo'),
    (17, '/no-existe-esto-12345', 'nada',
     'lo que de verdad no existe se deja como estaba'),
    (17, '/unidades/9/1 Esmeraldas Procesos Formativos y Sociales', 'nada',
     'las unidades tienen su propio camino'),
    (17, '/compartido/53/M&E Maquita Cacao', 'nada',
     'lo que ya viene por el camino bueno no se toca'),
]

fallos = 0
for quien, ruta, esperado, porque in CASOS:
    salida = resolver(quien, ruta)
    if salida is None:
        obtenido = 'nada'
    elif salida.get('ir_a'):
        obtenido = 'ir_a'
    else:
        obtenido = 'pedir_acceso'
    correcto = obtenido == esperado
    fallos += 0 if correcto else 1
    print('%s %-58s -> %-5s  %s' % ('OK ' if correcto else 'MAL', porque,
                                    obtenido, salida.get('ir_a', '') if salida else ''))

print()
print('fallos:', fallos)
sys.exit(1 if fallos else 0)
