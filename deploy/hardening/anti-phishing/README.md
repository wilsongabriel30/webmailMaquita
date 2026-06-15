# Anti-phishing — capas

| Capa | Qué hace | Estado |
|---|---|---|
| Rspamd phishing | OpenPhish + PhishTank + SURBL | activo (`/etc/rspamd/local.d/phishing.conf`) |
| Safe Links — threat feeds | URLHAUS (abuse.ch) y listas de hosts maliciosos | `backend/app/safelinks/threatfeeds.py` |
| Safe Links — reescritura | Reescribe URLs entrantes para chequeo al click | `inbound_rewriter.py` |
| **Lookalike** (`safelinks/lookalike.py`) | **Detecta dominios suplantados**: typosquatting, homoglyphs/IDN, subdominios engañosos | nuevo |
| Hook IA (clasificación) | Clasificar el cuerpo como phishing con LLM local | diseño (abajo) |

## Lookalike — uso
```python
from app.safelinks import lookalike
r = lookalike.check("maqulta.org")
# {'lookalike': True, 'target': 'maquita.org', 'reason': 'typosquatting de maquita.org (distancia 1)'}
```
Detecta `maqulta.org`, `paypa1.com`, `maquita.org.secure-login.com`, homoglyphs
cirílicos, etc. Lista de dominios protegidos en `PROTECTED_DOMAINS` (propios +
marcas sensibles; ampliar por instalación). Integrar en el análisis del remitente
(From) y de URLs: si `lookalike` → subir score / avisar / cuarentena.

## Hook IA — diseño (panel ya existe, faltaba el motor)
1. Variable `OLLAMA_URL` (ya en `.env`) → modelo local de clasificación.
2. Función `classify_phishing(asunto, cuerpo) -> {veredicto, score, razones}`:
   prompt al LLM "clasifica este correo: phishing / legítimo + indicadores".
3. Invocar en la entrega (o on-demand desde el panel) y guardar el veredicto.
4. Combinar señales: Rspamd score + lookalike(From) + feeds(URLs) + IA → decisión.
> Validar el endpoint del gateway IA y el coste por correo antes de activarlo en
> el flujo de entrega (puede añadir latencia).
