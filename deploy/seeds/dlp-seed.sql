-- DLP seed inicial (Ecuador / LatAm). Idempotente.
-- Los detectores de patrón (cédula mod10, RUC, tarjeta/Luhn, IBAN, cuenta) ya
-- están en código (backend/app/dlp/detectors.py) y validan de verdad. Este seed
-- deja el DLP HABILITADO con esas reglas + un set inicial de palabras clave.

INSERT INTO dlp_config (id, enabled, default_action, rules)
VALUES (1, true, 'warn',
 '{"cedula":{"enabled":true,"action":null},"ruc":{"enabled":true,"action":null},"tarjeta":{"enabled":true,"action":null},"iban":{"enabled":true,"action":null},"cuenta":{"enabled":true,"action":null},"keyword":{"enabled":true,"action":null}}'::jsonb)
ON CONFLICT (id) DO UPDATE SET enabled=true, rules=EXCLUDED.rules, updated_at=NOW();

INSERT INTO dlp_keywords (term)
SELECT t FROM (VALUES
 ('confidencial'),('estrictamente confidencial'),('no divulgar'),('uso interno'),
 ('datos personales'),('historia clínica'),('número de tarjeta'),('clave de acceso'),
 ('contraseña'),('estado de cuenta'),('rol de pagos'),('comprobante de pago')
) AS s(t)
WHERE NOT EXISTS (SELECT 1 FROM dlp_keywords k WHERE lower(k.term)=lower(s.t));
