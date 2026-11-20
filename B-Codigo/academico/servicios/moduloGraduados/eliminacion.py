"""
Borrado controlado de graduados y de relaciones con carreras.

Todas las operaciones son transaccionales y dejan constancia en
AUDITORIA. El borrado completo elimina explícitamente el secundario
porque esa FK es PROTECT; el resto de las dependencias son CASCADE.
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


def resumen_impacto(legajo, carrera=None):
    """Cantidades que se borrarían, para mostrar en la confirmación."""

    examenes = GraduadoExamen.objects.filter(legajo_graduado_id=legajo)
    analiticos = Analitico.objects.filter(legajo_graduado_id=legajo)

    if carrera:
        examenes = examenes.filter(codigo_carrera_id=carrera)
        analiticos = analiticos.filter(codigo_carrera_id=carrera)

    total_carreras = GraduadoCarrera.objects.filter(
        legajo_graduado_id=legajo
    ).count()

    return {
        "legajo": legajo,
        "carrera": carrera or "",
        "carreras": (
            GraduadoCarrera.objects.filter(
                legajo_graduado_id=legajo,
                codigo_carrera_id=carrera,
            ).count()
            if carrera else total_carreras
        ),
        "total_carreras": total_carreras,
        "ultima_carrera": bool(carrera) and total_carreras <= 1,
        "examenes": examenes.count(),
        "analiticos": analiticos.count(),
        "secundarios": Secundario.objects.filter(
            legajo_graduado_id=legajo
        ).count(),
        "nacimientos": DatosNacimiento.objects.filter(
            legajo_graduado_id=legajo
        ).count(),
    }


def eliminar_carrera(legajo, carrera, usuario=None, confirmacion=""):
    """
    Quita la fila (legajo, carrera) y todo lo asociado a esa
    carrera. El graduado y sus otras carreras quedan intactos.
    """

    impacto = resumen_impacto(legajo, carrera)

    if impacto["analiticos"] and confirmacion != CONFIRMACION_BORRADO:
        raise ValueError(
            "Esta carrera tiene analíticos validados. "
            "Confirmá escribiendo ELIMINAR para borrarlos también."
        )

    with transaction.atomic():
        registro = GraduadoCarrera.objects.select_related(
            "legajo_graduado"
        ).get(
            legajo_graduado_id=legajo,
            codigo_carrera_id=carrera,
        )

        Analitico.objects.filter(
            legajo_graduado_id=legajo,
            codigo_carrera_id=carrera,
        ).delete()

        GraduadoExamen.objects.filter(
            legajo_graduado_id=legajo,
            codigo_carrera_id=carrera,
        ).delete()

        registro.delete()

        registrar_auditoria(
            usuario,
            "eliminar_carrera_graduado",
            entidad="GraduadoCarrera",
            entidad_id=f"{legajo}|{carrera}",
            detalle=impacto,
        )

    impacto["quedan_carreras"] = (
        GraduadoCarrera.objects.filter(legajo_graduado_id=legajo).count()
    )

    return impacto


def eliminar_graduado(legajo, usuario=None, confirmacion=""):
    """
    Borra el graduado completo y todas sus relaciones.

    Si tiene analíticos validados exige la doble confirmación.
    """

    graduado = Graduado.objects.get(pk=legajo)
    impacto = resumen_impacto(legajo)

    if impacto["analiticos"] and confirmacion != CONFIRMACION_BORRADO:
        raise ValueError(
            "Este graduado tiene analíticos validados. "
            "Confirmá escribiendo ELIMINAR para borrarlos también."
        )

    with transaction.atomic():
        # Secundario es PROTECT: hay que borrarlo antes que al
        # graduado. El resto cae en cascada.
        Secundario.objects.filter(legajo_graduado=graduado).delete()
        graduado.delete()

        registrar_auditoria(
            usuario,
            "eliminar_graduado",
            entidad="Graduado",
            entidad_id=legajo,
            detalle=impacto,
        )

    return impacto
