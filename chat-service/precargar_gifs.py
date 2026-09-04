#!/opt/maquita-webmail/chat-service/venv/bin/python3
# -*- coding: utf-8 -*-
"""
Precarga MASIVA de GIF a la biblioteca propia (28/08/2026).
Recorre la lista de términos de `gifs_terminos.txt` (uno por línea, español e inglés), pide a cada fuente
externa hasta N resultados por término y los descarga a estaticos/gifs + chat_gifs, etiquetados con el término.
Idempotente (origen_url única): se puede relanzar cuando se quiera para ampliar la biblioteca.
Uso: precargar_gifs.py [--por-termino 40] [--solo giphy|commons] [--dry-run]
Registro: /var/log/maquita-chat-gifs-precarga.log
"""
import os
import sys
import time
import argparse
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'app'))
os.chdir(BASE)
for linea in open(os.path.join(BASE, '.env'), encoding='utf-8'):
    linea = linea.strip()
    if linea and not linea.startswith('#') and '=' in linea:
        k, v = linea.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

from interfaces.api import gifs_externos as ge  # noqa: E402


def log(m):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--por-termino', type=int, default=40)
    ap.add_argument('--solo', choices=list(ge.FUENTES))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    terminos = [t.strip() for t in open(os.path.join(BASE, 'gifs_terminos.txt'), encoding='utf-8') if t.strip() and not t.startswith('#')]
    fuentes = {a.solo: ge.FUENTES[a.solo]} if a.solo else ge.FUENTES
    log(f"Precarga: {len(terminos)} términos × {a.por_termino} por fuente ({', '.join(fuentes)})")
    nuevos = repetidos = fallos = 0
    for i, t in enumerate(terminos, 1):
        for nombre, fn in fuentes.items():
            for intento in range(4):
                try:
                    res = fn(t, a.por_termino)
                    break
                except Exception as e:
                    if '429' in str(e) or 'límite' in str(e):
                        log(f"{nombre}: límite de peticiones; pausa de 15 min")
                        time.sleep(900)
                    else:
                        log(f"FALLO búsqueda {nombre} «{t}»: {e}")
                        res = []
                        break
            else:
                res = []
            for r in res:
                if r.get('bytes') and r['bytes'] > ge.TAM_MAX:
                    continue
                if a.dry_run:
                    continue
                try:
                    antes = time.time()
                    fila = ge.importar_gif(r['url'], r['titulo'], t, nombre)
                    if fila['etiquetas'] and t.lower() not in fila['etiquetas'].split():
                        # ya existía por otro término: sumar la etiqueta nueva
                        with ge._conexion() as con, con.cursor() as cur:
                            cur.execute("UPDATE chat_gifs SET etiquetas = %s WHERE id = %s",
                                        (ge._normalizar_etiquetas(fila['etiquetas'] + ' ' + t), fila['id']))
                        repetidos += 1
                    elif time.time() - antes < 0.05:
                        repetidos += 1
                    else:
                        nuevos += 1
                except Exception as e:
                    fallos += 1
                    log(f"FALLO descarga {r['url'][:80]}: {e}")
            time.sleep(1.5)  # respetar límites de la fuente
        if i % 10 == 0:
            log(f"{i}/{len(terminos)} términos · nuevos={nuevos} repetidos={repetidos} fallos={fallos}")
    log(f"FIN: nuevos={nuevos} repetidos={repetidos} fallos={fallos}")


if __name__ == '__main__':
    main()
