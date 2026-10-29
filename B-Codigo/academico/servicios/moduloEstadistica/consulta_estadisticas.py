from statistics import mean, pvariance
from django.db.models import F, ExpressionWrapper, DurationField
from django.db.models.functions import ExtractYear
from django.db.models import Avg, Variance, Count
from django.db.models import OuterRef, Subquery
from academico.models import GraduadoCarrera
from django.db.models import F, ExpressionWrapper, DurationField


from academico.models import (
    Graduado,
    Carrera,
    Analitico,
)


# ==================================================
# CONSULTAS AUXILIARES
# ==================================================

def obtener_analiticos(fechaInicio, fechaFin):
    """
    Obtiene los analíticos que corresponden al período indicado.
    Los límites son opcionales.
    """
    analiticos = Analitico.objects.all()

    if fechaInicio:
        analiticos = analiticos.filter(
            fecha_egreso_carrera__gte=fechaInicio
        )

    if fechaFin:
        analiticos = analiticos.filter(
            fecha_egreso_carrera__lte=fechaFin
        )

    return analiticos


def filtrar_analiticos(analiticos, filtro, carrera, escuela):
    """
    Filtra analíticos por carrera o escuela cuando corresponda.
    """
    if filtro == "carrera":
        if not carrera:
            return analiticos.none()

        analiticos = analiticos.filter(
            titulo_carrera__carrera_id=carrera
        )

    elif filtro == "escuela":
        if not escuela:
            return analiticos.none()

        analiticos = analiticos.filter(
            titulo_carrera__carrera__escuela=escuela
        )

    return analiticos


# ==================================================
# PROMEDIOS Y VARIANZA
# ==================================================


def consultar_promedios(
    tipoPromedio,
    filtro,
    carrera,
    escuela,
    fechaInicio,
    fechaFin
):
    """
    Calcula el promedio y la varianza de los promedios académicos
    de los graduados que cumplen los filtros seleccionados.
    Cada graduado se considera una sola vez.
    """

    campos_validos = {
        "promedio_sin_aplazo",
        "promedio_con_aplazo",
    }

    if tipoPromedio not in campos_validos:
        return {
            "promedio": None,
            "varianza": None,
        }

    analiticos = obtener_analiticos(fechaInicio, fechaFin)

    analiticos = filtrar_analiticos(
        analiticos,
        filtro,
        carrera,
        escuela
    )

    legajos = analiticos.values("graduado_id").distinct()

    graduados = Graduado.objects.filter(
        pk__in=legajos
    )

    resultado = graduados.aggregate(
        promedio=Avg(tipoPromedio),
        varianza=Variance(tipoPromedio),
    )

    return resultado

# ==================================================
# CANTIDAD DE GRADUADOS
# ==================================================

def consultar_total(
    filtro,
    carrera,
    escuela,
    fechaInicio,
    fechaFin
):
    """
    Devuelve los totales y los datos agrupados necesarios
    para construir el gráfico correspondiente.
    """

    analiticos = obtener_analiticos(
        fechaInicio,
        fechaFin
    )

    # ----------------------------------------------
    # TODOS LOS GRADUADOS: distribución por escuela
    # ----------------------------------------------

    if filtro == "todos":

        total = analiticos.values(
            "graduado_id"
        ).distinct().count()

        agrupados = (
            analiticos
            .exclude(titulo_carrera__carrera__escuela="")
            .values("titulo_carrera__carrera__escuela")
            .annotate(
                total_escuela=Count(
                    "graduado_id",
                    distinct=True
                )
            )
            .order_by("titulo_carrera__carrera__escuela")
        )

        total_por_escuela = [
            {
                "escuela": fila["titulo_carrera__carrera__escuela"],
                "total_escuela": fila["total_escuela"],
            }
            for fila in agrupados
        ]

        cantidades = [
            fila["total_escuela"]
            for fila in total_por_escuela
        ]

        return {
            "total": total,
            "promedio_por_escuela": (
                mean(cantidades) if cantidades else None
            ),
            "varianza_escuelas": (
                pvariance(cantidades) if cantidades else None
            ),
            "total_por_escuela": total_por_escuela,
            "etiquetas": [
                fila["escuela"] for fila in total_por_escuela
            ],
            "valores": cantidades,
        }

    # ----------------------------------------------
    # UNA ESCUELA: distribución por carrera
    # ----------------------------------------------

    elif filtro == "escuela":

        if not escuela:
            return {
                "total_escuela": 0,
                "promedio_por_carrera": None,
                "varianza_carreras": None,
                "total_por_carrera": [],
                "etiquetas": [],
                "valores": [],
            }

        analiticos_escuela = analiticos.filter(
            titulo_carrera__carrera__escuela=escuela
        )

        total_escuela = (
            analiticos_escuela
            .values("graduado_id")
            .distinct()
            .count()
        )

        agrupados = (
            analiticos_escuela
            .values(
                "titulo_carrera__carrera_id",
                "titulo_carrera__carrera__nombre_carrera",
            )
            .annotate(
                total_carrera=Count(
                    "graduado_id",
                    distinct=True
                )
            )
            .order_by(
                "titulo_carrera__carrera__nombre_carrera"
            )
        )

        total_por_carrera = [
            {
                "codigo_carrera": fila[
                    "titulo_carrera__carrera_id"
                ],
                "nombre_carrera": fila[
                    "titulo_carrera__carrera__nombre_carrera"
                ],
                "total_carrera": fila["total_carrera"],
            }
            for fila in agrupados
        ]

        cantidades = [
            fila["total_carrera"]
            for fila in total_por_carrera
        ]

        return {
            "total_escuela": total_escuela,
            "promedio_por_carrera": (
                mean(cantidades) if cantidades else None
            ),
            "varianza_carreras": (
                pvariance(cantidades) if cantidades else None
            ),
            "total_por_carrera": total_por_carrera,
            "etiquetas": [
                fila["nombre_carrera"]
                for fila in total_por_carrera
            ],
            "valores": cantidades,
        }

    # ----------------------------------------------
    # UNA CARRERA: cantidad total de graduados
    # ----------------------------------------------

    elif filtro == "carrera":

        if not carrera:
            return {
                "total": 0,
                "etiquetas": [],
                "valores": [],
            }

        analiticos_carrera = analiticos.filter(
            titulo_carrera__carrera_id=carrera
        )

        total = (
            analiticos_carrera
            .values("graduado_id")
            .distinct()
            .count()
        )

        nombre_carrera = (
            Carrera.objects
            .filter(pk=carrera)
            .values_list("nombre_carrera", flat=True)
            .first()
        )

        return {
            "total": total,
            "etiquetas": [nombre_carrera or "Carrera"],
            "valores": [total],
        }

    # ----------------------------------------------
    # FILTRO INVÁLIDO
    # ----------------------------------------------

    return {
        "total": 0,
        "etiquetas": [],
        "valores": [],
    }







def consultar_tiempos(
    filtro,
    carrera,
    escuela,
    fechaInicio,
    fechaFin
):
    """
    Calcula el tiempo transcurrido entre el ingreso y el egreso
    de cada graduado en una carrera, expresado en años.
    """

    analiticos = obtener_analiticos(fechaInicio, fechaFin)

    analiticos = filtrar_analiticos(
        analiticos,
        filtro,
        carrera,
        escuela
    )

    # Relacionar cada analítico con el ingreso a su carrera.
    graduados_carrera = GraduadoCarrera.objects.filter(
        graduado_id=OuterRef("graduado_id"),
        carrera_id=OuterRef("titulo_carrera__carrera_id")
    )

    analiticos = analiticos.annotate(
        fecha_ingreso=Subquery(
            graduados_carrera.values("fecha_ingreso_carrera")[:1]
        )
    ).filter(
        fecha_ingreso__isnull=False
    )

    analiticos = analiticos.annotate(
        duracion=ExpressionWrapper(
            F("fecha_egreso_carrera") - F("fecha_ingreso"),
            output_field=DurationField()
        )
    )

    tiempos = analiticos.values(
        "graduado_id",
        "titulo_carrera__carrera__nombre_carrera",
        "duracion"
    ).order_by("graduado_id")

    etiquetas = []
    valores = []

    for fila in tiempos:
        duracion = fila["duracion"]

        if duracion is not None and duracion.days >= 0:
            etiquetas.append(
                str(fila["graduado_id"])
            )
            valores.append(
                round(duracion.days / 365.25, 2)
            )

    return {
        "etiquetas": etiquetas,
        "valores": valores,
        "promedio_tiempo": (
            round(sum(valores) / len(valores), 2)
            if valores else None
        )
    }
