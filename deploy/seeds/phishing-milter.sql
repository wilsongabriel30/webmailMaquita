-- Anti-phishing en el milter de entrega (default OFF, no afecta la entrega).
-- phishing_milter_mode: 'off' | 'header' (agrega cabecera X-Maquita-Phishing).
-- phishing_milter_external: si true, escala al modelo (gateway) en la banda
-- incierta [30,70); requiere OLLAMA_URL/IA_API_KEY. Por latencia, dejar en false
-- para correo masivo y usar el modelo via el endpoint on-demand.
ALTER TABLE safelinks_config ADD COLUMN IF NOT EXISTS phishing_milter_mode text NOT NULL DEFAULT 'off';
ALTER TABLE safelinks_config ADD COLUMN IF NOT EXISTS phishing_milter_external boolean NOT NULL DEFAULT false;
