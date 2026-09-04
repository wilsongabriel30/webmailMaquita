# Candado T-15: la cabecera de la conversacion trae los botones de Teams.
import time, re, urllib.request, urllib.error, http.cookiejar, jwt
env = {}
for l in open('/opt/maquita-webmail/chat-service/.env'):
    if '=' in l and not l.strip().startswith('#'):
        k, v = l.strip().split('=', 1); env[k] = v.strip('"\'')
tok = jwt.encode({'sub': 'test@maquita.org', 'type': 'access', 'exp': int(time.time())+900},
                 env['CHAT_JWT_SECRET'], algorithm='HS256')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/151 MaquitaTeams/0.4.41'
B = 'https://mail.maquita.org'
cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
fallas = []
def check(n, ok, d=''):
    print(('[OK    ] ' if ok else '[FALLA ] ') + n + (' - ' + d if d else ''))
    if not ok: fallas.append(n)
def pedir(ruta):
    time.sleep(1)
    r = urllib.request.Request(B + ruta)
    r.add_header('User-Agent', UA); r.add_header('Accept', 'text/html')
    r.add_header('Cookie', 'access_token=' + tok)
    try:
        resp = op.open(r, timeout=25); return resp.status, resp.read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e: return e.code, e.read().decode('utf-8', 'ignore')

c, h = pedir('/chat/')
check('T-15 . la cabecera trae videollamada y llamada de voz',
      'btnLlamadaVideo' in h and 'btnLlamadaAudio' in h, 'estado=%d' % c)
check('T-15 . el boton de llamada dice que en grupo llama a todos',
      'en un grupo' in h, 'titulos claros')
c2, js_grupos = pedir('/static/js/chat-grupos.js?v=20260831-t15')
check('T-15 . boton «iniciar chat de grupo» desde un 1a1 (con la persona actual)',
      'btnChatGrupoDesde' in js_grupos and 'addGroupMember' in js_grupos, 'estado=%d' % c2)
check('T-15 . en grupo se muestran videollamada y llamada (no solo la conferencia)',
      "conv-grupo" in js_grupos, 'clase de cabecera de grupo')
c3, css = pedir('/static/css/chat-page.css')
check('T-15 . el CSS muestra esos botones en grupos',
      'body.conv-grupo #btnLlamadaVideo' in css, 'estado=%d' % c3)
c4, js_meet = pedir('/static/js/chat-meet.js?v=20260831-t15')
check('T-15 . en grupo la videollamada arranca la conferencia grupal con el tipo',
      'iniciarConferenciaDesdeChat(tipo)' in js_meet and 'groupName, tipo' in js_meet, 'estado=%d' % c4)
c5, js_llam = pedir('/static/js/chat-llamadas.js?v=20260831-t15')
check('T-15 . la invitacion grupal viaja con el tipo y la ventana entra con camara',
      "tipo: tipo || 'audio'" in js_llam and "'&video=1'" in js_llam, 'estado=%d' % c5)
c6, conf = pedir('/chat/conferencia?role=guest&room=humo&name=Prueba&video=1')
check('T-15 . la ventana de conferencia enciende la camara si es videollamada',
      c6 == 200 and "Q.get('video') === '1'" in conf, 'estado=%d' % c6)
# T-30 (4): la purga por retencion de las grabaciones vive en esta VM
import subprocess
cron = subprocess.run(['bash', '-lc', 'ls /etc/cron.d/ | grep -c purgar-grabaciones'],
                      capture_output=True, text=True).stdout.strip()
check('T-30 (4) . la purga por retencion de grabaciones esta programada', cron == '1', 'cron=%s' % cron)
print('\nCandado T-15: %s' % ('TODO OK - 0 fallas' if not fallas else '%d FALLAS -> %s' % (len(fallas), fallas)))
