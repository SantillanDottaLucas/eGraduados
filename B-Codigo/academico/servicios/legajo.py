"""Generación del legajo institucional derivado del DNI y del año UARG.

El legajo ya no se ingresa: se calcula automáticamente cuando hay DNI y
año de ingreso a la UARG. Si falta cualquiera de los dos, no hay legajo.
El prefijo es fijo: ``1``.
"""


def normalizar_dni(dni):
    """Devuelve el DNI como texto sin espacios circundantes."""
    return str(dni or "").strip()


def generar_legajo(dni, anio_ingreso):
    """Devuelve ``1-<DNI>/<YY>`` o ``None`` si falta DNI o año."""
    dni_texto = normalizar_dni(dni)

    if not dni_texto or anio_ingreso in (None, ""):
        return None

    try:
        anio = int(anio_ingreso)
    except (TypeError, ValueError):
        return None

    return f"1-{dni_texto}/{anio % 100:02d}"
