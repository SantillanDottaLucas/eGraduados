
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from django.db.models import Exists, OuterRef, Q

from academico.models import Graduado, GraduadoCarrera


SITUACIONES_BUSQUEDA = ("todas", "sin_carrera", "con_carrera")

ORDENES_BUSQUEDA = (
    "inconsistencias",
    "legajo",
    "apellido",
    "ingreso_uarg_asc",
    "ingreso_uarg_desc",
    "menos_carreras",
)


def obtener_graduados_filtrados(parametros):
    graduados = Graduado.objects.all()

    # 1. Buscar por nombre o apellido, completo o parcial.
    nombre = parametros.get("nombre", "").strip()

    if nombre:
        for palabra in nombre.split():
            graduados = graduados.filter(
                Q(nombre__icontains=palabra)
                | Q(apellido__icontains=palabra)
            )

    # 2. Buscar por legajo completo o parcial.
    legajo = parametros.get("legajo", "").strip()

    if legajo:
        graduados = graduados.filter(
            legajo_graduado__icontains=legajo
        )

    # 3. Filtrar por carrera.
    carrera = parametros.get("carrera", "").strip()

    if carrera:
        graduados_por_carrera = GraduadoCarrera.objects.filter(
            legajo_graduado_id=OuterRef("pk"),
            codigo_carrera_id=carrera
        )

        graduados = graduados.filter(
            Exists(graduados_por_carrera)
        )

    # 4. Filtrar por escuela.
    escuela = parametros.get("escuela", "").strip()

    if escuela:
        graduados_por_escuela = GraduadoCarrera.objects.filter(
            legajo_graduado_id=OuterRef("pk"),
            codigo_carrera__id_escuela_id=escuela
        )

        graduados = graduados.filter(
            Exists(graduados_por_escuela)
        )

    # 5. Filtrar por fecha de egreso.
    fecha_desde = parametros.get("fecha_desde", "").strip()
    fecha_hasta = parametros.get("fecha_hasta", "").strip()

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
        egresos = GraduadoCarrera.objects.filter(
            legajo_graduado_id=OuterRef("pk")
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

    # Devolver graduados sin duplicados, ordenados por legajo.
    return graduados.order_by("legajo_graduado")


def _fechas(parametros):
    fecha_desde = parametros.get("fecha_desde", "").strip()
    fecha_hasta = parametros.get("fecha_hasta", "").strip()

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
        return None, None

    return fecha_desde, fecha_hasta


def obtener_filas_filtradas(parametros):
    """
    Filas de GRADUADO_CARRERA que cumplen TODOS los filtros del
    listado (nombre, legajo, carrera, escuela y período de egreso).

    A diferencia de ``obtener_graduados_filtrados``, no se pierde
    el filtro de carrera/escuela al volver a consultar la tabla
    de carreras: cada fila devuelta es la que coincide.

    Es la consulta que usa la exportación a Excel y mantiene el
    criterio histórico: no incluye graduados sin carrera.
    """

    filas = GraduadoCarrera.objects.select_related(
        "legajo_graduado",
        "codigo_carrera",
        "codigo_carrera__id_escuela",
    )

    nombre = parametros.get("nombre", "").strip()

    if nombre:
        for palabra in nombre.split():
            filas = filas.filter(
                Q(legajo_graduado__nombre__icontains=palabra)
                | Q(legajo_graduado__apellido__icontains=palabra)
            )

    legajo = parametros.get("legajo", "").strip()

    if legajo:
        filas = filas.filter(
            legajo_graduado__legajo_graduado__icontains=legajo
        )

    carrera = parametros.get("carrera", "").strip()

    if carrera:
        filas = filas.filter(codigo_carrera_id=carrera)

    escuela = parametros.get("escuela", "").strip()

    if escuela:
        filas = filas.filter(codigo_carrera__id_escuela_id=escuela)

    fecha_desde, fecha_hasta = _fechas(parametros)

    if fecha_desde:
        filas = filas.filter(fecha_egreso_carrera__gte=fecha_desde)

    if fecha_hasta:
        filas = filas.filter(fecha_egreso_carrera__lte=fecha_hasta)

    return filas.order_by("legajo_graduado_id", "codigo_carrera_id")


@dataclass
class FilaBusquedaGraduado:
    """
    Fila del buscador: un graduado y una de sus carreras.

    Si el graduado no tiene carrera, ``carrera`` es ``None`` y las
    propiedades dependientes de carrera devuelven valores vacíos.
    Los atributos con nombre ``legajo_graduado_id``,
    ``codigo_carrera_id``, etc. se conservan para que la plantilla
    y el marcado de analíticos sigan usando la misma interfaz.
    """

    graduado: Graduado
    carrera: object = None
    cantidad_carreras: int = 0
    sin_carrera: bool = False
    analitico_titulo: bool = False
    analitico_tramite: bool = False

    @property
    def legajo_graduado_id(self):
        return self.graduado.pk

    @property
    def legajo_graduado(self):
        return self.graduado

    @property
    def anio_ingreso_universidad(self):
        return self.graduado.anio_ingreso_universidad

    @property
    def codigo_carrera_id(self):
        return self.carrera.codigo_carrera_id if self.carrera else None

    @property
    def codigo_carrera(self):
        return self.carrera.codigo_carrera if self.carrera else None

    @property
    def fecha_ingreso_carrera(self):
        return self.carrera.fecha_ingreso_carrera if self.carrera else None

    @property
    def fecha_egreso_carrera(self):
        return self.carrera.fecha_egreso_carrera if self.carrera else None

    @property
    def promedio_sin_aplazo(self):
        return self.carrera.promedio_sin_aplazo if self.carrera else None

    @property
    def promedio_con_aplazo(self):
        return self.carrera.promedio_con_aplazo if self.carrera else None


def _valor(parametros, clave):
    valor = parametros.get(clave)
    return valor.strip() if isinstance(valor, str) else ""


def _relacion_coincide(relacion, carrera, escuela, fecha_desde, fecha_hasta):
    """Aplica los filtros de carrera a una relación ya recuperada."""

    if carrera and str(relacion.codigo_carrera_id) != str(carrera):
        return False

    if escuela and str(relacion.codigo_carrera.id_escuela_id) != str(escuela):
        return False

    if fecha_desde and relacion.fecha_egreso_carrera < fecha_desde:
        return False

    if fecha_hasta and relacion.fecha_egreso_carrera > fecha_hasta:
        return False

    return True


def _ordenar_filas_busqueda(filas, orden):
    def clave(fila):
        legajo = fila.legajo_graduado_id or ""
        codigo = fila.codigo_carrera_id or ""
        apellido = (fila.graduado.apellido or "").lower()
        nombre = (fila.graduado.nombre or "").lower()
        anio = fila.graduado.anio_ingreso_universidad or 0

        if orden == "legajo":
            return legajo, codigo

        if orden == "apellido":
            return apellido, nombre, legajo, codigo

        if orden == "ingreso_uarg_asc":
            return anio, legajo, codigo

        if orden == "ingreso_uarg_desc":
            return -anio, legajo, codigo

        if orden == "menos_carreras":
            return fila.cantidad_carreras, legajo, codigo

        # «inconsistencias» es el orden por defecto: primero los
        # graduados sin carrera, luego quienes tienen menos carreras.
        return (
            0 if fila.sin_carrera else 1,
            fila.cantidad_carreras,
            legajo,
            codigo,
        )

    return sorted(filas, key=clave)


def obtener_filas_busqueda(parametros):
    """
    Filas del buscador de graduados.

    A diferencia de ``obtener_filas_filtradas`` (usada por Excel),
    la consulta arranca de GRADUADO: siempre se devuelve el
    graduado y, si tiene carreras, una fila por cada una de ellas.
    Los graduados sin carrera también se devuelven, con los datos
    de carrera vacíos para que la plantilla muestre «Vacio».

    ``situacion`` permite aislar a los graduados sin carrera o a
    los que tienen alguna. Cuando se elige «sin_carrera», ese
    filtro prevalece sobre carrera/escuela/fechas, que no tienen
    sentido para esos legajos.
    """

    graduados = Graduado.objects.all()

    nombre = _valor(parametros, "nombre")
    if nombre:
        for palabra in nombre.split():
            graduados = graduados.filter(
                Q(nombre__icontains=palabra)
                | Q(apellido__icontains=palabra)
            )

    legajo = _valor(parametros, "legajo")
    if legajo:
        graduados = graduados.filter(legajo_graduado__icontains=legajo)

    situacion = _valor(parametros, "situacion") or "todas"
    if situacion not in SITUACIONES_BUSQUEDA:
        situacion = "todas"

    orden = _valor(parametros, "orden") or "inconsistencias"
    if orden not in ORDENES_BUSQUEDA:
        orden = "inconsistencias"

    carrera = _valor(parametros, "carrera")
    escuela = _valor(parametros, "escuela")
    fecha_desde, fecha_hasta = _fechas(parametros)

    filtro_carrera = bool(
        carrera or escuela or fecha_desde or fecha_hasta
    )

    graduados = list(graduados)
    legajos = [graduado.pk for graduado in graduados]

    carreras_por_legajo = defaultdict(list)

    # Se cargan todas las carreras de los graduados candidatos para
    # conocer la cantidad real: incluso con «sin_carrera» hay que
    # distinguir quién no tiene ninguna de quién tiene aunque haya
    # que ignorar los filtros de carrera/escuela/fecha.
    if legajos:
        relaciones = GraduadoCarrera.objects.filter(
            legajo_graduado_id__in=legajos
        ).select_related(
            "codigo_carrera",
            "codigo_carrera__id_escuela",
        )

        for relacion in relaciones:
            carreras_por_legajo[relacion.legajo_graduado_id].append(relacion)

    filas = []

    for graduado in graduados:
        todas = carreras_por_legajo.get(graduado.pk, [])
        cantidad_carreras = len(todas)

        if situacion == "sin_carrera" and cantidad_carreras:
            continue

        if situacion == "con_carrera" and not cantidad_carreras:
            continue

        if situacion == "sin_carrera":
            relaciones = []
        elif filtro_carrera:
            relaciones = [
                relacion
                for relacion in todas
                if _relacion_coincide(
                    relacion,
                    carrera,
                    escuela,
                    fecha_desde,
                    fecha_hasta,
                )
            ]

            if not relaciones:
                continue
        else:
            relaciones = todas

        if not relaciones:
            filas.append(
                FilaBusquedaGraduado(
                    graduado=graduado,
                    cantidad_carreras=cantidad_carreras,
                    sin_carrera=True,
                )
            )
            continue

        for relacion in relaciones:
            filas.append(
                FilaBusquedaGraduado(
                    graduado=graduado,
                    carrera=relacion,
                    cantidad_carreras=cantidad_carreras,
                )
            )

    return _ordenar_filas_busqueda(filas, orden)

