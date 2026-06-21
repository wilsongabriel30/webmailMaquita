CREATE TABLE IF NOT EXISTS conditional_access_policies (
  id serial PRIMARY KEY,
  name varchar NOT NULL,
  condition varchar NOT NULL,
  action varchar NOT NULL,
  enabled boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);
INSERT INTO conditional_access_policies (name, condition, action, enabled)
SELECT * FROM (VALUES
  ('Bloquear logins de riesgo alto', 'riesgo_alto', 'bloquear', false),
  ('Alertar pais no confiable', 'pais_no_confiable', 'alertar', false),
  ('Bloquear viaje imposible', 'viaje_imposible', 'bloquear', false)
) v(name,condition,action,enabled)
WHERE NOT EXISTS (SELECT 1 FROM conditional_access_policies);
