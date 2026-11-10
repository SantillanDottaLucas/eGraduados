"""
Validaciones de negocio compartidas por la carga de datos
(por Excel) y la edición manual de graduados.

Todas las funciones lanzan ValueError con un mensaje orientado
al usuario, para que cada llamador decida cómo presentarlo.
"""

from datetime import date

from academico.models import Graduado


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
# FECHAS
# ==================================================

def validar_cronologia_fechas(
    fecha_ingreso_universidad,
    fecha_ingreso_carrera,
    fecha_egreso_carrera
):
    """
    Comprueba la coherencia cronológica de las fechas de un
    graduado: el ingreso a la universidad debe ser el mismo día
    o anterior al ingreso a la carrera, y el egreso no puede ser
    anterior al ingreso a la carrera.
    """

    if fecha_ingreso_universidad > fecha_ingreso_carrera:
        raise ValueError(
            "El ingreso a la carrera no puede ser anterior "
            "al ingreso a la universidad."
        )

    if fecha_ingreso_carrera > fecha_egreso_carrera:
        raise ValueError(
            "El egreso de la carrera no puede ser anterior "
            "al ingreso a la carrera."
        )


# ==================================================
# DNI
# ==================================================

def validar_dni_unico(dni, legajo):
    """
    Comprueba que el DNI no pertenezca a otro legajo.

    Devuelve True si no hay conflicto.
    """

    return not Graduado.objects.exclude(
        legajo_graduado=legajo
    ).filter(dni=dni).exists()
