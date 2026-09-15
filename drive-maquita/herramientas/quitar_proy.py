"""14/09/2026: a las carpetas creadas «NNN Proy CÓDIGO» se les quita la palabra Proy → «NNN CÓDIGO»."""
import json, os, re, sys
sys.path.insert(0, "/home/sistemas/almacen-maquita/servicio")
import nucleo_archivos as nucleo
from seguridad_rutas import ruta_fisica
U = 14
D = "/unidades/13/08  Proyectos/2024 2025 2026 Proyectos e Ingresos"
fis = ruta_fisica(U, D)
reg = []
for n in sorted(os.listdir(fis)):
    m = re.fullmatch(r"(\d{3}) Proy (\S+)", n)
    if not m or not os.path.isdir(os.path.join(fis, n)): continue
    nuevo = m.group(1) + " " + m.group(2)
    if os.path.exists(os.path.join(fis, nuevo)):
        print("[ya existe]", nuevo); continue
    nucleo.renombrar(U, D + "/" + n, nuevo)
    reg.append({"accion": "renombrar", "de": n, "a": nuevo})
json.dump(reg, open("/home/sistemas/almacen-maquita/registros/proyectos-quitar-proy-20260914.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(reg), "renombradas")
