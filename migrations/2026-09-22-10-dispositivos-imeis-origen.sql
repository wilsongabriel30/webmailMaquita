-- AE-12 (22/09/2026): de cada IMEI se guarda su origen ({"3547…": "sistema"|"persona"|"tecnologia"}) para
-- que el panel distinga los leídos por Android (control completo, fiables) de los escritos a mano, y
-- un IMEI que ya pertenece a otro equipo registrado se rechaza.
ALTER TABLE disp_equipos ADD COLUMN IF NOT EXISTS imeis_origen JSONB NOT NULL DEFAULT '{}'::jsonb;
