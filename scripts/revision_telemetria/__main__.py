"""Punto de entrada: python -m revision_telemetria [--sin-correo] [--horas N] [--destino correo]."""
import argparse
import os
import sys
from datetime import datetime

from . import config, consultas_bd, consultas_journal, consultas_redis, correo, informe
from .hallazgo import CRITICO, ALTO


def main(argv=None):
    p = argparse.ArgumentParser(description='Revisión diaria de la telemetría del webmail Maquita')
    p.add_argument('--sin-correo', action='store_true', help='solo imprime y guarda el informe')
    p.add_argument('--horas', type=int, default=config.HORAS_VENTANA)
    p.add_argument('--destino', default=config.DESTINO_CORREO)
    p.add_argument('--no-guardar', action='store_true')
    args = p.parse_args(argv)

    hallazgos, errores, cifras = [], [], []
    mapa_ip = {}
    try:
        h, mapa_ip = consultas_bd.todo(args.horas)
        hallazgos += h
    except Exception as e:  # una fuente caída no debe impedir el resto del informe
        errores.append(f'PostgreSQL (app_telemetria/dlp_violations): {e}')
    try:
        h, total_llm = consultas_journal.todo(args.horas, mapa_ip)
        hallazgos += h
        cifras.append(f'Llamadas a la IA registradas: {total_llm}')
    except Exception as e:
        errores.append(f'journal de {config.SERVICIO_JOURNAL}: {e}')
    try:
        h, filas = consultas_redis.hallazgos()
        hallazgos += h
        dia = sorted((f for f in filas if f[0] == 'day'), key=lambda f: -f[2])[:5]
        cifras.append('Mayores remitentes del día (send_rl:day): ' + ', '.join(f'{u}={n}' for _, u, n, _ in dia))
    except Exception as e:
        errores.append(f'Redis send_rl: {e}')

    texto = informe.armar(hallazgos, args.horas, cifras, errores)
    print(texto)

    if not args.no_guardar:
        os.makedirs(config.DIR_INFORMES, exist_ok=True)
        ruta = os.path.join(config.DIR_INFORMES, datetime.now().strftime('%Y-%m-%d') + '.txt')
        with open(ruta, 'w', encoding='utf-8') as f:
            f.write(texto)
        print(f'[guardado en {ruta}]', file=sys.stderr)

    if not args.sin_correo:
        criticos = sum(1 for h in hallazgos if h.gravedad == CRITICO)
        altos = sum(1 for h in hallazgos if h.gravedad == ALTO)
        asunto = f'[Webmail] Revisión de telemetría {datetime.now():%d/%m/%Y}: {criticos} críticos, {altos} altos'
        mid = correo.enviar(asunto, texto, args.destino)
        print(f'[correo enviado a {args.destino}, Message-ID {mid}]', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
