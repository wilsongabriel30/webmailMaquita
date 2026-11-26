#!/usr/bin/env python3
"""Convierte en segundo plano los formatos antiguos (.xls, .doc, .ppt, .xlsb…) que
se subieron al Drive (cola `conversiones_pendientes`, módulo conversion_automatica).

Uso:
  convertir_pendientes.py                   # procesa la cola (hasta 20 archivos o 25 min)
  convertir_pendientes.py --barrer 300      # además encola 300 archivos antiguos que ya
                                            # estaban en el Drive (del más pequeño al más grande)
  convertir_pendientes.py --estado          # cuántos hay en cada estado

Lo corre cron (/etc/cron.d/almacen-conversion-automatica) con flock para no solaparse.
Registro: /home/sistemas/almacen-maquita/registros/conversion-automatica.log
"""
import argparse
import logging
import sys
import time

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
log = logging.getLogger('convertir_pendientes')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--barrer', type=int, default=0, help='encolar N archivos antiguos ya existentes')
    p.add_argument('--maximo-mb', type=int, default=0, help='al barrer, solo archivos de hasta N MB')
    p.add_argument('--limite', type=int, default=20)
    p.add_argument('--segundos', type=int, default=1500)
    p.add_argument('--estado', action='store_true')
    args = p.parse_args()

    import conversion_automatica as ca
    if args.estado:
        print(ca.resumen_estado())
        return
    if args.barrer:
        n = ca.encolar_antiguos(args.barrer, args.maximo_mb * 1024 * 1024 if args.maximo_mb else None)
        log.info('barrido: %d archivos antiguos encolados', n)
    t0 = time.time()
    r = ca.procesar(limite=args.limite, segundos_max=args.segundos)
    if any(r.values()):
        log.info('cola procesada en %.0f s: %s · estado: %s', time.time() - t0, r, ca.resumen_estado())


if __name__ == '__main__':
    main()
