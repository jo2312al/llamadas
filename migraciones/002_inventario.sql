CREATE TABLE IF NOT EXISTS inventario_habitaciones (
    tipo TEXT PRIMARY KEY CHECK (tipo IN ('doble', 'king', 'suite')),
    cantidad_total INTEGER NOT NULL CHECK (cantidad_total >= 0)
);

INSERT INTO inventario_habitaciones (tipo, cantidad_total) VALUES
    ('doble', 15),
    ('king', 5),
    ('suite', 5)
ON CONFLICT(tipo) DO UPDATE SET cantidad_total = excluded.cantidad_total;

CREATE TABLE IF NOT EXISTS bloqueos_inventario (
    identificador_bloqueo TEXT PRIMARY KEY,
    tipo TEXT NOT NULL REFERENCES inventario_habitaciones(tipo),
    fecha_entrada TEXT NOT NULL,
    fecha_salida TEXT NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    estado TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo', 'liberado')),
    referencia TEXT,
    fecha_creacion TEXT NOT NULL,
    CHECK (fecha_salida > fecha_entrada)
);

CREATE INDEX IF NOT EXISTS idx_bloqueos_disponibilidad
ON bloqueos_inventario(tipo, estado, fecha_entrada, fecha_salida);
