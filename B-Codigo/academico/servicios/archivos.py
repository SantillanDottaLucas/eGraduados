"""Validaciones comunes de archivos subidos por el usuario."""

from django.conf import settings


def validar_archivo(archivo, extensiones):
    """
    Devuelve un mensaje de error o None si el archivo es aceptable.

    ``extensiones`` es una colección de extensiones sin punto.
    """

    if archivo is None:
        return "No se recibió ningún archivo."

    nombre = getattr(archivo, "name", "") or ""

    if "." not in nombre:
        return "El archivo no tiene una extensión válida."

    extension = nombre.rsplit(".", 1)[-1].lower()

    if extension not in {ext.lower().lstrip(".") for ext in extensiones}:
        return (
            "Formato no admitido. Se esperaba "
            + " o ".join(f".{ext}" for ext in extensiones)
            + "."
        )

    tamano = getattr(archivo, "size", 0) or 0

    if tamano > settings.MAX_UPLOAD_SIZE:
        maximo = settings.MAX_UPLOAD_SIZE / (1024 * 1024)

        return (
            "El archivo supera el tamaño máximo permitido "
            f"({maximo:.0f} MB)."
        )

    return None
