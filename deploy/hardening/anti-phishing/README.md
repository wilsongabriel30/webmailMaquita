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

### Capa externa opcional (agnóstica de proveedor)
Si se define `PHISH_CLASSIFIER_URL`, el clasificador hace POST de las señales a
ese endpoint y **fusiona** su veredicto (toma el mayor puntaje). Es **fail-open**:
si el endpoint no está configurado o falla, se usa solo la heurística local;
nunca bloquea el flujo de correo.

Variables de entorno (en el `.env`, gitignored — nunca en código):
```
PHISH_CLASSIFIER_URL=        # endpoint HTTP del clasificador (vacío = solo heurística)
PHISH_CLASSIFIER_KEY=        # opcional: enviado como Authorization: Bearer
PHISH_CLASSIFIER_TIMEOUT=4   # segundos; si expira → fail-open
```
Contrato del endpoint (cualquier servicio que lo cumpla sirve: modelo propio
servido por HTTP, gateway interno, etc.):
```
POST  ->  {sender, subject, body, urls, signals}
RESP  <-  {label: "phishing|suspicious|clean", score: 0-100, reasons: [str]}
```

> **Antes de activar la capa externa en el flujo de entrega**: validar el endpoint
> y el coste/latencia por correo. La heurística local no añade latencia de red y
> ya cubre los casos típicos; la capa externa es para precisión adicional.

## Integración (decisión combinada)
Combinar señales en la entrega o on-demand desde el panel:
`Rspamd score + lookalike(From) + classifier.score_message(...) → decisión`
(avisar / etiquetar / cuarentena según el puntaje).
