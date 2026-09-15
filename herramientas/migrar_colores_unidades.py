"""14/09/2026: los colores que cada persona puso en carpetas de las unidades
compartidas pasan al estilo COMPARTIDO (usuario 0) para que los vean todos.
Uso: python3 migrar_colores_unidades.py [ejecutar]"""
import os
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
from almacen_bd import consultar, ejecutar          # noqa: E402
import estilos_compartidos as ec                   # noqa: E402

ejecutar_ = len(sys.argv) > 1 and sys.argv[1] == 'ejecutar'
RAIZ = '/mnt/almacen/_unidades'
personales = {}
for f in consultar('SELECT usuario_id, folder_id, color, icono FROM estilos_carpeta '
                   'WHERE usuario_id <> 0'):
    personales.setdefault(f['folder_id'], []).append(f)
compartidos = ec.estilos_de_unidad()
usuarios = sorted({f['usuario_id'] for l in personales.values() for f in l})
print('usuarios con estilos:', usuarios, '| estilos personales:', sum(map(len, personales.values())))

nuevos = 0
for unidad in sorted(os.listdir(RAIZ)):
    base = os.path.join(RAIZ, unidad, 'archivos')
    if not unidad.isdigit() or not os.path.isdir(base):
        continue
    for raiz, dirs, _ in os.walk(base):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for d in dirs:
            rel = os.path.relpath(os.path.join(raiz, d), base).replace(os.sep, '/')
            ruta = f'/unidades/{unidad}/{rel}'
            fid_comp = ec.folder_id_compartido(ruta)
            if fid_comp in compartidos:
                continue
            hallado = None
            for uid in (17, 14) + tuple(u for u in usuarios if u not in (17, 14)):
                filas = personales.get(ec._hash(uid, ruta))
                if filas:
                    hallado = filas[0]
                    break
            if not hallado or not (hallado['color'] or hallado['icono']):
                continue
            nuevos += 1
            print(f"[{hallado['usuario_id']}] {ruta}  → {hallado['color']} {hallado['icono'] or ''}")
            if ejecutar_:
                ejecutar('INSERT INTO estilos_carpeta (usuario_id, folder_id, color, icono) '
                         'VALUES (0, %s, %s, %s) ON CONFLICT DO NOTHING',
                         (fid_comp, hallado['color'], hallado['icono']))
print('estilos compartidos nuevos:', nuevos, '(ejecutado)' if ejecutar_ else '(simulación)')
