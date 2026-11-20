"""
Sugerencias de provincias para los formularios.

La tabla Provincia puede estar vacía o incompleta: siempre se
ofrece el listado completo de provincias argentinas (más CABA)
y se agregan las que haya cargado el usuario.
"""

from academico.models import Provincia


PROVINCIAS_ARGENTINAS = (
    "Buenos Aires",
    "Ciudad Autónoma de Buenos Aires",
    "Catamarca",
    "Chaco",
    "Chubut",
    "Córdoba",
    "Corrientes",
    "Entre Ríos",
    "Formosa",
    "Jujuy",
    "La Pampa",
    "La Rioja",
    "Mendoza",
    "Misiones",
    "Neuquén",
    "Río Negro",
    "Salta",
    "San Juan",
    "San Luis",
    "Santa Cruz",
    "Santa Fe",
    "Santiago del Estero",
    "Tierra del Fuego",
    "Tucumán",
)


def provincias_sugeridas():
    """Devuelve provincias base + personalizadas, sin duplicados."""

    nombres = list(PROVINCIAS_ARGENTINAS)

    personalizadas = list(
        Provincia.objects.order_by("nombre_provincia")
        .values_list("nombre_provincia", flat=True)
    )

    vistas = {
        nombre.casefold()
        for nombre in nombres
        if nombre
    }

    for nombre in personalizadas:
        if nombre and nombre.casefold() not in vistas:
            nombres.append(nombre)
            vistas.add(nombre.casefold())

    return nombres
