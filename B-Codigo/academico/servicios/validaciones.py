"""
Validaciones de negocio compartidas por la carga de datos
(por Excel), la carga manual de graduados, la edición manual
y la generación de analíticos.

Todas las funciones lanzan ValueError con un mensaje orientado
al usuario, para que cada llamador decida cómo presentarlo.
``validar_datos_graduado`` es la fachada que reúne todas las
reglas y devuelve la lista de errores.

El ingreso a la UARG se informa como AÑO (no como fecha).
"""

import re
from datetime import date, datetime

from academico.models import Graduado
from academico.servicios.legajo import generar_legajo


# ==================================================
# DNI
# ==================================================

DNI_MIN_DIGITOS = 7
DNI_MAX_DIGITOS = 8

ANIO_MIN = 1900
ANIO_MAX = 2100


def validar_dni(dni):
    """
    Exige un DNI formado sólo por dígitos (7 u 8) y lo devuelve
    sin espacios. No 'limpia' caracteres inválidos: los rechaza.
    """

    texto = str(dni or "").strip()

    if not texto:
        raise ValueError("El campo «dni» es obligatorio.")

    if not texto.isdigit():
        raise ValueError("El DNI debe contener sólo dígitos.")

    if not DNI_MIN_DIGITOS <= len(texto) <= DNI_MAX_DIGITOS:
        raise ValueError(
            f"El DNI debe tener entre {DNI_MIN_DIGITOS} y "
            f"{DNI_MAX_DIGITOS} dígitos."
        )

    return texto


def validar_dni_unico(dni, dni_actual=None):
    """
    Comprueba que el DNI no pertenezca a otro graduado.

    ``dni_actual`` es la clave del registro que se está editando.
    Devuelve True si no hay conflicto.
    """

    return not Graduado.objects.exclude(
        pk=dni_actual
    ).filter(pk=dni).exists()


# ==================================================
# AÑOS Y FECHAS
# ==================================================

def validar_anio(valor, campo="anio"):
    """Valida un año de 4 dígitos y lo devuelve como entero."""

    if valor in (None, ""):
        raise ValueError(f"El campo «{campo}» es obligatorio.")

    try:
        texto = str(valor).strip()

        if isinstance(valor, float) and valor.is_integer():
            texto = str(int(valor))

        if not re.fullmatch(r"\d{4}", texto):
            raise ValueError

        anio = int(texto)
    except (TypeError, ValueError):
        raise ValueError(
            f"El campo «{campo}» debe contener un año de 4 dígitos."
        )

    if not ANIO_MIN <= anio <= ANIO_MAX:
        raise ValueError(
            f"El campo «{campo}» debe estar entre {ANIO_MIN} y {ANIO_MAX}."
        )

    return anio


def anio_desde_valor(valor, campo="anio"):
    """
    Normaliza un valor que puede ser un año suelto o una fecha a
    un año entero. Se usa en la importación Excel, donde conviven
    planillas con ``fecha_ingreso_universidad`` y con año.
    """

    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise ValueError(f"El campo «{campo}» es obligatorio.")

    # NaN de pandas: no es igual ni siquiera a sí mismo.
    if isinstance(valor, float) and valor != valor:
        raise ValueError(f"El campo «{campo}» es obligatorio.")

    if isinstance(valor, datetime):
        valor = valor.date()

    if isinstance(valor, date):
        return validar_anio(valor.year, campo)

    texto = str(valor).strip()

    # Excel puede entregar el año como texto «2014.0».
    if re.fullmatch(r"\d{4}\.0+", texto):
        texto = texto.split(".")[0]

    try:
        return validar_anio(texto, campo)
    except ValueError as error_anio:
        for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                fecha = datetime.strptime(texto, formato).date()
            except ValueError:
                continue

            return validar_anio(fecha.year, campo)

        raise ValueError(
            f"El campo «{campo}» debe ser un año de 4 dígitos "
            "o una fecha válida."
        ) from error_anio


def validar_anios(
    fecha_nacimiento=None,
    anio_ingreso_universidad=None,
    anio_ingreso_carrera=None,
):
    """Orden cronológico de los años informados en el formulario."""

    if (
        anio_ingreso_universidad is not None
        and anio_ingreso_carrera is not None
        and anio_ingreso_universidad > anio_ingreso_carrera
    ):
        raise ValueError(
            "El año de ingreso a la universidad no puede ser "
            "posterior al año de ingreso a la carrera."
        )

    anio_nacimiento = (
        getattr(fecha_nacimiento, "year", None)
        if fecha_nacimiento is not None else None
    )

    if (
        anio_nacimiento is not None
        and anio_ingreso_universidad is not None
        and anio_nacimiento > anio_ingreso_universidad
    ):
        raise ValueError(
            "El año de nacimiento no puede ser posterior al año "
            "de ingreso a la universidad."
        )

    if (
        anio_nacimiento is not None
        and anio_ingreso_carrera is not None
        and anio_nacimiento > anio_ingreso_carrera
    ):
        raise ValueError(
            "El año de nacimiento no puede ser posterior al año "
            "de ingreso a la carrera."
        )


def _errores_cronologia_fechas(
    fecha_ingreso_carrera,
    fecha_egreso_carrera,
    fecha_nacimiento=None,
):
    """Devuelve todas las inconsistencias cronológicas."""

    errores = []

    if (
        fecha_ingreso_carrera is not None
        and fecha_egreso_carrera is not None
        and fecha_ingreso_carrera >= fecha_egreso_carrera
    ):
        errores.append(
            "La fecha de egreso debe ser posterior a la fecha "
            "de ingreso a la carrera."
        )

    if (
        fecha_nacimiento is not None
        and fecha_egreso_carrera is not None
        and fecha_nacimiento >= fecha_egreso_carrera
    ):
        errores.append(
            "La fecha de nacimiento debe ser anterior a la "
            "fecha de egreso."
        )

    return errores


def validar_cronologia_fechas(
    fecha_ingreso_carrera,
    fecha_egreso_carrera,
    fecha_nacimiento=None,
):
    """
    Comprueba la coherencia cronológica de las fechas de la
    carrera: el egreso debe ser posterior al ingreso.

    Lanza el primer error (para los llamadores que esperan una
    única excepción). La fachada usa ``_errores_cronologia_fechas``
    para informar todos los problemas a la vez.
    """

    errores = _errores_cronologia_fechas(
        fecha_ingreso_carrera,
        fecha_egreso_carrera,
        fecha_nacimiento,
    )

    if errores:
        raise ValueError(errores[0])


# ==================================================
# PROMEDIOS
# ==================================================

def validar_promedio(valor, campo):
    """
    Valida un promedio numérico entre 0 y 10.

    Devuelve el valor convertido a float.
    """

    try:
        texto = str(valor).strip().replace(",", ".")
        promedio = float(texto)
    except (TypeError, ValueError):
        raise ValueError(
            f"El campo «{campo}» debe ser numérico."
        )

    if not 0 <= promedio <= 10:
        raise ValueError(
            f"El campo «{campo}» debe estar entre 0 y 10."
        )

    return promedio


# ==================================================
# FACHADA
# ==================================================

def validar_datos_graduado(datos, exigir_anio_uarg=False):
    """
    Aplica todas las reglas de negocio sobre un graduado.

    ``datos`` puede contener ``dni``, ``anio_ingreso_universidad``,
    ``anio_ingreso_carrera``, ``fecha_nacimiento``,
    ``fecha_ingreso_carrera`` y ``fecha_egreso_carrera``.

    El año de ingreso a la UARG es opcional por defecto. Los
    analíticos lo exigen (``exigir_anio_uarg=True``) porque la
    plantilla del documento necesita ``anio_ingreso_uarg``.

    Devuelve ``(normalizados, errores)``. ``normalizados`` trae el
    DNI, el año y el legajo derivado listos para persistir. El
    legajo es ``None`` si no hay DNI o año.
    """

    errores = []
    normalizados = {
        "dni": "",
        "legajo": None,
        "anio_ingreso_universidad": None,
    }

    dni = datos.get("dni")
    anio_uarg = None

    valor_anio = datos.get("anio_ingreso_universidad")

    if valor_anio in (None, "") and exigir_anio_uarg:
        errores.append("El campo «anio_ingreso_universidad» es obligatorio.")
    elif valor_anio not in (None, ""):
        try:
            anio_uarg = validar_anio(
                valor_anio,
                "anio_ingreso_universidad",
            )
            normalizados["anio_ingreso_universidad"] = anio_uarg
        except ValueError as error:
            errores.append(str(error))

    try:
        anio_carrera = datos.get("anio_ingreso_carrera")

        if anio_carrera not in (None, ""):
            anio_carrera = validar_anio(anio_carrera, "anio_ingreso_carrera")
        else:
            anio_carrera = None
    except ValueError as error:
        anio_carrera = None
        errores.append(str(error))

    try:
        normalizados["dni"] = validar_dni(dni)
    except ValueError as error:
        errores.append(str(error))

    normalizados["legajo"] = generar_legajo(
        normalizados["dni"],
        anio_uarg,
    )

    try:
        validar_anios(
            datos.get("fecha_nacimiento"),
            anio_uarg,
            anio_carrera,
        )
    except ValueError as error:
        errores.append(str(error))

    fecha_ingreso = datos.get("fecha_ingreso_carrera")
    fecha_egreso = datos.get("fecha_egreso_carrera")

    if fecha_ingreso is not None and fecha_egreso is not None:
        errores.extend(
            _errores_cronologia_fechas(
                fecha_ingreso,
                fecha_egreso,
                fecha_nacimiento=datos.get("fecha_nacimiento"),
            )
        )

    return normalizados, errores
