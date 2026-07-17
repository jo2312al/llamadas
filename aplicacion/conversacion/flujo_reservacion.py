"""Recopilación determinística de datos y consulta real de disponibilidad."""

import re
import unicodedata
from datetime import date

from aplicacion.conversacion.maquina_estados import transicionar
from aplicacion.disponibilidad.servicio import ServicioDisponibilidad, normalizar_tipo
from aplicacion.modelos.conversacion import EstadoConversacion, SesionLlamada

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}
NUMEROS = {
    "uno": 1,
    "una": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
}


class FlujoReservacion:
    """Solicita un dato por turno y consulta inventario autorizado."""

    def __init__(self, disponibilidad: ServicioDisponibilidad) -> None:
        self.disponibilidad = disponibilidad

    def procesar(self, sesion: SesionLlamada, mensaje: str) -> tuple[str, str]:
        """Actualiza la sesión y devuelve intención y siguiente pregunta."""
        if sesion.estado_actual == EstadoConversacion.BIENVENIDA:
            transicionar(sesion, EstadoConversacion.IDENTIFICAR_INTENCION)
            intencion, respuesta = clasificar_intencion(mensaje)
            sesion.intencion = intencion
            if intencion != "reservacion":
                return intencion, respuesta
            transicionar(sesion, EstadoConversacion.RECOPILAR_DATOS)
            return intencion, "Con gusto. ¿Para qué fecha desea reservar?"

        if sesion.intencion != "reservacion":
            return clasificar_intencion(mensaje)

        datos = sesion.datos
        if datos.fecha_entrada is None:
            entrada = extraer_fecha(mensaje)
            if entrada is None:
                return "reservacion", "No comprendí la fecha de entrada. Dígala con día, mes y año."
            datos.fecha_entrada = entrada
            return "reservacion", "¿Qué día realizará su salida?"

        if datos.fecha_salida is None:
            salida = extraer_fecha(mensaje, referencia=datos.fecha_entrada)
            if salida is None or salida <= datos.fecha_entrada:
                return "reservacion", "La salida debe ser posterior a la entrada. ¿Qué fecha será?"
            datos.fecha_salida = salida
            datos.numero_noches = (salida - datos.fecha_entrada).days
            return "reservacion", "¿Prefiere habitación doble, king o suite?"

        if datos.tipo_habitacion is None:
            try:
                datos.tipo_habitacion = normalizar_tipo(extraer_tipo(mensaje)).value
            except ValueError:
                return "reservacion", "Indique doble, king o suite."
            return "reservacion", "¿Cuántos adultos se hospedarán?"

        if datos.numero_adultos is None:
            adultos = extraer_numero(mensaje)
            if adultos is None or not 1 <= adultos <= 20:
                return "reservacion", "Indique cuántos adultos, entre uno y veinte."
            datos.numero_adultos = adultos
            return "reservacion", self._consultar_y_responder(sesion)

        return "reservacion", self._consultar_y_responder(sesion)

    def _consultar_y_responder(self, sesion: SesionLlamada) -> str:
        datos = sesion.datos
        assert datos.fecha_entrada and datos.fecha_salida and datos.tipo_habitacion
        if sesion.estado_actual == EstadoConversacion.RECOPILAR_DATOS:
            transicionar(sesion, EstadoConversacion.VALIDAR_DATOS)
            transicionar(sesion, EstadoConversacion.CONSULTAR_DISPONIBILIDAD)
        resultado = {
            item.tipo.value: item
            for item in self.disponibilidad.consultar(datos.fecha_entrada, datos.fecha_salida)
        }[datos.tipo_habitacion]
        if sesion.estado_actual == EstadoConversacion.CONSULTAR_DISPONIBILIDAD:
            transicionar(sesion, EstadoConversacion.PRESENTAR_OPCIONES)
        if resultado.disponibles < datos.numero_habitaciones:
            return f"No hay habitaciones {datos.tipo_habitacion} disponibles en esas fechas."
        return (
            f"Hay {resultado.disponibles} habitaciones {datos.tipo_habitacion} disponibles. "
            "¿Desea continuar con la solicitud?"
        )


def clasificar_intencion(mensaje: str) -> tuple[str, str]:
    """Clasifica la intención inicial mediante palabras completas."""
    palabras = set(re.findall(r"\w+", mensaje.casefold()))
    if palabras.intersection({"recepción", "humano", "persona"}):
        return "transferencia", "Claro. Le comunicaré con recepción."
    if any(palabra.startswith(("reserv", "habitaci", "hosped")) for palabra in palabras):
        return "reservacion", "Con gusto. ¿Para qué fecha desea reservar?"
    return "informacion", "Con gusto. ¿Qué información del hotel necesita?"


def extraer_fecha(mensaje: str, referencia: date | None = None) -> date | None:
    """Extrae fechas ISO, numéricas o españolas con año explícito."""
    texto = quitar_acentos(mensaje.casefold())
    if coincidencia := re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", texto):
        valores = map(int, coincidencia.groups())
        return _crear_fecha(*valores)
    if coincidencia := re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", texto):
        dia, mes, ano = map(int, coincidencia.groups())
        return _crear_fecha(ano, mes, dia)
    meses = "|".join(MESES)
    if coincidencia := re.search(
        rf"\b(\d{{1,2}})\s+(?:de\s+)?({meses})(?:\s+(?:de\s+)?(20\d{{2}}))?\b", texto
    ):
        dia = int(coincidencia.group(1))
        mes = MESES[coincidencia.group(2)]
        ano = int(coincidencia.group(3)) if coincidencia.group(3) else None
        if ano is None and referencia:
            ano = referencia.year + (mes < referencia.month)
        if ano is None:
            return None
        return _crear_fecha(ano, mes, dia)
    return None


def extraer_tipo(mensaje: str) -> str:
    palabras = set(re.findall(r"\w+", mensaje.casefold()))
    for tipo in ("doble", "dobles", "king", "suite", "suites"):
        if tipo in palabras:
            return tipo
    return mensaje


def extraer_numero(mensaje: str) -> int | None:
    if coincidencia := re.search(r"\b(\d{1,2})\b", mensaje):
        return int(coincidencia.group(1))
    palabras = set(re.findall(r"\w+", quitar_acentos(mensaje.casefold())))
    return next((valor for palabra, valor in NUMEROS.items() if palabra in palabras), None)


def quitar_acentos(texto: str) -> str:
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caracter) != "Mn"
    )


def _crear_fecha(ano: int, mes: int, dia: int) -> date | None:
    try:
        return date(ano, mes, dia)
    except ValueError:
        return None
