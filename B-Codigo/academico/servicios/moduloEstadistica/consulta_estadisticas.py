
from django.db.models import Avg, Variance, Count, Exists, OuterRef

from academico.models import GraduadoCarrera, Carrera
from collections import defaultdict
from statistics import mean, pvariance


# ==================================================
# CONSULTA AUXILIAR
# ==================================================

def obtener_graduados_carrera(fechaInicio=None, fechaFin=None):
    """
    Obtiene las relaciones entre graduados y carreras,
    aplicando opcionalmente un intervalo de fechas de egreso.
    """

    registros = GraduadoCarrera.objects.all()

    if fechaInicio:
        registros = registros.filter(
            fecha_egreso_carrera__gte=fechaInicio
        )

    if fechaFin:
        registros = registros.filter(
            fecha_egreso_carrera__lte=fechaFin
        )

    return registros


def filtrar_graduados_carrera(
    registros,
    filtro,
    carrera=None,
    escuela=None
):
    """
    Filtra las relaciones graduado-carrera por carrera o escuela.
    """

    if filtro == "carrera":
        if not carrera:
            return registros.none()

        registros = registros.filter(
            codigo_carrera_id=carrera
        )

    elif filtro == "escuela":
        if not escuela:
            return registros.none()

        registros = registros.filter(
            codigo_carrera__id_escuela_id=escuela
        )

    return registros


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
    Calcula el promedio y la varianza de los promedios
    académicos de las relaciones graduado-carrera filtradas.
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

    registros = obtener_graduados_carrera(
        fechaInicio,
        fechaFin
    )

    registros = filtrar_graduados_carrera(
        registros,
        filtro,
        carrera,
        escuela
    )

    return registros.aggregate(
        promedio=Avg(tipoPromedio),
        varianza=Variance(tipoPromedio),
    )


# ==================================================
# CANTIDAD DE GRADUADOS
# ==================================================

def consultar_total(
    filtro,
    carrera,
    escuela,
    fechaInicio,
    fechaFin,
):
    """
    Devuelve cantidades y datos agrupados para los gráficos.

    Filtro 'todos': distribución por escuela.
    Filtro 'escuela': distribución por carrera.
    Filtro 'carrera': total de graduados de esa carrera.
    """

    registros = obtener_graduados_carrera(
        fechaInicio,
        fechaFin,
    )

    # TODOS LOS GRADUADOS: distribución por escuela
    if filtro == "todos":

        total = (
            registros
            .values("legajo_graduado_id")
            .distinct()
            .count()
        )

        agrupados = (
            registros
            .values(
                "codigo_carrera__id_escuela_id",
                "codigo_carrera__id_escuela__nombre_escuela",
            )
            .annotate(
                total_escuela=Count(
                    "legajo_graduado_id",
                    distinct=True,
                )
            )
            .order_by(
                "codigo_carrera__id_escuela__nombre_escuela"
            )
        )

        total_por_escuela = [
            {
                "escuela": fila[
                    "codigo_carrera__id_escuela__nombre_escuela"
                ],
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

    # UNA ESCUELA: distribución por carrera
    elif filtro == "escuela":

        if not escuela:
            return {
                "total": 0,
                "total_escuela": 0,
                "promedio_por_carrera": None,
                "varianza_carreras": None,
                "total_por_carrera": [],
                "etiquetas": [],
                "valores": [],
            }

        registros_escuela = registros.filter(
            codigo_carrera__id_escuela_id=escuela
        )

        total_escuela = (
            registros_escuela
            .values("legajo_graduado_id")
            .distinct()
            .count()
        )

        agrupados = (
            registros_escuela
            .values(
                "codigo_carrera_id",
                "codigo_carrera__nombre_carrera",
            )
            .annotate(
                total_carrera=Count(
                    "legajo_graduado_id",
                    distinct=True,
                )
            )
            .order_by("codigo_carrera__nombre_carrera")
        )

        total_por_carrera = [
            {
                "codigo_carrera": fila["codigo_carrera_id"],
                "nombre_carrera": fila[
                    "codigo_carrera__nombre_carrera"
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
            "total": total_escuela,
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

    # UNA CARRERA: cantidad total de graduados
    elif filtro == "carrera":

        if not carrera:
            return {
                "total": 0,
                "varianza": None,
                "etiquetas": [],
                "valores": [],
            }

        registros_carrera = registros.filter(
            codigo_carrera_id=carrera
        )

        total = (
            registros_carrera
            .values("legajo_graduado_id")
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

    # FILTRO INVÁLIDO
    return {
        "total": 0,
        "etiquetas": [],
        "valores": [],
    }
# ==================================================
# EVOLUCIÓN / TIEMPO DE GRADUACIÓN
# ==================================================

from collections import defaultdict
from statistics import mean


def consultar_tiempos(
    filtro,
    carrera,
    escuela,
    fechaInicio,
    fechaFin
):
    """
    Calcula el tiempo promedio de graduación por carrera,
    expresado en años.
    """

    registros = obtener_graduados_carrera(
        fechaInicio,
        fechaFin
    )

    registros = filtrar_graduados_carrera(
        registros,
        filtro,
        carrera,
        escuela
    )

    registros = registros.select_related(
        "legajo_graduado",
        "codigo_carrera"
    ).order_by(
        "codigo_carrera__nombre_carrera",
        "legajo_graduado_id"
    )

    tiempos_por_carrera = defaultdict(list)
    nombres_carreras = {}
    todos_los_tiempos = []

    for registro in registros.iterator(chunk_size=500):

        fecha_ingreso = registro.fecha_ingreso_carrera
        fecha_egreso = registro.fecha_egreso_carrera

        if fecha_ingreso and fecha_egreso:
            dias = (fecha_egreso - fecha_ingreso).days

            if dias >= 0:
                tiempo = dias / 365.25

                id_carrera = registro.codigo_carrera_id

                tiempos_por_carrera[id_carrera].append(tiempo)
                nombres_carreras[id_carrera] = (
                    registro.codigo_carrera.nombre_carrera
                )

                todos_los_tiempos.append(tiempo)

    # Una etiqueta y un promedio por cada carrera.
    carreras_ordenadas = sorted(
        tiempos_por_carrera.keys(),
        key=lambda id_carrera: nombres_carreras[id_carrera].lower()
    )

    etiquetas = []
    valores = []

    for id_carrera in carreras_ordenadas:
        tiempos = tiempos_por_carrera[id_carrera]

        etiquetas.append(nombres_carreras[id_carrera])
        valores.append(round(mean(tiempos), 2))

    return {
            "etiquetas": etiquetas,
            "valores": valores,
            "promedio_tiempo": (
                round(mean(todos_los_tiempos), 2)
                if todos_los_tiempos else None
            ),
            "varianza_tiempos": (
                round(pvariance(todos_los_tiempos), 4)
                if todos_los_tiempos else None
            ),
        }