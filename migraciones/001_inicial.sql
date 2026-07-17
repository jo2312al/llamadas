CREATE TABLE IF NOT EXISTS solicitudes_reservacion (
    identificador_solicitud TEXT PRIMARY KEY,
    identificador_llamada TEXT NOT NULL,
    fecha_creacion TEXT NOT NULL,
    estado TEXT NOT NULL,
    datos_json TEXT NOT NULL,
    resumen_conversacion TEXT NOT NULL DEFAULT '',
    nivel_confianza REAL NOT NULL DEFAULT 0 CHECK (nivel_confianza BETWEEN 0 AND 1),
    requiere_revision INTEGER NOT NULL DEFAULT 0,
    motivo_revision TEXT,
    total_estimado REAL,
    moneda TEXT NOT NULL DEFAULT 'MXN'
);
CREATE INDEX IF NOT EXISTS idx_solicitudes_llamada
ON solicitudes_reservacion(identificador_llamada);

