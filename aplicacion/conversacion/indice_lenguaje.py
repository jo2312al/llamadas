"""Índice local, precalculado y seguro para lenguaje frecuente del hotel."""

import re
import unicodedata
from functools import lru_cache


@lru_cache(maxsize=2048)
def normalizar_texto(texto: str) -> tuple[str, frozenset[str]]:
    """Normaliza una frase una vez y conserva el resultado para llamadas repetidas."""
    limpio = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto.casefold())
        if unicodedata.category(caracter) != "Mn"
    )
    limpio = " ".join(re.findall(r"[a-z0-9]+", limpio))
    return limpio, frozenset(limpio.split())


RAICES_RESERVACION = (
    "reserv",
    "habitaci",
    "hosped",
    "aloj",
    "estancia",
    "cuarto",
    "dormir",
    "quedar",
    "apartar",
)

TIPOS_HABITACION = {
    "doble": frozenset({"doble", "dobles", "matrimonial"}),
    "king": frozenset({"king", "cama king", "cama grande"}),
    "suite": frozenset({"suite", "suites", "suit"}),
}

AFIRMACIONES = frozenset(
    {"si", "confirmo", "continuar", "adelante", "correcto", "de acuerdo", "esta bien"}
)
NEGACIONES = frozenset({"no", "negativo", "no gracias", "para nada"})

PREGUNTAS_FRECUENTES = (
    (frozenset({"wifi", "internet"}), "Sí contamos con wifi."),
    (
        frozenset({"estacionamiento", "parking", "carro", "auto"}),
        "Sí contamos con estacionamiento sin costo.",
    ),
    (frozenset({"alberca", "piscina"}), "No contamos con alberca."),
    (
        frozenset({"desayuno", "desayunos"}),
        "El desayuno no está incluido bajo ninguna modalidad.",
    ),
    (
        frozenset({"restaurante", "comida", "comedor"}),
        "Tenemos restaurante y servicio a la habitación, de 7 a 11 de la mañana "
        "y de 6 a 10 de la noche.",
    ),
    (frozenset({"alcohol", "cerveza", "vino"}), "No vendemos bebidas alcohólicas."),
    (frozenset({"elevador", "ascensor"}), "Sí contamos con elevador."),
    (
        frozenset({"factura", "facturar", "facturacion"}),
        "Sí emitimos facturas. Comuníquese con recepción o ventas de lunes a sábado, "
        "de 7 de la mañana a 11 de la noche.",
    ),
    (
        frozenset({"direccion", "ubicacion", "domicilio", "donde"}),
        "Estamos en Andrés Sánchez Magallanes 910, colonia Centro, Villahermosa, Tabasco.",
    ),
    (
        frozenset({"tarjeta", "efectivo", "pago", "pagar"}),
        "Aceptamos efectivo y tarjeta. El pago se realiza en recepción.",
    ),
)


def contiene_expresion(texto: str, expresiones: frozenset[str]) -> bool:
    normalizado, palabras = normalizar_texto(texto)
    return any(
        expresion in palabras if " " not in expresion else expresion in normalizado
        for expresion in expresiones
    )


def es_solicitud_reservacion(texto: str) -> bool:
    _normalizado, palabras = normalizar_texto(texto)
    return any(palabra.startswith(RAICES_RESERVACION) for palabra in palabras)


def buscar_tipo_habitacion(texto: str) -> str | None:
    for tipo, expresiones in TIPOS_HABITACION.items():
        if contiene_expresion(texto, expresiones):
            return tipo
    return None


def buscar_respuesta_frecuente(texto: str) -> str | None:
    for expresiones, respuesta in PREGUNTAS_FRECUENTES:
        if contiene_expresion(texto, expresiones):
            return respuesta
    return None


def es_afirmacion(texto: str) -> bool:
    return contiene_expresion(texto, AFIRMACIONES)


def es_negacion(texto: str) -> bool:
    return contiene_expresion(texto, NEGACIONES)
