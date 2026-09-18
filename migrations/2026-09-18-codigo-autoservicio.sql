-- Código de enrolamiento autoservicio: cada usuario genera desde su Configuración un código para
-- activar la app en su propio teléfono (modo limitado, queda como custodio él mismo).
ALTER TABLE disp_codigos
    ADD COLUMN IF NOT EXISTS custodio_email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS autoservicio   BOOLEAN NOT NULL DEFAULT FALSE;
