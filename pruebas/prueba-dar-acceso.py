# -*- coding: utf-8 -*-
"""De la solicitud al acceso: el recorrido entero, sin mandar correos.

Se ejecuta con:
    cd /home/sistemas/almacen-maquita/servicio
    sudo -u sistemas python3 ../pruebas/prueba-dar-acceso.py

Al final se deshace todo lo que crea: no deja ninguna solicitud ni ningún
compartido de prueba.
"""
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

from almacen_bd import consultar, ejecutar
import solicitudes_acceso as SA
from permisos_accion import puede_leer

DUENA = 104                                  # Janeth, dueña de la carpeta
RUTA = '/Trazabilidad proyecto GO12'
# El acceso se mide DONDE lo ve quien pide: en «Compartido conmigo». Sobre la
# ruta a secas todo el mundo «puede», porque seria su propio espacio.
RUTA_VISTA = '/compartido/%d%s' % (104, RUTA)
QUIEN_PIDE = 17                              # Wilson

fallos = 0


def comprobar(condicion, texto):
    global fallos
    fallos += 0 if condicion else 1
    print(('OK  ' if condicion else 'MAL ') + texto)


# El correo no se manda en la prueba: se sustituye el envío.
correos = []
SA._avisar = lambda comp, email, nombre, mensaje, clave=None: (
    correos.append({'clave': clave, 'para': comp['propietario_id']}) or True)

fila = consultar('SELECT username, email FROM usuarios WHERE id = %s',
                 (QUIEN_PIDE,), nomina=True)
correo_solicitante = (fila[0]['email'] or '').lower()

print('== antes ==')
comprobar(not puede_leer(QUIEN_PIDE, RUTA_VISTA), 'quien pide NO tiene acceso todavia')

print()
print('== pide el acceso ==')
ok, mensaje = SA.registrar_por_ruta(DUENA, RUTA, correo_solicitante, 'Wilson',
                                    'Lo necesito para la revision')
comprobar(ok, 'la solicitud se registra: ' + mensaje)
comprobar(len(correos) == 1 and correos[0]['clave'],
          'el correo al dueno lleva su clave para el boton')
clave = correos[0]['clave']

print()
print('== el dueno pulsa «Dar acceso» ==')
ok, mensaje, solicitud = SA.conceder(clave, DUENA)
comprobar(ok, 'se concede: ' + mensaje)
comprobar(puede_leer(QUIEN_PIDE, RUTA_VISTA), 'quien pedia YA puede entrar')

from permisos_accion import puede_escribir
comprobar(not puede_escribir(QUIEN_PIDE, RUTA_VISTA), 'de momento solo lectura')

print()
print('== ampliar a edicion ==')
ok, mensaje, _ = SA.conceder(clave, DUENA, puede_editar=True)
comprobar(ok and puede_escribir(QUIEN_PIDE, RUTA_VISTA), 'ahora tambien puede editar')

print()
print('== lo que NO debe pasar ==')
ok, mensaje, _ = SA.conceder(clave, QUIEN_PIDE)
comprobar(not ok and 'no es tuya' in mensaje,
          'otra persona no puede conceder con esa clave')

ok, mensaje, _ = SA.conceder('clave-inventada-12345', DUENA)
comprobar(not ok, 'una clave inventada no vale')

estado = consultar('SELECT estado FROM solicitudes_acceso WHERE clave_respuesta = %s',
                   (clave,))
comprobar(estado and estado[0]['estado'] == 'aceptada',
          'la solicitud queda marcada como aceptada')

# ── Se deshace todo ──────────────────────────────────────────────────────
ejecutar('DELETE FROM compartidos WHERE propietario_id = %s AND ruta = %s '
         '  AND LOWER(email) = %s', (DUENA, RUTA, correo_solicitante))
ejecutar('DELETE FROM solicitudes_acceso WHERE clave_respuesta = %s', (clave,))

print()
comprobar(not puede_leer(QUIEN_PIDE, RUTA_VISTA), 'la prueba no deja rastro: se quita el acceso')
print()
print('fallos:', fallos)
sys.exit(1 if fallos else 0)
