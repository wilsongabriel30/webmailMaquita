# neurona_spam.py — Neurona de spam (patron INFINITO):
#   1) Determinista primero (reglas duras, 0 costo)
#   2) Mini-red neuronal (MLP propio) para casos grises, aprende y persiste en JSON
#   3) LLM local SOLO si la red duda (micro-llamada acotada al servidor IA)
#   4) Modulo independiente: se engancha en UN punto del filtro.
# Advisory: NEURONA_PESO controla cuanto influye en el score (0 = solo registra).
import os
import logging
from red_neuronal import RedNeuronal

PESOS = "/opt/maquita-mail-filter/datos/neurona_spam.json"
ETIQUETAS = ["ham", "spam"]
def _peso_cfg():
    import json
    try:
        with open("/etc/maquita-mail/filtro-avanzado.json", encoding="utf-8") as fh:
            return int(json.load(fh).get("neurona_peso", 0) or 0)
    except Exception:
        return 0


NEURONA_PESO = _peso_cfg()   # 0 = log-only (advisory). Se afina desde el panel.
IA_URL = "http://193.16.0.170:11434/api/generate"
IA_MODEL = os.environ.get("MAQUITA_IA_MODEL", "gemma2:9b")

# 8 features derivadas de las 'razones' que ya produce el filtro (costo 0)
_FEATS = [
    ("adjunto-peligroso", "ejecutable-en-comprimido"),     # f0 ejecutable
    ("office-con-macros", "office-macros-en-comprimido"),  # f1 macros
    ("comprimido-no-inspeccionable",),                     # f2 archivo opaco
    ("muchos-links", "demasiados-links"),                  # f3 links
    ("urls-acortadas",),                                   # f4 acortadores
    ("mayusculas", "subject-mayusculas"),                  # f5 grita
    ("reply-to-diferente",),                               # f6 reply-to
    ("sin-dkim", "sin-spf", "sin-autenticacion"),          # f7 sin auth
]


def features(razones):
    txt = " ".join(razones).lower()
    return [1.0 if any(k in txt for k in grupo) else 0.0 for grupo in _FEATS]


# bootstrap: vectores claros -> 1=spam, 0=ham
_BOOT = [
    ([1, 0, 0, 0, 0, 0, 0, 0], 1),
    ([0, 0, 1, 0, 0, 0, 0, 0], 1),
    ([0, 1, 0, 0, 0, 1, 1, 1], 1),
    ([0, 0, 0, 1, 1, 1, 0, 1], 1),
    ([0, 0, 0, 0, 0, 0, 1, 1], 1),
    ([0, 0, 0, 0, 0, 0, 0, 0], 0),
    ([0, 1, 0, 0, 0, 0, 0, 0], 0),   # macro sola, sin otras senales -> ham (revisar)
    ([0, 0, 0, 0, 0, 1, 0, 0], 0),
]


class _Red:
    def __init__(self):
        self.r = None

    def _red(self):
        if self.r:
            return self.r
        if os.path.exists(PESOS):
            try:
                self.r = RedNeuronal.cargar(PESOS)
                return self.r
            except Exception:
                pass
        r = RedNeuronal([8, 6, 2], lr=0.4)
        X = [b[0] for b in _BOOT]
        Y = [[1.0 if i == b[1] else 0.0 for i in range(2)] for b in _BOOT]
        r.entrenar(X, Y, epocas=4000)
        r.guardar(PESOS)
        self.r = r
        return r

    def probs(self, f):
        try:
            return list(self._red().forward(f))
        except Exception:
            return [1.0, 0.0]

    def aprender(self, f, idx):
        r = self._red()
        y = [1.0 if i == idx else 0.0 for i in range(2)]
        r.entrenar([f], [y], epocas=30)
        r.guardar(PESOS)


_NET = _Red()


def _llm_si_duda(subject, snippet):
    """Micro-decision con LLM LOCAL, solo cuando la red empata. Timeout corto,
    salida validada, NUNCA bloquea. Devuelve 'spam'/'ham' o None."""
    try:
        import requests
        prompt = ('Responde UNA palabra (spam o ham/legitimo) para este correo. '
                  'Asunto: "%s". Texto: "%s"' % (subject[:120], (snippet or "")[:240]))
        r = requests.post(IA_URL, json={"model": IA_MODEL, "prompt": prompt,
                          "stream": False, "options": {"temperature": 0.1, "num_predict": 5}},
                          timeout=2.0)
        out = (r.json().get("response") or "").lower()
        if "spam" in out:
            return "spam"
        if "ham" in out or "leg" in out:
            return "ham"
    except Exception:
        pass
    return None


def decidir(razones, subject="", snippet="", permitir_llm=False):
    """Devuelve dict {etiqueta, confianza, fuente, features}. Determinista-primero."""
    f = features(razones)
    # 1) REGLA DURA: ejecutable o archivo opaco -> spam seguro (0 costo)
    if f[0] >= 1.0 or f[2] >= 1.0:
        return {"etiqueta": "spam", "confianza": 0.99, "fuente": "regla", "features": f}
    # 2) RED NEURONAL para los grises
    p = _NET.probs(f)
    orden = sorted(range(2), key=lambda i: p[i], reverse=True)
    idx, fuente = orden[0], "neurona"
    margen = p[orden[0]] - p[orden[1]]
    # 3) LLM SOLO SI DUDA (empate) y si se permite (apagado en el path en vivo)
    if permitir_llm and margen < 0.20:
        et = _llm_si_duda(subject, snippet)
        if et in ETIQUETAS:
            idx, fuente = ETIQUETAS.index(et), "llm"
    return {"etiqueta": ETIQUETAS[idx], "confianza": round(p[idx], 2),
            "fuente": fuente, "features": f}


def aprender(razones, etiqueta_correcta):
    if etiqueta_correcta in ETIQUETAS:
        _NET.aprender(features(razones), ETIQUETAS.index(etiqueta_correcta))


def ajuste_score(verdict):
    """Cuanto suma la neurona al score del filtro (advisory). 0 si NEURONA_PESO=0."""
    if NEURONA_PESO and verdict["etiqueta"] == "spam" and verdict["fuente"] != "regla":
        return int(round(NEURONA_PESO * verdict["confianza"]))
    return 0
