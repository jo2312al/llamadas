"""Recopilación determinística de datos y consulta real de disponibilidad."""

import re
import unicodedata
from collections import Counter
from datetime import date, time, timedelta

from aplicacion.base_datos.repositorio_reservaciones import guardar_solicitud
from aplicacion.conversacion.maquina_estados import transicionar
from aplicacion.disponibilidad.servicio import ServicioDisponibilidad, normalizar_tipo
from aplicacion.integraciones.api_reservas import ClienteApiReservas, ErrorApiReservas
from aplicacion.modelos.conversacion import EstadoConversacion, SesionLlamada
from aplicacion.modelos.reservacion import (
    DetalleHabitacion,
    EstadoSolicitud,
    SolicitudReservacion,
)

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
    "cero": 0,
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
DIAS_HABLADOS = {
    **NUMEROS,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciseis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintiuno": 21,
    "veintiun": 21,
    "veintidos": 22,
    "veintitres": 23,
    "veinticuatro": 24,
    "veinticinco": 25,
    "veintiseis": 26,
    "veintisiete": 27,
    "veintiocho": 28,
    "veintinueve": 29,
    "treinta": 30,
    "treinta y uno": 31,
}


class FlujoReservacion:
    """Solicita un dato por turno y consulta inventario autorizado."""

    def __init__(
        self,
        disponibilidad: ServicioDisponibilidad,
        api_reservas: ClienteApiReservas | None = None,
    ) -> None:
        self.disponibilidad = disponibilidad
        self.api_reservas = api_reservas

    def procesar(self, sesion: SesionLlamada, mensaje: str) -> tuple[str, str]:
        """Actualiza la sesión y devuelve intención y siguiente pregunta."""
        if sesion.estado_actual == EstadoConversacion.BIENVENIDA:
            transicionar(sesion, EstadoConversacion.IDENTIFICAR_INTENCION)
            intencion, respuesta = clasificar_intencion(mensaje)
            sesion.intencion = intencion
            if intencion != "reservacion":
                return intencion, respuesta
            transicionar(sesion, EstadoConversacion.RECOPILAR_DATOS)
            return intencion, "Con gusto. ¿Cuál es su fecha de entrada?"

        if sesion.intencion != "reservacion":
            return clasificar_intencion(mensaje)

        datos = sesion.datos
        if sesion.estado_actual == EstadoConversacion.PRESENTAR_OPCIONES:
            cambio = detectar_cambio(mensaje)
            if cambio:
                transicionar(sesion, EstadoConversacion.RECOPILAR_DATOS)
                return "reservacion", self._reiniciar_dato(sesion, cambio)
            if es_afirmativo(mensaje):
                transicionar(sesion, EstadoConversacion.CONFIRMAR_DATOS)
                return "reservacion", "Para registrar la solicitud, dígame su nombre completo."
            if es_negativo(mensaje) or desea_cancelar(mensaje):
                transicionar(sesion, EstadoConversacion.FINALIZAR)
                return (
                    "reservacion",
                    "De acuerdo, no registraré la solicitud. Gracias por llamar.",
                )
            return (
                "reservacion",
                "Diga continuar, cambiar fechas, cambiar habitación, "
                "cambiar huéspedes o cancelar.",
            )

        if sesion.estado_actual == EstadoConversacion.CONFIRMAR_DATOS:
            return "reservacion", self._recopilar_contacto(sesion, mensaje)

        if datos.fecha_entrada is None:
            entrada = extraer_fecha(mensaje)
            if entrada is None:
                return (
                    "reservacion",
                    "No comprendí la fecha de entrada. Puede decir hoy, mañana o el día y mes.",
                )
            datos.fecha_entrada = entrada
            return "reservacion", "¿Cuántas noches desea hospedarse?"

        if datos.numero_noches is None:
            noches = extraer_numero(mensaje)
            if noches is None or noches < 1:
                return "reservacion", "Indique una cantidad de noches mayor a cero."
            datos.numero_noches = noches
            datos.fecha_salida = datos.fecha_entrada.fromordinal(
                datos.fecha_entrada.toordinal() + noches
            )
            return "reservacion", "¿Cuántas habitaciones desea reservar? El máximo es cuatro."

        if datos.numero_habitaciones is None:
            cantidad = extraer_numero(mensaje)
            if cantidad is None or not 1 <= cantidad <= 4:
                return "reservacion", "Indique entre una y cuatro habitaciones."
            datos.numero_habitaciones = cantidad
            return "reservacion", "¿Qué tipo desea para la habitación uno: doble, king o suite?"

        if len(datos.habitaciones) < datos.numero_habitaciones:
            respuesta = self._recopilar_habitacion(sesion, mensaje)
            if respuesta:
                return "reservacion", respuesta

        if datos.hora_llegada is None:
            llegada = extraer_hora(mensaje)
            if llegada is None:
                return (
                    "reservacion",
                    "Indique su hora aproximada de llegada, por ejemplo 6 de la tarde.",
                )
            datos.hora_llegada = llegada
            return "reservacion", self._consultar_y_responder(sesion)

        return "reservacion", self._consultar_y_responder(sesion)

    def _recopilar_habitacion(self, sesion: SesionLlamada, mensaje: str) -> str | None:
        datos = sesion.datos
        numero = len(datos.habitaciones) + 1
        if sesion.tipo_habitacion_actual is None:
            try:
                sesion.tipo_habitacion_actual = normalizar_tipo(extraer_tipo(mensaje)).value
            except ValueError:
                return "Indique doble, king o suite."
            return f"¿Cuántos adultos ocuparán la habitación {numero}?"
        if sesion.adultos_habitacion_actual is None:
            adultos = extraer_numero(mensaje)
            limite = 2 if sesion.tipo_habitacion_actual == "king" else 4
            if adultos is None or not 1 <= adultos <= limite:
                return f"Esa habitación admite entre uno y {limite} adultos."
            sesion.adultos_habitacion_actual = adultos
            return f"¿Cuántos niños de cero a once años ocuparán la habitación {numero}?"
        if sesion.menores_habitacion_actual is None:
            menores = extraer_numero(mensaje)
            if menores is None or menores < 0:
                return "Indique cuántos niños se hospedarán, incluso si son cero."
            if sesion.adultos_habitacion_actual + menores > 4:
                return "La ocupación total no puede superar cuatro personas. Indique menos niños."
            sesion.menores_habitacion_actual = menores
            if menores:
                return "Diga las edades de los niños."
            return self._completar_habitacion(sesion, [])
        edades = extraer_numeros(mensaje)
        if len(edades) != sesion.menores_habitacion_actual or any(edad > 11 for edad in edades):
            return "Indique una edad de cero a once años por cada niño."
        return self._completar_habitacion(sesion, edades)

    def _completar_habitacion(self, sesion: SesionLlamada, edades: list[int]) -> str | None:
        datos = sesion.datos
        assert sesion.tipo_habitacion_actual and sesion.adultos_habitacion_actual
        detalle = DetalleHabitacion(
            tipo=sesion.tipo_habitacion_actual,
            adultos=sesion.adultos_habitacion_actual,
            edades_menores=edades,
            precio_noche=calcular_precio_noche(
                sesion.tipo_habitacion_actual, sesion.adultos_habitacion_actual
            ),
        )
        datos.habitaciones.append(detalle)
        sesion.tipo_habitacion_actual = None
        sesion.adultos_habitacion_actual = None
        sesion.menores_habitacion_actual = None
        if len(datos.habitaciones) < (datos.numero_habitaciones or 0):
            siguiente = len(datos.habitaciones) + 1
            return f"¿Qué tipo desea para la habitación {siguiente}: doble, king o suite?"
        datos.numero_adultos = sum(item.adultos for item in datos.habitaciones)
        datos.numero_menores = sum(len(item.edades_menores) for item in datos.habitaciones)
        datos.edades_menores = [edad for item in datos.habitaciones for edad in item.edades_menores]
        return "¿A qué hora calcula llegar al hotel?"

    @staticmethod
    def _reiniciar_dato(sesion: SesionLlamada, cambio: str) -> str:
        datos = sesion.datos
        if cambio == "fechas":
            datos.fecha_entrada = None
            datos.fecha_salida = None
            datos.numero_noches = None
            return "Claro. ¿Cuál será la nueva fecha de entrada?"
        if cambio == "habitacion":
            datos.habitaciones.clear()
            sesion.tipo_habitacion_actual = None
            sesion.adultos_habitacion_actual = None
            sesion.menores_habitacion_actual = None
            return "Claro. ¿Qué tipo desea para la habitación uno: doble, king o suite?"
        datos.habitaciones.clear()
        sesion.tipo_habitacion_actual = None
        sesion.adultos_habitacion_actual = None
        sesion.menores_habitacion_actual = None
        return "Claro. Volvamos a distribuir los huéspedes. ¿Qué tipo desea para la habitación uno?"

    def _recopilar_contacto(self, sesion: SesionLlamada, mensaje: str) -> str:
        datos = sesion.datos
        if datos.nombre_completo is None:
            nombre = " ".join(mensaje.strip().split())
            if len(nombre) < 5 or any(caracter.isdigit() for caracter in nombre):
                return "Dígame su nombre y apellidos, por favor."
            datos.nombre_completo = nombre[:120]
            if datos.telefono:
                return self._finalizar_contacto(sesion)
            return "¿Cuál es su número de teléfono?"
        if datos.telefono is None:
            telefono = "".join(re.findall(r"\d", mensaje))
            if not 10 <= len(telefono) <= 15:
                return "Indique un teléfono de entre diez y quince dígitos."
            datos.telefono = telefono
            datos.consentimiento_contacto = True
            return self._finalizar_contacto(sesion)
        return "Su solicitud ya fue registrada."

    def _finalizar_contacto(self, sesion: SesionLlamada) -> str:
        try:
            return self._registrar_y_enviar(sesion)
        except ValueError:
            sesion.datos.consentimiento_contacto = None
            return (
                "La disponibilidad cambió antes de registrar. " "Recepción revisará otras opciones."
            )

    def _registrar_y_enviar(self, sesion: SesionLlamada) -> str:
        entrada = sesion.datos.fecha_entrada
        salida = sesion.datos.fecha_salida
        if not entrada or not salida or not sesion.datos.habitaciones:
            raise ValueError("Faltan datos para bloquear inventario")
        solicitud = SolicitudReservacion(
            identificador_llamada=sesion.identificador_llamada,
            datos=sesion.datos,
            resumen_conversacion="Solicitud recopilada por agente telefónico.",
            nivel_confianza=1,
            estado=EstadoSolicitud.CONFIRMADA,
            total_estimado=calcular_total(sesion.datos),
        )
        self.disponibilidad.bloquear_varios(
            dict(Counter(item.tipo for item in sesion.datos.habitaciones)),
            entrada,
            salida,
            solicitud.identificador_solicitud,
        )
        transicionar(sesion, EstadoConversacion.GUARDAR_SOLICITUD)
        guardar_solicitud(self.disponibilidad.conexion, solicitud)
        sesion.identificador_solicitud = solicitud.identificador_solicitud
        transicionar(sesion, EstadoConversacion.ENVIAR_NOTIFICACION)
        if self.api_reservas:
            try:
                self.api_reservas.enviar(solicitud)
            except ErrorApiReservas:
                sesion.requiere_revision = True
                sesion.motivo_revision = "Entrega pendiente a API de reservas"
                self.disponibilidad.conexion.execute(
                    """UPDATE solicitudes_reservacion
                       SET requiere_revision = 1, motivo_revision = ?
                       WHERE identificador_solicitud = ?""",
                    (sesion.motivo_revision, solicitud.identificador_solicitud),
                )
                self.disponibilidad.conexion.commit()
        transicionar(sesion, EstadoConversacion.FINALIZAR)
        if sesion.requiere_revision:
            return "Su solicitud quedó registrada y será revisada por recepción."
        return "Su solicitud fue registrada correctamente. El hotel le contactará para confirmarla."

    def _consultar_y_responder(self, sesion: SesionLlamada) -> str:
        datos = sesion.datos
        assert datos.fecha_entrada and datos.fecha_salida and datos.habitaciones
        if sesion.estado_actual == EstadoConversacion.RECOPILAR_DATOS:
            transicionar(sesion, EstadoConversacion.VALIDAR_DATOS)
            transicionar(sesion, EstadoConversacion.CONSULTAR_DISPONIBILIDAD)
        resultados = {
            item.tipo.value: item
            for item in self.disponibilidad.consultar(datos.fecha_entrada, datos.fecha_salida)
        }
        if sesion.estado_actual == EstadoConversacion.CONSULTAR_DISPONIBILIDAD:
            transicionar(sesion, EstadoConversacion.PRESENTAR_OPCIONES)
        cantidades = Counter(item.tipo for item in datos.habitaciones)
        faltantes = [
            tipo for tipo, cantidad in cantidades.items() if resultados[tipo].disponibles < cantidad
        ]
        if faltantes:
            return "No hay disponibilidad para toda la reservación solicitada."
        total = calcular_total(datos)
        anticipo = (
            " La llegada anticipada cuesta 200 pesos y depende de recepción."
            if datos.hora_llegada and datos.hora_llegada < time(15, 0)
            else ""
        )
        return (
            f"Sí hay disponibilidad. El total es de {total} pesos, IVA incluido."
            f"{anticipo} ¿Desea confirmar la reservación?"
        )


def clasificar_intencion(mensaje: str) -> tuple[str, str]:
    """Clasifica solicitudes iniciales comunes, incluso si llegan abreviadas."""
    texto = quitar_acentos(mensaje.casefold())
    palabras = set(re.findall(r"\w+", texto))
    if palabras.intersection({"recepcion", "humano", "persona"}):
        return "transferencia", "Claro. Le comunicaré con recepción."
    raices_reservacion = (
        "reserv",
        "habitaci",
        "hosped",
        "aloj",
        "estancia",
        "cuarto",
        "dormir",
        "quedar",
    )
    if any(palabra.startswith(raices_reservacion) for palabra in palabras):
        return "reservacion", "Con gusto. ¿Para qué fecha desea reservar?"
    return "informacion", "Con gusto. ¿Qué información del hotel necesita?"


def extraer_fecha(mensaje: str, referencia: date | None = None) -> date | None:
    """Extrae fechas absolutas o relativas y completa el año cuando se omite."""
    texto = quitar_acentos(mensaje.casefold())
    referencia = referencia or date.today()
    if re.search(r"\bpasado manana\b", texto):
        return referencia + timedelta(days=2)
    if re.search(r"\bmanana\b", texto):
        return referencia + timedelta(days=1)
    if re.search(r"\bhoy\b", texto):
        return referencia
    if coincidencia := re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", texto):
        valores = map(int, coincidencia.groups())
        return _crear_fecha(*valores)
    if coincidencia := re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", texto):
        dia, mes, ano = map(int, coincidencia.groups())
        return _crear_fecha(ano, mes, dia)
    if coincidencia := re.search(r"\b(\d{1,2})[/-](\d{1,2})\b", texto):
        dia, mes = map(int, coincidencia.groups())
        return _fecha_sin_ano(dia, mes, referencia)
    meses = "|".join(MESES)
    dias = "|".join(sorted(DIAS_HABLADOS, key=len, reverse=True))
    if coincidencia := re.search(
        rf"\b(\d{{1,2}}|{dias})\s+(?:de\s+)?({meses})(?:\s+(?:de\s+)?(20\d{{2}}))?\b",
        texto,
    ):
        valor_dia = coincidencia.group(1)
        dia = int(valor_dia) if valor_dia.isdigit() else DIAS_HABLADOS[valor_dia]
        mes = MESES[coincidencia.group(2)]
        ano = int(coincidencia.group(3)) if coincidencia.group(3) else None
        if ano is None:
            return _fecha_sin_ano(dia, mes, referencia)
        return _crear_fecha(ano, mes, dia)
    return None


def _fecha_sin_ano(dia: int, mes: int, referencia: date) -> date | None:
    """Elige la siguiente ocurrencia válida de un día y mes."""
    candidata = _crear_fecha(referencia.year, mes, dia)
    if candidata is None:
        return None
    if candidata < referencia:
        candidata = _crear_fecha(referencia.year + 1, mes, dia)
    return candidata


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


def extraer_numeros(mensaje: str) -> list[int]:
    """Extrae una secuencia de edades expresadas con dígitos o palabras."""
    texto = quitar_acentos(mensaje.casefold())
    encontrados: list[tuple[int, int]] = []
    for coincidencia in re.finditer(r"\b\d{1,2}\b", texto):
        encontrados.append((coincidencia.start(), int(coincidencia.group())))
    for palabra, valor in NUMEROS.items():
        for coincidencia in re.finditer(rf"\b{palabra}\b", texto):
            encontrados.append((coincidencia.start(), valor))
    return [valor for _, valor in sorted(encontrados)]


def extraer_hora(mensaje: str) -> time | None:
    """Interpreta horas telefónicas habituales en formato de 12 o 24 horas."""
    texto = quitar_acentos(mensaje.casefold())
    periodo = None
    if "tarde" in texto or "noche" in texto or "pm" in texto:
        periodo = "pm"
    elif "manana" in texto or "am" in texto:
        periodo = "am"
    coincidencia = re.search(r"\b(\d{1,2})(?::(\d{2}))?\b", texto)
    if coincidencia:
        hora = int(coincidencia.group(1))
        minuto = int(coincidencia.group(2) or 0)
    else:
        valores = [
            (texto.find(palabra), valor)
            for palabra, valor in NUMEROS.items()
            if palabra != "cero" and re.search(rf"\b{palabra}\b", texto)
        ]
        if not valores:
            return None
        hora = min(valores)[1]
        minuto = 0
    if periodo == "pm" and hora < 12:
        hora += 12
    if periodo == "am" and hora == 12:
        hora = 0
    try:
        return time(hora, minuto)
    except ValueError:
        return None


def calcular_precio_noche(tipo: str, adultos: int) -> int:
    if tipo == "doble":
        return 700 if adultos <= 2 else 800
    if tipo == "king":
        return 700
    if tipo == "suite":
        return 900
    raise ValueError("Tipo de habitación no reconocido")


def calcular_total(datos) -> int:
    assert datos.numero_noches
    return sum(item.precio_noche for item in datos.habitaciones) * datos.numero_noches


def es_afirmativo(mensaje: str) -> bool:
    palabras = set(re.findall(r"\w+", quitar_acentos(mensaje.casefold())))
    return bool(palabras.intersection({"si", "confirmo", "continuar", "adelante"}))


def es_negativo(mensaje: str) -> bool:
    palabras = set(re.findall(r"\w+", quitar_acentos(mensaje.casefold())))
    return bool(palabras.intersection({"no", "negativo"}))


def detectar_cambio(mensaje: str) -> str | None:
    """Identifica el dato que el huésped desea corregir."""
    palabras = set(re.findall(r"\w+", quitar_acentos(mensaje.casefold())))
    if palabras.intersection({"fecha", "fechas", "entrada", "salida", "dia", "dias"}):
        return "fechas"
    if palabras.intersection({"habitacion", "habitaciones", "doble", "king", "suite"}):
        return "habitacion"
    if palabras.intersection({"adulto", "adultos", "huesped", "huespedes", "persona", "personas"}):
        return "huespedes"
    return None


def desea_cancelar(mensaje: str) -> bool:
    palabras = set(re.findall(r"\w+", quitar_acentos(mensaje.casefold())))
    return bool(palabras.intersection({"cancelar", "cancela", "terminar", "finalizar"}))


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
