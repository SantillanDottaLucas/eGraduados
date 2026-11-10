"""
Utilidades de texto para la generación de analíticos:

- Números enteros en letras (español), para notas 0-10.
- Promedio con letras, p. ej. «SIETE con sesenta y siete centésimos».
- Fechas largas en español en ambos formatos:
    «24 de abril de 2.026.»        (formato corto del documento)
    «veintinueve días del mes de abril del año dos mil veintiséis.»
- Años con punto de miles (1.999, 2.026) y DNI con puntos (41.734.713).
"""

import unicodedata
from datetime import date


UNIDADES = {
    0: "cero", 1: "uno", 2: "dos", 3: "tres", 4: "cuatro",
    5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve",
    10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce",
    15: "quince", 16: "dieciséis", 17: "diecisiete",
    18: "dieciocho", 19: "diecinueve", 20: "veinte",
    21: "veintiuno", 22: "veintidós", 23: "veintitrés",
    24: "veinticuatro", 25: "veinticinco", 26: "veintiséis",
    27: "veintisiete", 28: "veintiocho", 29: "veintinueve",
}

DECENAS = {
    30: "treinta", 40: "cuarenta", 50: "cincuenta",
    60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa",
}

CENTENAS = {
    100: "cien", 200: "doscientos", 300: "trescientos",
    400: "cuatrocientos", 500: "quinientos", 600: "seiscientos",
    700: "setecientos", 800: "ochocientos", 900: "novecientos",
}

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _quitar_acentos(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )


def numero_a_letras(numero):
    """Convierte un entero entre 0 y 9999 a letras en español."""

    numero = int(numero)

    if numero < 0 or numero > 9999:
        raise ValueError("Sólo se soportan enteros entre 0 y 9999.")

    if numero < 30:
        return UNIDADES[numero]

    if numero < 100:
        decena = (numero // 10) * 10
        unidad = numero % 10

        if unidad == 0:
            return DECENAS[decena]

        return f"{DECENAS[decena]} y {UNIDADES[unidad]}"

    if numero == 100:
        return "cien"

    if numero < 1000:
        centena = (numero // 100) * 100
        resto = numero % 100

        if resto == 0:
            return CENTENAS[centena]

        if centena == 100:
            return f"ciento {numero_a_letras(resto)}"

        return f"{CENTENAS[centena]} {numero_a_letras(resto)}"

    miles = numero // 1000
    resto = numero % 1000

    if miles == 1:
        texto_miles = "mil"
    else:
        texto_miles = f"{numero_a_letras(miles)} mil"

    if resto == 0:
        return texto_miles

    return f"{texto_miles} {numero_a_letras(resto)}"


def nota_a_letras(nota):
    """Nota 0-10 como «9(nueve)» (se usa en el documento)."""

    return f"{nota}({numero_a_letras(int(nota))})"


def promedio_a_letras(promedio):
    """
    «7,67» -> «SIETE con sesenta y siete centésimos».
    Maneja el caso .00 (exactamente, «ENTRO con cero centésimos»).
    """

    promedio = round(float(promedio), 2)
    parte_entera = int(promedio)
    centesimos = int(round((promedio - parte_entera) * 100))

    return (
        f"{numero_a_letras(parte_entera).upper()} con "
        f"{numero_a_letras(centesimos)} centésimos"
    )


def _dia_en_letras(cantidad):
    return numero_a_letras(int(cantidad))


def fecha_larga(fecha):
    """
    «24 de abril de 2.026.» — formato corto con año con punto.
    """

    if fecha is None:
        return ""

    return (
        f"{fecha.day} de {MESES[fecha.month - 1]} "
        f"de {anio_con_punto(fecha.year)}"
    )


def fecha_larga_letras(fecha):
    """
    «veintinueve días del mes de abril del año dos mil veintiséis».
    """

    if fecha is None:
        return ""

    dia = numero_a_letras(fecha.day)
    mes = MESES[fecha.month - 1]
    anio = numero_a_letras(fecha.year)

    return f"{dia} días del mes de {mes} del año {anio}"


def fecha_nacimiento_larga(fecha):
    """«06 de abril de 1.999» — nacimiento con puntos en el año."""

    if fecha is None:
        return ""

    return (
        f"{fecha.day:02d} de {MESES[fecha.month - 1]} "
        f"de {anio_con_punto(fecha.year)}"
    )


def anio_con_punto(anio):
    """2016 -> «2.016», 1999 -> «1.999»."""

    anio = int(anio)
    miles, resto = divmod(anio, 1000)

    if miles and resto < 100:
        return f"{miles}.{resto:03d}"

    return str(anio)


def dni_con_puntos(dni):
    """«41734713» -> «41.734.713»."""

    texto = "".join(c for c in str(dni) if c.isdigit())

    if len(texto) <= 3:
        return texto

    grupos = []

    while texto:
        grupos.insert(0, texto[-3:])
        texto = texto[:-3]

    return ".".join(grupos)
