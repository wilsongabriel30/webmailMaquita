-- Primer punto de acceso wifi de Maquita central como ancla (BSSID reportado por el A53 el 22/09/2026).
-- Coordenadas del GPS del NTP, radio 30 m. Los demás puntos de acceso se cargan desde el panel.
INSERT INTO disp_anclas_red (tipo, valor, sede, nombre, lat, lon, radio_m) VALUES
  ('bssid', '74:ac:b9:6a:b8:0f', 'Maquita central', 'Punto de acceso «MAQUITA CENTRAL» (oficina)', -0.2772, -78.5464, 30)
ON CONFLICT (tipo, valor) DO NOTHING;
