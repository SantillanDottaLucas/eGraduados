"""
Validaciones de negocio compartidas por la carga de datos
(por Excel), la edición manual de graduados y la generación
de analíticos.

Todas las funciones lanzan ValueError con un mensaje orientado
al usuario, para que cada llamador decida cómo presentarlo.
``validar_datos_graduado`` es la fachada que reúne todas las
reglas y devuelve la lista de errores.
"""

import re

from academico.models import Graduado


# ==================================================
# DNI
# ==================================================

DNI_MIN_DIGITOS = 7
DNI_MAX_DIGITOS = 8

# Legajo institucional: <prefijo 1..4>-<DNI>/<últimos 2 dígitos del año>.
# Ejemplo: 1-46189053/24
RE_LEGAJO = re.compile(r"^([1-4])-(\d{7,8})/(\d{2})$")


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


def validar_dni_unico(dni, legajo):
    """
    Comprueba que el DNI no pertenezca a otro legajo.

    Devuelve True si no hay conflicto.
    """

    return not Graduado.objects.exclude(
        legajo_graduado=legajo
    ).filter(dni=dni).exists()


# ==================================================
# LEGAJO
# ==================================================

def validar_legajo(legajo, dni=None, anio_ingreso=None):
    """
    Valida el formato del legajo y su coherencia con el DNI y
    con el año de ingreso a la universidad.

    Formato: ``<1 a 4>-<DNI>/<YY>``. Ejemplo: ``1-46189053/24``.
    """

    texto = str(legajo or "").strip()
    coincide = RE_LEGAJO.fullmatch(texto)

    if coincide is None:
        raise ValueError(
            "El legajo debe tener el formato 1-46189053/24 "
            "(prefijo del 1 al 4, DNI y los últimos dos dígitos "
            "del año de ingreso)."
        )

    _, dni_legajo, sufijo_anio = coincide.groups()

    dni_normalizado = str(dni or "").strip()

    if dni_normalizado and dni_legajo != dni_normalizado:
        raise ValueError(
            "El DNI del legajo no coincide con el DNI informado."
        )

    if anio_ingreso is not None:
        try:
            anio = int(anio_ingreso)
        except (TypeError, ValueError):
            anio = None

        if anio is not None and int(sufijo_anio) != anio % 100:
            raise ValueError(
                "Los dos dígitos del legajo no coinciden con el "
                "año de ingreso a la universidad."
            )

    return texto


# ==================================================
# AÑOS Y FECHAS
# ==================================================

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
    fecha_ingreso_universidad,
    fecha_ingreso_carrera,
    fecha_egreso_carrera,
    fecha_nacimiento=None,
):
    """Devuelve todas las inconsistencias cronológicas."""

    errores = []

    if (
        fecha_ingreso_universidad is not None
        and fecha_ingreso_carrera is not None
        and fecha_ingreso_universidad > fecha_ingreso_carrera
    ):
        errores.append(
            "El ingreso a la carrera no puede ser anterior "
            "al ingreso a la universidad."
        )

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
        fecha_ingreso_universidad is not None
        and fecha_egreso_carrera is not None
        and fecha_ingreso_universidad >= fecha_egreso_carrera
    ):
        errores.append(
            "La fecha de egreso debe ser posterior a la fecha "
            "de ingreso a la universidad."
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
    fecha_ingreso_universidad,
    fecha_ingreso_carrera,
    fecha_egreso_carrera,
    fecha_nacimiento=None,
):
    """
    Comprueba la coherencia cronológica de las fechas de un
    graduado: el ingreso a la universidad debe ser el mismo día
    o anterior al ingreso a la carrera, y el egreso debe ser
    posterior a ambos ingresos.

    Lanza el primer error (para los llamadores que esperan una
    única excepción). La fachada usa ``_errores_cronologia_fechas``
    para informar todos los problemas a la vez.
    """

    errores = _errores_cronologia_fechas(
        fecha_ingreso_universidad,
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
    Valora un promedio numérico entre 0 y 10.

    Devuelve el valor convertido a float.
    """

    try:
        texto = str(valor).strip()
        promedio = float(texto)

    except (TypeError, ValueError):
        raise ValueError(
            f"El campo '{campo}' debe ser numérico."
        )

    if not 0 <= promedio <= 10:
        raise ValueError(
            f"El campo '{campo}' debe estar entre 0 y 10."
        )

    return promedio


# ==================================================
# FACHADA
# ==================================================

def validar_datos_graduado(datos):
    """
    Aplica todas las reglas de negocio sobre un graduado.

    ``datos`` puede contener:``dni``, ``legajo``,
    ``anio_ingreso_universidad``, ``anio_ingreso_carrera``,
    ``fecha_nacimiento``, ``fecha_ingreso_universidad``,
    ``fecha_ingreso_carrera`` y ``fecha_egreso_carrera``.

    Devuelve ``(normalizados, errores)``. ``normalizados`` trae
    el DNI y el legajo sin espacios para que el llamador los use
    al persistir.
    """

    errores = []
    normalizados = {
        "dni": "",
        "legajo": "",
    }

    dni = datos.get("dni")
    legajo = datos.get("legajo")
    anio_uarg = datos.get("anio_ingreso_universidad")
    anio_carrera = datos.get("anio_ingreso_carrera")
    fecha_nac = datos.get("fecha_nacimiento")

    try:
        normalizados["dni"] = validar_dni(dni)
    except ValueError as error:
        errores.append(str(error))

    try:
        normalizados["legajo"] = validar_legajo(
            legajo,
            dni=normalizados["dni"] or dni,
            anio_ingreso=anio_uarg,
        )
    except ValueError as error:
        errores.append(str(error))

    try:
        validar_anios(fecha_nac, anio_uarg, anio_carrera)
    except ValueError as error:
        errores.append(str(error))

    fechas = (
        datos.get("fecha_ingreso_universidad"),
        datos.get("fecha_ingreso_carrera"),
        datos.get("fecha_egreso_carrera"),
    )

    if all(fecha is not None for fecha in fechas):
        errores.extend(
            _errores_cronologia_fechas(*fechas, fecha_nacimiento=fecha_nac)
        )

    return normalizados, errores
