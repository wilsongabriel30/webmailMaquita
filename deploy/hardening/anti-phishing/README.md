# Anti-phishing — capas

| Capa | Qué hace | Estado |
|---|---|---|
| Rspamd phishing | OpenPhish + PhishTank + SURBL | activo (`/etc/rspamd/local.d/phishing.conf`) |
| Safe Links — threat feeds | URLHAUS (abuse.ch) y listas de hosts maliciosos | `backend/app/safelinks/threatfeeds.py` |
| Safe Links — reescritura | Reescribe URLs entrantes para chequeo al click | `inbound_rewriter.py` |
| **Lookalike** (`safelinks/lookalike.py`) | Detecta dominios suplantados: typosquatting, homoglyphs/IDN, subdominios engañosos | activo |
| **Clasificador de contenido** (`safelinks/classifier.py`) | Puntúa el mensaje (remitente + asunto + cuerpo + enlaces) como phishing/suspicious/clean | activo (heurística) + hook externo opcional |

## Lookalike — uso
```python
from app.safelinks import lookalike
r = lookalike.check("maqulta.org")
# {'lookalike': True, 'target': 'maquita.org', 'reason': 'typosquatting de maquita.org (distancia 1)'}
```
Detecta `maqulta.org`, `paypa1.com`, `maquita.org.secure-login.com`, homoglyphs
cirílicos, etc. Lista de dominios protegidos en `PROTECTED_DOMAINS` (propios +
marcas sensibles; ampliar por instalación).

## Clasificador de contenido — uso
Funciona **de entrada** con heurísticas propias (no requiere servicios externos):
```python
from app.safelinks import classifier
r = classifier.score_message(
    sender='Soporte Banco <seguridad@gmaill-secure.com>',
    subject='Su cuenta sera suspendida - accion urgente',
    body='Verifique su contrasena en <a href="http://maqulta.org">bancopichincha.com</a>')
# {'label': 'phishing', 'score': 100, 'reasons': [...], 'source': 'heuristica'}
```
Señales (capa local): suplantación del remitente (display-name vs dominio),
dominio remitente lookalike, urgencia + cosecha de credenciales, estafa de
premio/herencia/lotería, texto de enlace que no coincide con el destino real,
y veredicto de los URLs (reusa `checker` + `lookalike`).
Umbrales: `score >= 70` → phishing, `>= 40` → suspicious, resto clean.

### Capa externa opcional
Suma un veredicto adicional a la heurística. **Fail-open**: si no está configurada
o falla/expira, se usa solo la heurística local; nunca bloquea el flujo de correo.
El `score` externo se interpreta como **riesgo de phishing** (si el veredicto
externo es `clean`, su riesgo es 0); se toma el mayor riesgo y se recalcula el label.
Dos modos según `PHISH_CLASSIFIER_KIND`:

**a) Modo `gateway` (recomendado aquí)** — usa el gateway de modelos propio,
reutilizando `OLLAMA_URL` / `IA_API_KEY` ya configurados para el resto del webmail.
```
PHISH_CLASSIFIER_KIND=gateway
PHISH_CLASSIFIER_MODEL=qwen2.5:7b   # modelo a pedir al gateway
PHISH_CLASSIFIER_TIMEOUT=8          # segundos; si expira → fail-open
```
Llama a `POST {OLLAMA_URL}/api/v1/ia/generate` (header `X-API-Key: IA_API_KEY`)
y parsea del modelo un JSON `{label, score, reasons}`.

**b) Modo contrato directo** — cualquier servicio HTTP que cumpla el contrato:
```
PHISH_CLASSIFIER_KIND=               # vacío = modo contrato
PHISH_CLASSIFIER_URL=                # endpoint HTTP (vacío = solo heurística)
PHISH_CLASSIFIER_KEY=                # opcional: Authorization: Bearer
PHISH_CLASSIFIER_TIMEOUT=4
```
```
POST  ->  {sender, subject, body, urls, signals}
RESP  <-  {label: "phishing|suspicious|clean", score: 0-100, reasons: [str]}
```
> Todas las variables van en el `.env` (gitignored — nunca en código). La heurística
> local no añade latencia de red; la capa externa es para precisión adicional. Validar
> coste/latencia por correo antes de invocarla en el flujo de entrega masivo.

## Integración (decisión combinada)
Combinar señales en la entrega o on-demand desde el panel:
`Rspamd score + lookalike(From) + classifier.score_message(...) → decisión`
(avisar / etiquetar / cuarentena según el puntaje).
