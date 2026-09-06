"""Runner CLI del motor SafeAttach (multi-motor + detonación).

Uso: python -m app.safeattach.scan_file <ruta> <nombre_original>
Imprime el veredicto en JSON (result, threats, details). Lo usa el panel.
"""

import json
import sys

from app.safeattach import scan_attachment


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "uso: scan_file <ruta> <nombre>"}))
        return
    path, name = sys.argv[1], sys.argv[2]
    with open(path, "rb") as f:
        content = f.read()
    print(json.dumps(scan_attachment(content, name, ""), ensure_ascii=False))


if __name__ == "__main__":
    main()
