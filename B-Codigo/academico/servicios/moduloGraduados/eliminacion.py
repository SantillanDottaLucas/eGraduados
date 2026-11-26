"""
Borrado controlado de graduados y de relaciones con carreras.

Todas las operaciones son transaccionales y dejan constancia en
AUDITORIA. El graduado se identifica por DNI (su clave primaria);
el legajo es sólo un dato derivado. El borrado completo elimina
explícitamente el secundario porque esa FK es PROTECT; el resto de
las dependencias son CASCADE.
"""

from django.db import transaction

from academico.models import (
    Analitico,
    DatosNacimiento,
    Graduado,
    GraduadoCarrera,
    GraduadoExamen,
    Secundario,
)
from academico.servicios.auditoria import registrar_auditoria


CONFIRMACION_BORRADO = "ELIMINAR"


def resumen_impacto(dni, carrera=None):
    """Cantidades que se borrarían, para mostrar en la confirmación."""

    examenes = GraduadoExamen.objects.filter(dni_graduado_id=dni)
    analiticos = Analitico.objects.filter(dni_graduado_id=dni)

    if carrera:
        examenes = examenes.filter(codigo_carrera_id=carrera)
        analiticos = analiticos.filter(codigo_carrera_id=carrera)

    total_carreras = GraduadoCarrera.objects.filter(
        dni_graduado_id=dni
    ).count()

    return {
        "dni": dni,
        "carrera": carrera or "",
        "carreras": (
            GraduadoCarrera.objects.filter(
                dni_graduado_id=dni,
                codigo_carrera_id=carrera,
            ).count()
            if carrera else total_carreras
        ),
        "total_carreras": total_carreras,
        "ultima_carrera": bool(carrera) and total_carreras <= 1,
        "examenes": examenes.count(),
        "analiticos": analiticos.count(),
        "secundarios": Secundario.objects.filter(
            dni_graduado_id=dni
        ).count(),
        "nacimientos": DatosNacimiento.objects.filter(
            dni_graduado_id=dni
        ).count(),
    }


def eliminar_carrera(dni, carrera, usuario=None, confirmacion=""):
    """
    Quita la fila (dni, carrera) y todo lo asociado a esa
    carrera. El graduado y sus otras carreras quedan intactos.
    """

    impacto = resumen_impacto(dni, carrera)

    if impacto["analiticos"] and confirmacion != CONFIRMACION_BORRADO:
        raise ValueError(
            "Esta carrera tiene analíticos validados. "
            "Confirmá escribiendo ELIMINAR para borrarlos también."
        )

    with transaction.atomic():
        registro = GraduadoCarrera.objects.select_related(
            "dni_graduado"
        ).get(
            dni_graduado_id=dni,
            codigo_carrera_id=carrera,
        )

        Analitico.objects.filter(
            dni_graduado_id=dni,
            codigo_carrera_id=carrera,
        ).delete()

        GraduadoExamen.objects.filter(
            dni_graduado_id=dni,
            codigo_carrera_id=carrera,
        ).delete()

        registro.delete()

        registrar_auditoria(
            usuario,
            "eliminar_carrera_graduado",
            entidad="GraduadoCarrera",
            entidad_id=f"{dni}|{carrera}",
            detalle=impacto,
        )

    impacto["quedan_carreras"] = (
        GraduadoCarrera.objects.filter(dni_graduado_id=dni).count()
    )

    return impacto


def eliminar_graduado(dni, usuario=None, confirmacion=""):
    """
    Borra el graduado identificado por DNI y todas sus relaciones.

    Si tiene analíticos validados exige la doble confirmación.
    """

    graduado = Graduado.objects.get(pk=dni)
    impacto = resumen_impacto(dni)

    if impacto["analiticos"] and confirmacion != CONFIRMACION_BORRADO:
        raise ValueError(
            "Este graduado tiene analíticos validados. "
            "Confirmá escribiendo ELIMINAR para borrarlos también."
        )

    with transaction.atomic():
        # Secundario es PROTECT: hay que borrarlo antes que al
        # graduado. El resto cae en cascada.
        Secundario.objects.filter(dni_graduado=graduado).delete()
        graduado.delete()

        registrar_auditoria(
            usuario,
            "eliminar_graduado",
            entidad="Graduado",
            entidad_id=dni,
            detalle=impacto,
        )

    return impacto
