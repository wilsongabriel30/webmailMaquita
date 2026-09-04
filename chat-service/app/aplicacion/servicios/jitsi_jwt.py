# -*- coding: utf-8 -*-
"""
JWT de Meet Maquita (Jitsi) — mismo esquema y secreto que el módulo /reuniones/ de FARO
(`modulos/jitsi/aplicacion/servicios/servicio_jitsi.py`), para que el servidor Teams
Maquita emita tokens válidos sin pasar por FARO.
"""
import os
import re
import time
import uuid
from datetime import datetime

import jwt

JITSI_URL = os.getenv('JITSI_URL', 'https://meet.maquita.com.ec').rstrip('/')
JITSI_DOMAIN = os.getenv('JITSI_DOMAIN', 'meet.maquita.com.ec')
JITSI_APP_ID = os.getenv('JITSI_APP_ID', 'maquita_meet')


def _secreto():
    s = os.getenv('JITSI_APP_SECRET', '')
    if not s:
        raise RuntimeError('JITSI_APP_SECRET no configurado')
    return s


def generar_jwt(usuario_id, nombre, email, sala='*', es_moderador=True, duracion_horas=8, avatar_url=None):
    duracion_horas = min(max(int(duracion_horas or 8), 8), 72)
    ahora = int(time.time())
    payload = {
        'context': {
            'user': {'id': str(usuario_id), 'name': nombre, 'email': email,
                     'avatar': avatar_url or '', 'moderator': es_moderador},
            'features': {'livestreaming': es_moderador, 'recording': es_moderador,
                         'transcription': False, 'outbound-call': False},
        },
        'aud': 'jitsi', 'iss': JITSI_APP_ID, 'sub': JITSI_DOMAIN, 'room': sala,
        'exp': ahora + duracion_horas * 3600, 'iat': ahora, 'nbf': ahora, 'moderator': es_moderador,
    }
    tok = jwt.encode(payload, _secreto(), algorithm='HS256')
    return tok.decode() if isinstance(tok, bytes) else tok


def nombre_sala_nuevo():
    return f"Maquita{datetime.now():%Y%m%d%H%M}{uuid.uuid4().hex[:6]}"


def limpiar_nombre_sala(nombre):
    limpio = re.sub(r'[^a-zA-Z0-9\-_]', '', nombre or '')
    return limpio or nombre_sala_nuevo()


def url_sala(sala, token=None, sin_prejoin=False):
    u = f'{JITSI_URL}/{sala}'
    if token:
        u += f'?jwt={token}' + ('&config.prejoinPageEnabled=false' if sin_prejoin else '')
    return u


# ---------------------------------------------------------------------------
# Perfil «modo app» (cliente de escritorio Teams Maquita) — T-10
# La web de Meet no cambia: estas sobreescrituras viajan en la URL (#config.*) y
# solo las usa la app. Claves de la lista blanca de Jitsi (1.0.9268).
# ---------------------------------------------------------------------------
import json as _json
from urllib.parse import quote as _quote

BOTONES_APP = ["microphone", "camera", "desktop", "chat", "raisehand", "participants-pane", "tileview",
               "fullscreen", "settings", "select-background", "noisesuppression", "recording", "hangup"]


def config_app(moderador=True, camara_al_entrar=True):
    """Configuración óptima y estable para la app: sin pre-join, 720p con simulcast (el servidor ya tiene
    channelLastN/layer suspension), sin P2P (más estable con TURN), detección de ruido, sin funciones web."""
    conf = {
        "config.prejoinPageEnabled": "false",
        "config.disableDeepLinking": "true",
        "config.resolution": "720",
        "config.constraints.video.height.ideal": "720",
        "config.constraints.video.height.max": "720",
        "config.constraints.video.height.min": "180",
        "config.p2p.enabled": "false",
        "config.enableNoisyMicDetection": "true",
        "config.disableInviteFunctions": "true",
        "config.disableThirdPartyRequests": "true",
        "config.startWithAudioMuted": "false",
        "config.startWithVideoMuted": "false" if camara_al_entrar else "true",
        "config.toolbarButtons": _json.dumps(BOTONES_APP if moderador else [b for b in BOTONES_APP if b != "recording"]),
        # Codec: AV1 preferido (mejor calidad por bit) con caida automatica a VP9/VP8 si el equipo o el par no lo soportan
        "config.videoQuality.codecPreferenceOrder": _json.dumps(["AV1", "VP9", "VP8"]),
        "config.videoQuality.preferredCodec": "AV1",
        "config.videoQuality.disabledCodec": "",
        # Pantalla compartida: 1080p a 30 fps (ssHigh) con bitrate suficiente; camara sigue en 720p
        "config.desktopSharingFrameRate.min": "5",
        "config.desktopSharingFrameRate.max": "30",
        "config.videoQuality.maxBitratesVideo": _json.dumps({
            "AV1": {"low": 100000, "standard": 300000, "high": 1000000, "ssHigh": 2500000},
            "VP9": {"low": 100000, "standard": 300000, "high": 1200000, "ssHigh": 2500000},
            "VP8": {"low": 200000, "standard": 500000, "high": 1500000, "ssHigh": 2500000},
            "H264": {"low": 200000, "standard": 500000, "high": 1500000, "ssHigh": 2500000}}),
        "config.videoQuality.minHeightForQualityLvl": _json.dumps({"360": "standard", "720": "high", "1080": "high"}),
        "interfaceConfig.SHOW_JITSI_WATERMARK": "false",
        "interfaceConfig.MOBILE_APP_PROMO": "false",
        "interfaceConfig.SHOW_CHROME_EXTENSION_BANNER": "false",
    }
    return "&".join(f"{k}={_quote(v, safe='')}" for k, v in conf.items())


def url_sala_app(sala, token, moderador=True, camara_al_entrar=True):
    return f"{JITSI_URL}/{sala}?jwt={token}#{config_app(moderador, camara_al_entrar)}"
