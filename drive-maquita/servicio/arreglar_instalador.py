#!/usr/bin/env python3
"""Instalador: el secreto del canal panel→Almacén se genera ANTES de escribir el .env del panel y
entra en su heredoc; corrige también la prueba de enlaces (registra el SQL de cada consulta)."""
p = "deploy/webmail/instalar.sh"
s = open(p, encoding="utf-8").read()
bloque = """  # Canal panel -> Almacén (loopback, secreto propio): vincular buzones y cuota del Drive
  SECRETO_PANEL=$(openssl rand -hex 24)
  grep -q '^ALMACEN_SECRETO_PANEL=' "${APP_DIR}/almacen/.env" 2>/dev/null || echo "ALMACEN_SECRETO_PANEL=${SECRETO_PANEL}" >> "${APP_DIR}/almacen/.env"
"""
assert s.count(bloque) == 1
s = s.replace(bloque, "")
ancla = 'cd "${APP_DIR}/admin-panel/backend"\n'
assert s.count(ancla) == 1
s = s.replace(ancla, ancla + """# Canal panel -> Almacén (loopback, secreto propio): vincular buzones a personas del directorio y
# fijar la cuota del Drive al crear el buzón. El mismo valor va en almacen/.env y en el .env del panel.
SECRETO_PANEL=$(openssl rand -hex 24)
grep -q '^ALMACEN_SECRETO_PANEL=' "${APP_DIR}/almacen/.env" 2>/dev/null || echo "ALMACEN_SECRETO_PANEL=${SECRETO_PANEL}" >> "${APP_DIR}/almacen/.env"
""")
fin = "WEBMAIL_IMAP_PORT=143\nENVADMIN\n"
assert s.count(fin) == 1
s = s.replace(fin, "WEBMAIL_IMAP_PORT=143\nALMACEN_URL=http://127.0.0.1:8788\nALMACEN_SECRETO_PANEL=${SECRETO_PANEL}\nENVADMIN\n")
open(p, "w", encoding="utf-8").write(s)

t = "almacen/tests/test_enlaces_correo.py"
s = open(t, encoding="utf-8").read()
s = s.replace("        llamadas.append((sql.split()[0], parametros, nomina))", "        llamadas.append((\" \".join(sql.split()), parametros, nomina))")
s = s.replace('    assert llamadas[0][0] == "SELECT" and "enlaces_correo" in str(llamadas)', '    assert "enlaces_correo" in llamadas[0][0]  # el vínculo se mira antes que el correo')
open(t, "w", encoding="utf-8").write(s)
print("instalador y prueba corregidos")
