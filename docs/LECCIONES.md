# Lecciones (registro vivo)

Cada entrada: qué pasó, qué faltó, qué regla queda. Se añade cuando algo nos cuesta; no se borra.

## 2026-09-07 — «Activo» no es «sano» (N-15)
- **Qué pasó:** tras rotar secretos el 03/09, la clave del webmail hacia la pasarela de IA dejó de
  coincidir. Smart Reply, resumen y asuntos devolvieron 502 durante cuatro días. Ningún servicio
  estaba caído; ninguna alerta saltó; nadie lo notó hasta preparar una prueba.
- **Qué faltó:** vigilar que las integraciones con clave compartida *funcionan*, no solo que los
  servicios están activos.
- **Regla:** cada integración con secreto compartido tiene una sonda horaria sin efectos
  secundarios (`deploy/hardening/vigilar-integraciones.py`) y al rotar un secreto se corre
  `--probar` antes de dar la rotación por terminada.

## 2026-09-07 — Retirar funcionalidad exige saber quién la va a usar (D-9)
- **Qué pasó:** Z-Push (ActiveSync) se retiró con evidencia de uso cero (registros de dos semanas,
  cero dispositivos) y un informe de vulnerabilidades. Horas después se corrigió: la dirección
  ejecutiva y las gerencias trabajan en Outlook de escritorio, que solo sincroniza calendario y
  contactos por ActiveSync. Sin Z-Push, el día del corte habrían visto el calendario vacío.
- **Qué faltó:** confirmar con quien conoce a los usuarios **quién la va a usar tras el
  lanzamiento**. Los registros de una plataforma sin usuarios solo dicen quién la usa hoy.
- **Regla:** una decisión de retirar funcionalidad requiere dos confirmaciones explícitas: uso
  actual (datos) y uso previsto (dirección). Sin la segunda, se endurece, no se retira.
