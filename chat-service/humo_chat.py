# Prueba de humo T-41 - seccion Chat en MODO APP (UA MaquitaTeams), contra el dominio publico
import time, json, urllib.request, urllib.error, http.cookiejar, jwt
env = {}
for l in open('/opt/maquita-webmail/chat-service/.env'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.strip().split('=', 1); env[k] = v.strip('"\'')
tok = jwt.encode({'sub': 'test@maquita.org', 'type': 'access', 'exp': int(time.time())+900},
                 env['CHAT_JWT_SECRET'], algorithm='HS256')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151 Safari/537.36 MaquitaTeams/0.4.34'
B = 'https://mail.maquita.org'
cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
fallas = []
def pedir(ruta, con_token=True, html=False, metodo='GET', datos=None):
    r = urllib.request.Request(B + ruta, method=metodo, data=datos)
    r.add_header('User-Agent', UA)
    r.add_header('Accept', 'text/html,application/xhtml+xml' if html else 'application/json')
    if con_token: r.add_header('Cookie', 'access_token=' + tok)
    try:
        resp = op.open(r, timeout=25); return resp.status, resp.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'ignore')
def check(nombre, ok, detalle):
    print(('[OK    ] ' if ok else '[FALLA ] ') + nombre + ' - ' + detalle)
    if not ok: fallas.append(nombre)

c, b = pedir('/chat/', True, True)
check('Chat - la pagina abre en modo app', c == 200 and '<title' in b and len(b) > 2000, 'estado=%d %dB' % (c, len(b)))
c, b = pedir('/api/chat/conversations?limit=50')
try: n = len(json.loads(b).get('conversaciones', []))
except Exception: n = -1
check('Chat - lista de conversaciones (no en blanco)', c == 200 and n >= 0, 'estado=%d conversaciones=%d' % (c, n))
c, b = pedir('/api/chat/unread/count')
check('Chat - contador de no leidos', c == 200, 'estado=%d' % c)
c, b = pedir('/api/chat/presence/update', metodo='POST', datos=b'{}')
check('Chat - presencia', c in (200, 204), 'estado=%d' % c)
cj.clear()
c, b = pedir('/chat/', False, True)
ok = c == 401 and '<html' in b.lower() and 'sesion' in b.lower() and 'No autenticado"' not in b
check('Chat - SIN sesion: mensaje claro, NUNCA pantalla en blanco (T-41)', ok, 'estado=%d html=%s' % (c, '<html' in b.lower()))
c, b = pedir('/api/chat/conversations', False)
check('Chat - SIN sesion: la API responde JSON con motivo', c == 401 and 'motivo' in b, 'estado=%d' % c)
cj.clear()
c, b = pedir('/chat/', True, True)
check('Chat - vuelve a abrir tras reponer la sesion', c == 200, 'estado=%d' % c)
# 31/08: la app abre una conversacion concreta por esta ruta; devolvia 404 («Not Found»)
c, b = pedir('/chat/conversation/32', True, True)
check('Chat - abrir una conversacion por su URL (nunca 404)', c == 200 and 'openConversation' in b, 'estado=%d' % c)
c, b = pedir('/chat/?conv=32', True, True)
check('Chat - abrir conversacion con ?conv=', c == 200, 'estado=%d' % c)
print(('\nCandado Chat: TODO OK - 0 fallas' if not fallas else '\nCandado Chat: %d FALLAS -> %s' % (len(fallas), fallas)))
