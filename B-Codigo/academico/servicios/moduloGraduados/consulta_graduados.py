
from datetime import date

from django.db.models import Exists, OuterRef, Q

from academico.models import Graduado, GraduadoCarrera, Analitico


def obtener_graduados_filtrados(parametros):
    graduados = Graduado.objects.all()

    # 1. Buscar por nombre o apellido completo o parcial.
    nombre = parametros.get('nombre', '').strip()

    if nombre:
        for palabra in nombre.split():
            graduados = graduados.filter(
                Q(nombres_asociados__nombre__icontains=palabra)
                | Q(apellidos_asociados__apellido__icontains=palabra)
            )

    # 2. Buscar por legajo completo o parcial.
    legajo = parametros.get('legajo', '').strip()

    if legajo:
        graduados = graduados.filter(
            legajo_graduado__icontains=legajo
        )

    # 3. Filtrar por carrera.
    carrera = parametros.get('carrera', '').strip()

    if carrera:
        graduados_por_carrera = GraduadoCarrera.objects.filter(
            graduado_id=OuterRef('pk'),
            carrera_id=carrera
        )

        graduados = graduados.filter(Exists(graduados_por_carrera))

    # 4. Filtrar por escuela.
    escuela = parametros.get('escuela', '').strip()

    if escuela:
        graduados_por_escuela = GraduadoCarrera.objects.filter(
            graduado_id=OuterRef('pk'),
            carrera__escuela=escuela
        )

        graduados = graduados.filter(Exists(graduados_por_escuela))

    # 5. Filtrar por fecha de egreso.
    fecha_desde = parametros.get('fecha_desde', '').strip()
    fecha_hasta = parametros.get('fecha_hasta', '').strip()

    try:
        fecha_desde = date.fromisoformat(fecha_desde) if fecha_desde else None
    except ValueError:
        fecha_desde = None

    try:
        fecha_hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else None
    except ValueError:
        fecha_hasta = None

    # No aplicar el intervalo si las fechas están invertidas.
    if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
        fecha_desde = None
        fecha_hasta = None

    if fecha_desde or fecha_hasta:
        egresos = Analitico.objects.filter(
            graduado_id=OuterRef('pk')
        )

        if fecha_desde:
            egresos = egresos.filter(
                fecha_egreso_carrera__gte=fecha_desde
            )

        if fecha_hasta:
            egresos = egresos.filter(
                fecha_egreso_carrera__lte=fecha_hasta
            )

        graduados = graduados.filter(Exists(egresos))

    return (
        graduados
        .distinct()
        .order_by('legajo_graduado')
        .prefetch_related('nombres_asociados', 'apellidos_asociados')
    )
