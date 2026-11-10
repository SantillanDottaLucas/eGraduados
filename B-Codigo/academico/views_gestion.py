"""
Vistas de gestión: edición de graduados y ABM académico
(escuelas, carreras, planes de estudio, materias y las
materias de cada plan).
"""

from urllib.parse import parse_qsl, urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .autenticacion import requiere_sesion
from .forms import (
    CarreraForm,
    EdicionGraduadoForm,
    EscuelaForm,
    GrupoOptativoForm,
    MateriaForm,
    PlanEstudiosForm,
    PlanEstudiosGrupoOptativoForm,
    PlanEstudiosMateriaForm,
    ResolucionForm,
)
from .models import (
    Carrera,
    CarreraResolucion,
    Ciudad,
    DatosNacimiento,
    Escuela,
    Graduado,
    GraduadoCarrera,
    GrupoOptativo,
    Materia,
    PlanEstudios,
    PlanEstudiosGrupoOptativo,
    PlanEstudiosMateria,
    Provincia,
    Resolucion,
    Secundario,
    TipoResolucion,
)
from .servicios.validaciones import validar_dni_unico


# Filtros de la lista de graduados que se preservan al volver.
FILTROS_LISTA = {
    "nombre",
    "legajo",
    "escuela",
    "carrera",
    "fecha_desde",
    "fecha_hasta",
}

# Entidades del ABM académico.
ENTIDADES = (
    "escuela",
    "carrera",
    "plan",
    "materia",
    "plan_materia",
    "grupo_optativo",
)


# ==================================================
# AYUDAS GENERALES
# ==================================================

def _obtener_o_crear_provincia(nombre):
    nombre = (nombre or "").strip()

    if not nombre:
        return None

    provincia, _ = Provincia.objects.get_or_create(
        nombre_provincia=nombre,
        defaults={"nombre_provincia": nombre},
    )

    return provincia


def _obtener_o_crear_ciudad(nombre, id_provincia):
    nombre = (nombre or "").strip()

    if not nombre or id_provincia is None:
        return None

    ciudad, _ = Ciudad.objects.get_or_create(
        nombre_ciudad=nombre,
        defaults={
            "nombre_ciudad": nombre,
            "id_provincia": id_provincia,
        },
    )

    return ciudad


def _url_lista_con_filtros(volver):
    """
    Construye la URL de la lista de graduados preservando
    sólo los filtros conocidos.
    """

    destino = reverse("lista_graduados")

    parametros = [
        (clave, valor)
        for clave, valor in parse_qsl(volver or "")
        if clave in FILTROS_LISTA
    ]

    if parametros:
        destino += "?" + urlencode(parametros)

    return destino


def _redirigir_gestion(entidad, **extra):
    """Redirige a la pestaña indicada de la gestión académica."""

    destino = reverse("gestion_academica")

    parametros = {"entidad": entidad}
    parametros.update(extra)

    return redirect(destino + "?" + urlencode(parametros))


def _entero(valor):
    """Convierte un valor a entero o None."""

    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


# ==================================================
# EDICIÓN DE GRADUADOS
# ==================================================

@requiere_sesion
def editar_graduado(request, legajo, carrera):
    """
    Edita los datos personales de un graduado y su relación
    con una carrera (fila del listado de graduados).
    """

    graduado = get_object_or_404(
        Graduado,
        legajo_graduado=legajo,
    )

    registro = get_object_or_404(
        GraduadoCarrera.objects.select_related(
            "codigo_carrera"
        ),
        legajo_graduado=graduado,
        codigo_carrera_id=carrera,
    )

    volver = request.GET.get("volver", "")

    if request.method == "POST":
        volver = request.POST.get("volver", "")

        form = EdicionGraduadoForm(request.POST)

        if form.is_valid():
            datos = form.cleaned_data
            carrera_nueva = datos["codigo_carrera"]
            cambio_carrera = (
                carrera_nueva.codigo_carrera != registro.codigo_carrera_id
            )

            # No puede duplicar la fila (legajo, nueva carrera).
            if cambio_carrera and GraduadoCarrera.objects.filter(
                legajo_graduado=graduado,
                codigo_carrera=carrera_nueva,
            ).exists():
                form.add_error(
                    "codigo_carrera",
                    "El graduado ya tiene datos cargados para esa carrera.",
                )

            # El DNI no puede pertenecer a otro legajo.
            elif not validar_dni_unico(datos["dni"], legajo):
                form.add_error(
                    "dni",
                    "El DNI ya está asociado a otro graduado.",
                )

            else:
                with transaction.atomic():
                    graduado.nombre = datos["nombre"]
                    graduado.apellido = datos["apellido"]
                    graduado.dni = datos["dni"]
                    graduado.fecha_ingreso_universidad = (
                        datos["fecha_ingreso_universidad"]
                    )
                    graduado.save()

                    # Un cambio de carrera modifica la clave
                    # primaria compuesta (legajo, carrera).
                    # Se migra la fila dentro de la transacción.
                    if cambio_carrera:
                        GraduadoCarrera.objects.create(
                            legajo_graduado=graduado,
                            codigo_carrera=carrera_nueva,
                            fecha_ingreso_carrera=(
                                datos["fecha_ingreso_carrera"]
                            ),
                            fecha_egreso_carrera=(
                                datos["fecha_egreso_carrera"]
                            ),
                            promedio_sin_aplazo=(
                                datos["promedio_sin_aplazo"]
                            ),
                            promedio_con_aplazo=(
                                datos["promedio_con_aplazo"]
                            ),
                        )
                        registro.delete()

                    else:
                        registro.fecha_ingreso_carrera = (
                            datos["fecha_ingreso_carrera"]
                        )
                        registro.fecha_egreso_carrera = (
                            datos["fecha_egreso_carrera"]
                        )
                        registro.promedio_sin_aplazo = (
                            datos["promedio_sin_aplazo"]
                        )
                        registro.promedio_con_aplazo = (
                            datos["promedio_con_aplazo"]
                        )
                        registro.save()

                    # Datos de nacimiento (todos opcionales;
                    # sólo se guardan si se completa algo).
                    fecha_nac = datos.get("fecha_nacimiento")
                    ciudad_nac = (datos.get("ciudad_nacimiento") or "").strip()
                    provincia_nac = (datos.get("provincia_nacimiento") or "").strip()

                    if any([fecha_nac, ciudad_nac, provincia_nac]):
                        provincia_obj = _obtener_o_crear_provincia(
                            provincia_nac
                        )
                        ciudad_obj = _obtener_o_crear_ciudad(
                            ciudad_nac,
                            provincia_obj,
                        )

                        nacimiento = (
                            DatosNacimiento.objects
                            .filter(legajo_graduado=graduado)
                            .first()
                        )

                        if nacimiento is not None:
                            nacimiento.fecha_nacimiento = fecha_nac
                            nacimiento.id_provincia = provincia_obj
                            nacimiento.id_ciudad = ciudad_obj
                            nacimiento.save()
                        else:
                            DatosNacimiento.objects.create(
                                legajo_graduado=graduado,
                                fecha_nacimiento=fecha_nac,
                                id_provincia=provincia_obj,
                                id_ciudad=ciudad_obj,
                            )

                    # Datos del secundario (todos opcionales;
                    # sólo se guardan si se completa algo).
                    nombre_sec = (
                        datos.get("nombre_secundario") or ""
                    ).strip()
                    titulo_sec = (
                        datos.get("titulo_secundario") or ""
                    ).strip()
                    ciudad_sec = (
                        datos.get("ciudad_secundario") or ""
                    ).strip()
                    provincia_sec = (
                        datos.get("provincia_secundario") or ""
                    ).strip()
                    anio_sec = datos.get("anio_egreso_secundario")

                    if any([
                        nombre_sec,
                        titulo_sec,
                        ciudad_sec,
                        provincia_sec,
                        anio_sec,
                    ]):
                        provincia_obj_sec = _obtener_o_crear_provincia(
                            provincia_sec
                        )
                        ciudad_obj_sec = _obtener_o_crear_ciudad(
                            ciudad_sec,
                            provincia_obj_sec,
                        )

                        if nombre_sec:
                            secundario, _ = Secundario.objects.get_or_create(
                                nombre_secundario=nombre_sec,
                                defaults={
                                    "legajo_graduado": graduado,
                                    "id_provincia": provincia_obj_sec,
                                    "id_ciudad": ciudad_obj_sec,
                                },
                            )
                        else:
                            secundario = (
                                Secundario.objects
                                .filter(legajo_graduado=graduado)
                                .first()
                            )

                        if secundario is not None:
                            secundario.legajo_graduado = graduado
                            secundario.id_provincia = provincia_obj_sec
                            secundario.id_ciudad = ciudad_obj_sec
                            secundario.titulo_secundario = titulo_sec
                            secundario.anio_egreso_secundario = anio_sec
                            secundario.save()

                messages.success(
                    request,
                    (
                        f"Datos de {graduado} actualizados "
                        "correctamente."
                    ),
                )

                return redirect(_url_lista_con_filtros(volver))

    else:
        nacimiento = (
            DatosNacimiento.objects
            .filter(legajo_graduado=graduado)
            .select_related("id_ciudad", "id_provincia")
            .first()
        )
        secundario = (
            Secundario.objects
            .filter(legajo_graduado=graduado)
            .select_related("id_ciudad", "id_provincia")
            .first()
        )

        form = EdicionGraduadoForm(
            initial={
                "codigo_carrera": registro.codigo_carrera_id,
                "nombre": graduado.nombre,
                "apellido": graduado.apellido,
                "dni": graduado.dni,
                "fecha_ingreso_universidad": (
                    graduado.fecha_ingreso_universidad
                ),
                "fecha_ingreso_carrera": (
                    registro.fecha_ingreso_carrera
                ),
                "fecha_egreso_carrera": (
                    registro.fecha_egreso_carrera
                ),
                "promedio_sin_aplazo": registro.promedio_sin_aplazo,
                "promedio_con_aplazo": registro.promedio_con_aplazo,
                "fecha_nacimiento": (
                    nacimiento.fecha_nacimiento if nacimiento else None
                ),
                "ciudad_nacimiento": (
                    nacimiento.id_ciudad.nombre_ciudad
                    if nacimiento and nacimiento.id_ciudad else ""
                ),
                "provincia_nacimiento": (
                    nacimiento.id_provincia.nombre_provincia
                    if nacimiento and nacimiento.id_provincia else ""
                ),
                "nombre_secundario": (
                    secundario.nombre_secundario if secundario else ""
                ),
                "titulo_secundario": (
                    secundario.titulo_secundario if secundario else ""
                ),
                "ciudad_secundario": (
                    secundario.id_ciudad.nombre_ciudad
                    if secundario and secundario.id_ciudad else ""
                ),
                "provincia_secundario": (
                    secundario.id_provincia.nombre_provincia
                    if secundario and secundario.id_provincia else ""
                ),
                "anio_egreso_secundario": (
                    secundario.anio_egreso_secundario
                    if secundario else None
                ),
            }
        )

    contexto = {
        "form": form,
        "graduado": graduado,
        "registro": registro,
        "volver": volver,
        "provincias": list(
            Provincia.objects.order_by("nombre_provincia")
            .values_list("nombre_provincia", flat=True)
        ),
        "ciudades": list(
            Ciudad.objects.order_by("nombre_ciudad")
            .values_list("nombre_ciudad", flat=True)
        ),
    }

    return render(
        request,
        "academico/editar_graduado.html",
        contexto,
    )


# ==================================================
# ABM ACADÉMICO
# ==================================================

# --------------------------------------------------
# Búsquedas por clave primaria
# --------------------------------------------------

def _buscar_escuela(valor):
    identificador = _entero(valor)

    if identificador is None:
        return None

    return Escuela.objects.filter(
        id_escuela=identificador
    ).first()


def _buscar_carrera(valor):
    if not valor:
        return None

    return Carrera.objects.filter(
        codigo_carrera=valor
    ).first()


def _buscar_resolucion(valor):
    if not valor:
        return None

    return Resolucion.objects.filter(
        resolucion=valor
    ).first()


def _buscar_plan(valor):
    if not valor:
        return None

    return PlanEstudios.objects.filter(
        codigo_plan=valor
    ).first()


def _buscar_materia(valor):
    if not valor:
        return None

    return Materia.objects.filter(
        codigo_materia=valor
    ).first()


def _buscar_plan_materia(plan, materia):
    if not plan or not materia:
        return None

    return PlanEstudiosMateria.objects.filter(
        codigo_plan_id=plan,
        codigo_materia_id=materia,
    ).first()


def _buscar_grupo_optativo(valor):
    identificador = _entero(valor)

    if identificador is None:
        return None

    return GrupoOptativo.objects.filter(
        id_grupo_optativo=identificador
    ).first()


def _contexto_resoluciones(carrera=None):
    """
    Construye los grupos de resoluciones por tipo (para el
    checklist del ABM de carreras) y los ids seleccionados
    para la carrera en edición.
    """

    orden = [
        TipoResolucion.INSTITUCIONAL,
        TipoResolucion.MINISTERIAL_NACIONAL,
        TipoResolucion.OTRO_INSTRUMENTO,
    ]
    etiquetas = dict(TipoResolucion.choices)

    resoluciones = list(
        Resolucion.objects.order_by("resolucion")
    )

    grupos = []

    for clave in orden:
        grupos.append({
            "clave": clave,
            "etiqueta": etiquetas[clave],
            "items": [
                r for r in resoluciones
                if r.tipo_resolucion == clave
            ],
        })

    seleccionadas = set()

    if carrera is not None and carrera.pk:
        seleccionadas = set(
            CarreraResolucion.objects
            .filter(codigo_carrera=carrera)
            .values_list("resolucion", flat=True)
        )

    return {
        "resoluciones_agrupadas": grupos,
        "resoluciones_seleccionadas": seleccionadas,
        "form_resolucion": ResolucionForm(),
    }


def _sincronizar_resoluciones(carrera, seleccion):
    """Sincroniza CARRERA_RESOLUCION con la selección del POST."""

    deseadas = set(
        Resolucion.objects
        .filter(resolucion__in=seleccion)
        .values_list("resolucion", flat=True)
    )

    actuales = set(
        CarreraResolucion.objects
        .filter(codigo_carrera=carrera)
        .values_list("resolucion", flat=True)
    )

    for nueva in deseadas - actuales:
        CarreraResolucion.objects.create(
            codigo_carrera=carrera,
            resolucion_id=nueva,
        )

    CarreraResolucion.objects.filter(
        codigo_carrera=carrera,
        resolucion__in=actuales - deseadas,
    ).delete()


def _cronograma_plan(plan):
    """
    Construye el cronograma intercalado del plan: materias
    comunes, grupos optativos ubicados y materias miembro
    (que heredan año/cuatrimestre/orden de su grupo).
    """

    filas = []

    if plan is None:
        return filas

    materias = (
        PlanEstudiosMateria.objects
        .filter(codigo_plan=plan)
        .select_related("codigo_materia", "id_grupo_optativo")
    )

    miembros = {}

    for asociacion in materias:
        if asociacion.id_grupo_optativo_id:
            miembros.setdefault(
                asociacion.id_grupo_optativo_id,
                [],
            ).append(asociacion)

        else:
            filas.append({
                "tipo": "materia",
                "anio": asociacion.anio_materia,
                "cuatrimestre": asociacion.cuatrimestre_materia,
                "orden": asociacion.orden_materia,
                "nombre": asociacion.codigo_materia.nombre_materia,
                "requisito": asociacion.materia_requisito,
                "miembro": False,
                "id_grupo": None,
                "editar_plan": asociacion.codigo_plan_id,
                "editar_materia": asociacion.codigo_materia_id,
            })

    ubicaciones = (
        PlanEstudiosGrupoOptativo.objects
        .filter(codigo_plan=plan)
        .select_related("id_grupo_optativo")
    )

    grupos_ubicados = set()

    for ubicacion in ubicaciones:
        grupo = ubicacion.id_grupo_optativo
        grupos_ubicados.add(grupo.id_grupo_optativo)

        filas.append({
            "tipo": "grupo",
            "anio": ubicacion.anio_materia,
            "cuatrimestre": ubicacion.cuatrimestre_materia,
            "orden": ubicacion.orden_materia,
            "nombre": grupo.nombre_grupo,
            "requisito": False,
            "miembro": False,
            "id_grupo": grupo.id_grupo_optativo,
            "miembros": miembros.get(grupo.id_grupo_optativo, []),
            "editar_plan": None,
            "editar_materia": None,
        })

        for miembro in miembros.get(grupo.id_grupo_optativo, []):
            filas.append({
                "tipo": "miembro",
                "anio": ubicacion.anio_materia,
                "cuatrimestre": ubicacion.cuatrimestre_materia,
                "orden": ubicacion.orden_materia,
                "nombre": miembro.codigo_materia.nombre_materia,
                "requisito": miembro.materia_requisito,
                "miembro": True,
                "id_grupo": grupo.id_grupo_optativo,
                "editar_plan": miembro.codigo_plan_id,
                "editar_materia": miembro.codigo_materia_id,
            })

    # Materias miembro de grupos todavía no ubicados en el plan.
    for grupo_id, lista in miembros.items():
        if grupo_id in grupos_ubicados:
            continue

        for miembro in lista:
            filas.append({
                "tipo": "miembro_sin_ubicar",
                "anio": None,
                "cuatrimestre": None,
                "orden": None,
                "nombre": miembro.codigo_materia.nombre_materia,
                "requisito": miembro.materia_requisito,
                "miembro": True,
                "id_grupo": grupo_id,
                "editar_plan": miembro.codigo_plan_id,
                "editar_materia": miembro.codigo_materia_id,
            })

    def _clave(fila):
        return (
            fila["anio"] if fila["anio"] is not None else 99,
            fila["cuatrimestre"] or "zz",
            fila["orden"] if fila["orden"] is not None else 99,
            1 if fila["tipo"] == "miembro" else 0,
        )

    filas.sort(key=_clave)

    return filas


BUSCADORES = {
    "escuela": lambda valor: _buscar_escuela(valor),
    "carrera": lambda valor: _buscar_carrera(valor),
    "plan": lambda valor: _buscar_plan(valor),
    "materia": lambda valor: _buscar_materia(valor),
}


# --------------------------------------------------
# Vista principal
# --------------------------------------------------

@requiere_sesion
def gestion_academica(request):
    """
    ABM de escuelas, carreras, planes de estudio, materias y
    las materias asociadas a cada plan.
    """

    # ==========================================
    # 1. DATOS DE TODAS LAS PESTAÑAS
    # ==========================================

    escuelas = Escuela.objects.order_by("nombre_escuela")

    carreras = (
        Carrera.objects
        .select_related("id_escuela")
        .order_by("nombre_carrera")
    )

    planes = (
        PlanEstudios.objects
        .select_related("codigo_carrera")
        .order_by("codigo_plan")
    )

    materias = Materia.objects.order_by("nombre_materia")

    grupos_optativos = GrupoOptativo.objects.order_by(
        "nombre_grupo"
    )

    # ==========================================
    # 2. ENTIDAD ACTIVA (PESTAÑA VISIBLE)
    # ==========================================

    if request.method == "POST":
        entidad_activa = (
            request.POST.get("entidad")
            if request.POST.get("entidad") in ENTIDADES
            else "escuela"
        )

    else:
        entidad_activa = (
            request.GET.get("entidad")
            if request.GET.get("entidad") in ENTIDADES
            else "escuela"
        )

    # ==========================================
    # 3. PLAN SELECCIONADO (PESTAÑA MATERIAS DEL PLAN)
    # ==========================================

    plan_seleccionado = None

    if request.method == "POST":
        valor_plan = request.POST.get("plan") or None
    else:
        valor_plan = request.GET.get("plan") or None

    plan_seleccionado = _buscar_plan(valor_plan)

    if plan_seleccionado is None:
        # Por defecto se muestra el primer plan disponible.
        plan_seleccionado = (
            PlanEstudios.objects
            .order_by("codigo_plan")
            .first()
        )

    if plan_seleccionado is not None:
        materias_del_plan = list(
            PlanEstudiosMateria.objects
            .filter(codigo_plan=plan_seleccionado)
            .select_related("codigo_materia", "id_grupo_optativo")
            .order_by(
                "anio_materia",
                "cuatrimestre_materia",
                "orden_materia",
            )
        )
    else:
        materias_del_plan = []

    filas_plan = _cronograma_plan(plan_seleccionado)

    grupos_del_plan = []

    if plan_seleccionado is not None:
        grupos_del_plan = list(
            GrupoOptativo.objects
            .filter(codigo_plan=plan_seleccionado)
            .prefetch_related("ubicaciones", "materias")
            .order_by("nombre_grupo")
        )

    # ==========================================
    # 4. FORMULARIOS POR DEFECTO
    # ==========================================

    form_escuela = EscuelaForm()
    form_carrera = CarreraForm()
    form_plan = PlanEstudiosForm()
    form_materia = MateriaForm()
    form_plan_materia = PlanEstudiosMateriaForm(
        plan_inicial=(
            plan_seleccionado.codigo_plan
            if plan_seleccionado else None
        ),
    )
    form_grupo_optativo = GrupoOptativoForm(
        plan=plan_seleccionado,
    )
    form_ubicacion = PlanEstudiosGrupoOptativoForm(
        plan=plan_seleccionado,
    )

    # Instancia en edición (para el título del formulario).
    instancia_editar = None

    # ==========================================
    # 5. PROCESAR ACCIONES POR POST
    # ==========================================

    if request.method == "POST":
        return _procesar_post_gestion(request, entidad_activa)

    # ==========================================
    # 6. PRECARGAR FORMULARIO PARA EDITAR (GET)
    # ==========================================

    if entidad_activa == "plan_materia":
        instancia_editar = _buscar_plan_materia(
            request.GET.get("editar_plan"),
            request.GET.get("editar_materia"),
        )

        if instancia_editar is not None:
            form_plan_materia = PlanEstudiosMateriaForm(
                instance=instancia_editar,
                plan_inicial=(
                    plan_seleccionado.codigo_plan
                    if plan_seleccionado else None
                ),
            )

    elif entidad_activa == "grupo_optativo":
        instancia_editar = _buscar_grupo_optativo(
            request.GET.get("editar_grupo")
        )

        if instancia_editar is not None:
            form_grupo_optativo = GrupoOptativoForm(
                instance=instancia_editar,
                plan=plan_seleccionado,
            )

        ubicar_grupo = _buscar_grupo_optativo(
            request.GET.get("ubicar_grupo")
        )

        if ubicar_grupo is not None:
            ubicacion = PlanEstudiosGrupoOptativo.objects.filter(
                codigo_plan=plan_seleccionado,
                id_grupo_optativo=ubicar_grupo,
            ).first()

            initial = {
                "id_grupo_optativo": ubicar_grupo,
            }

            if ubicacion is not None:
                initial.update({
                    "anio_materia": ubicacion.anio_materia,
                    "cuatrimestre_materia": (
                        ubicacion.cuatrimestre_materia
                    ),
                    "orden_materia": ubicacion.orden_materia,
                })

            form_ubicacion = PlanEstudiosGrupoOptativoForm(
                plan=plan_seleccionado,
                initial=initial,
            )

    else:
        instancia_editar = BUSCADORES[entidad_activa](
            request.GET.get("editar")
        )

        if instancia_editar is not None:
            if entidad_activa == "escuela":
                form_escuela = EscuelaForm(
                    instance=instancia_editar
                )

            elif entidad_activa == "carrera":
                form_carrera = CarreraForm(
                    instance=instancia_editar
                )

            elif entidad_activa == "plan":
                form_plan = PlanEstudiosForm(
                    instance=instancia_editar
                )

            elif entidad_activa == "materia":
                form_materia = MateriaForm(
                    instance=instancia_editar
                )

    # ==========================================
    # 7. RENDERIZAR
    # ==========================================

    carrera_editar = (
        instancia_editar
        if entidad_activa == "carrera" and instancia_editar is not None
        else None
    )

    contexto = {
        "entidad_activa": entidad_activa,
        "instancia_editar": instancia_editar,

        "form_escuela": form_escuela,
        "form_carrera": form_carrera,
        "form_plan": form_plan,
        "form_materia": form_materia,
        "form_plan_materia": form_plan_materia,
        "form_grupo_optativo": form_grupo_optativo,
        "form_ubicacion": form_ubicacion,

        "escuelas": escuelas,
        "carreras": carreras,
        "planes": planes,
        "materias": materias,
        "grupos_optativos": grupos_optativos,
        "grupos_del_plan": grupos_del_plan,

        "plan_seleccionado": plan_seleccionado,
        "materias_del_plan": materias_del_plan,
        "filas_plan": filas_plan,

        # Catálogo de resoluciones (checklist del ABM de carreras).
        **_contexto_resoluciones(carrera_editar),
    }

    return render(
        request,
        "academico/gestion_academica.html",
        contexto,
    )


def _procesar_post_gestion(request, entidad):
    """
    Ejecuta la acción indicada (guardar o eliminar) sobre
    la entidad correspondiente y redirige a la pestaña activa.
    """

    accion = request.POST.get("accion", "guardar")

    # ==========================================
    # ESCUELAS
    # ==========================================

    if entidad == "escuela":

        if accion == "eliminar":
            objetivo = _buscar_escuela(request.POST.get("id"))

            return _eliminar_instancia(
                request,
                objetivo,
                "la escuela",
                {"entidad": "escuela"},
            )

        instancia = _buscar_escuela(request.POST.get("id"))
        form = EscuelaForm(request.POST, instance=instancia)

        if form.is_valid():
            escuela = form.save()
            messages.success(
                request,
                f"Escuela {escuela.nombre_escuela} guardada.",
            )

            return _redirigir_gestion("escuela")

        return _re_render_gestion(
            request, "escuela", form, "form_escuela"
        )

    # ==========================================
    # CARRERAS
    # ==========================================

    elif entidad == "carrera":

        if accion == "crear_resolucion":
            form_res = ResolucionForm(request.POST)

            if form_res.is_valid():
                res = form_res.save()
                messages.success(
                    request,
                    f"Resolución {res.resolucion} creada.",
                )

            else:
                for errores in form_res.errors.values():
                    messages.error(request, errores[0])

            parametros_vuelta = {}

            if request.POST.get("id"):
                parametros_vuelta["editar"] = request.POST.get("id")

            return _redirigir_gestion("carrera", **parametros_vuelta)

        if accion == "eliminar_resolucion":
            instancia_res = _buscar_resolucion(request.POST.get("id"))

            if instancia_res is None:
                messages.error(
                    request,
                    "No se encontró la resolución indicada.",
                )

            elif CarreraResolucion.objects.filter(
                resolucion=instancia_res
            ).exists():
                messages.error(
                    request,
                    (
                        f"No se puede eliminar «{instancia_res.resolucion}» "
                        "porque está asociada a una carrera."
                    ),
                )

            else:
                instancia_res.delete()
                messages.success(
                    request,
                    f"Se eliminó la resolución {instancia_res.resolucion}.",
                )

            return _redirigir_gestion("carrera")

        if accion == "eliminar":
            objetivo = _buscar_carrera(request.POST.get("id"))

            return _eliminar_instancia(
                request,
                objetivo,
                "la carrera",
                {"entidad": "carrera"},
            )

        instancia = _buscar_carrera(request.POST.get("id"))
        form = CarreraForm(request.POST, instance=instancia)

        if form.is_valid():
            carrera_obj = form.save()
            _sincronizar_resoluciones(
                carrera_obj,
                request.POST.getlist("resoluciones"),
            )
            carrera = carrera_obj
            messages.success(
                request,
                f"Carrera {carrera.nombre_carrera} guardada.",
            )

            return _redirigir_gestion("carrera")

        return _re_render_gestion(
            request, "carrera", form, "form_carrera", carrera=instancia
        )

    # ==========================================
    # PLANES DE ESTUDIO
    # ==========================================

    elif entidad == "plan":

        if accion == "eliminar":
            objetivo = _buscar_plan(request.POST.get("id"))

            return _eliminar_instancia(
                request,
                objetivo,
                "el plan de estudios",
                {"entidad": "plan"},
            )

        instancia = _buscar_plan(request.POST.get("id"))
        form = PlanEstudiosForm(request.POST, instance=instancia)

        if form.is_valid():
            plan = form.save()
            messages.success(
                request,
                f"Plan {plan.codigo_plan} guardado.",
            )

            return _redirigir_gestion("plan")

        return _re_render_gestion(
            request, "plan", form, "form_plan"
        )

    # ==========================================
    # MATERIAS
    # ==========================================

    elif entidad == "materia":

        if accion == "eliminar":
            objetivo = _buscar_materia(request.POST.get("id"))

            return _eliminar_instancia(
                request,
                objetivo,
                "la materia",
                {"entidad": "materia"},
            )

        instancia = _buscar_materia(request.POST.get("id"))
        form = MateriaForm(request.POST, instance=instancia)

        if form.is_valid():
            materia = form.save()
            messages.success(
                request,
                f"Materia {materia.nombre_materia} guardada.",
            )

            return _redirigir_gestion("materia")

        return _re_render_gestion(
            request, "materia", form, "form_materia"
        )

    # ==========================================
    # MATERIAS DEL PLAN
    # ==========================================

    elif entidad == "plan_materia":

        if accion == "eliminar":
            objetivo = _buscar_plan_materia(
                request.POST.get("id_plan"),
                request.POST.get("id_materia"),
            )

            return _eliminar_instancia(
                request,
                objetivo,
                "la materia del plan",
                {
                    "entidad": "plan_materia",
                    "plan": request.POST.get("id_plan") or "",
                },
            )

        instancia = _buscar_plan_materia(
            request.POST.get("id_plan"),
            request.POST.get("id_materia"),
        )

        plan = request.POST.get("plan") or None
        plan_objeto = _buscar_plan(plan)

        form = PlanEstudiosMateriaForm(
            request.POST,
            instance=instancia,
            plan_inicial=(
                plan_objeto.codigo_plan if plan_objeto else None
            ),
        )

        if form.is_valid():
            asociacion = form.save()
            messages.success(
                request,
                (
                    f"Materia {asociacion.codigo_materia} "
                    f"asociada al plan "
                    f"{asociacion.codigo_plan_id}."
                ),
            )

            return _redirigir_gestion(
                "plan_materia",
                plan=(
                    instancia.codigo_plan_id
                    if instancia is not None
                    else (plan_objeto.codigo_plan if plan_objeto else "")
                ),
            )

        return _re_render_gestion(
            request,
            "plan_materia",
            form,
            "form_plan_materia",
            plan=plan or "",
        )

    # ==========================================
    # GRUPOS OPTATIVOS
    # ==========================================

    elif entidad == "grupo_optativo":
        plan_objeto = _buscar_plan(
            request.POST.get("plan") or None
        )

        if plan_objeto is None:
            messages.error(
                request,
                "No se encontró el plan de estudios indicado.",
            )

            return _redirigir_gestion("grupo_optativo")

        # -- Ubicar el grupo en el cronograma del plan.
        if accion == "ubicar":
            form = PlanEstudiosGrupoOptativoForm(
                request.POST,
                plan=plan_objeto,
            )

            if form.is_valid():
                datos = form.cleaned_data
                grupo = datos["id_grupo_optativo"]

                PlanEstudiosGrupoOptativo.objects.update_or_create(
                    codigo_plan=plan_objeto,
                    id_grupo_optativo=grupo,
                    defaults={
                        "anio_materia": datos["anio_materia"],
                        "cuatrimestre_materia": (
                            datos["cuatrimestre_materia"]
                        ),
                        "orden_materia": datos["orden_materia"],
                    },
                )

                messages.success(
                    request,
                    (
                        f"Grupo optativo «{grupo.nombre_grupo}» "
                        "ubicado en el cronograma del plan."
                    ),
                )

                return _redirigir_gestion(
                    "grupo_optativo",
                    plan=plan_objeto.codigo_plan,
                )

            return _re_render_gestion(
                request,
                "grupo_optativo",
                form,
                "form_ubicacion",
                plan=plan_objeto.codigo_plan,
            )

        # -- Quitar la ubicación (el grupo sigue existiendo).
        if accion == "eliminar_ubicacion":
            grupo = _buscar_grupo_optativo(request.POST.get("id"))

            if grupo and grupo.codigo_plan_id == plan_objeto.codigo_plan:
                PlanEstudiosGrupoOptativo.objects.filter(
                    codigo_plan=plan_objeto,
                    id_grupo_optativo=grupo,
                ).delete()

                messages.success(
                    request,
                    (
                        f"Se quitó la ubicación del grupo "
                        f"«{grupo.nombre_grupo}». Las materias "
                        "miembro quedan a la espera de una nueva "
                        "ubicación."
                    ),
                )

            else:
                messages.error(
                    request,
                    "No se encontró el grupo optativo indicado.",
                )

            return _redirigir_gestion(
                "grupo_optativo",
                plan=plan_objeto.codigo_plan,
            )

        # -- Eliminar el grupo (bloqueado en uso).
        if accion == "eliminar_grupo":
            grupo = _buscar_grupo_optativo(request.POST.get("id"))

            if grupo and grupo.codigo_plan_id == plan_objeto.codigo_plan:
                tiene_miembros = PlanEstudiosMateria.objects.filter(
                    id_grupo_optativo=grupo,
                ).exists()

                esta_ubicado = PlanEstudiosGrupoOptativo.objects.filter(
                    codigo_plan=plan_objeto,
                    id_grupo_optativo=grupo,
                ).exists()

                if tiene_miembros or esta_ubicado:
                    messages.error(
                        request,
                        (
                            f"No se puede eliminar el grupo "
                            f"«{grupo.nombre_grupo}» porque tiene "
                            "materias asociadas o está ubicado en "
                            "el cronograma. Quitalo primero."
                        ),
                    )

                else:
                    grupo.delete()
                    messages.success(
                        request,
                        f"Se eliminó el grupo optativo: {grupo.nombre_grupo}.",
                    )

            else:
                messages.error(
                    request,
                    "No se encontró el grupo optativo indicado.",
                )

            return _redirigir_gestion(
                "grupo_optativo",
                plan=plan_objeto.codigo_plan,
            )

        # -- Crear o renombrar el grupo.
        instancia = None

        if request.POST.get("id"):
            instancia = _buscar_grupo_optativo(request.POST.get("id"))

            if (
                instancia is not None
                and instancia.codigo_plan_id != plan_objeto.codigo_plan
            ):
                instancia = None

        form = GrupoOptativoForm(
            request.POST,
            instance=instancia,
            plan=plan_objeto,
        )

        if form.is_valid():
            grupo = form.save(commit=False)
            grupo.codigo_plan = plan_objeto
            grupo.save()

            messages.success(
                request,
                f"Grupo optativo «{grupo.nombre_grupo}» guardado.",
            )

            return _redirigir_gestion(
                "grupo_optativo",
                plan=plan_objeto.codigo_plan,
            )

        return _re_render_gestion(
            request,
            "grupo_optativo",
            form,
            "form_grupo_optativo",
            plan=plan_objeto.codigo_plan,
        )

    return _redirigir_gestion("escuela")


def _eliminar_instancia(request, objetivo, descripcion, parametros):
    """
    Elimina una instancia con mensaje amigable cuando tiene
    dependencias protegidas.
    """

    if objetivo is None:
        messages.error(
            request,
            f"No se encontró {descripcion} indicada.",
        )

    else:
        try:
            objetivo.delete()
            messages.success(
                request,
                f"Se eliminó {descripcion}: {objetivo}.",
            )

        except ProtectedError:
            messages.error(
                request,
                (
                    f"No se puede eliminar {descripcion} "
                    "porque tiene registros asociados."
                ),
            )

    return _redirigir_gestion(
        parametros.get("entidad", "escuela"),
        **{
            clave: valor
            for clave, valor in parametros.items()
            if clave != "entidad"
        }
    )


def _re_render_gestion(request, entidad, form, nombre_form, **extra):
    """
    Vuelve a renderizar la página de gestión cuando el
    formulario tiene errores, mostrando la pestaña activa.
    """

    # Reconstruir todo el contexto con el formulario con errores.
    contexto = _contexto_gestion(
        request,
        entidad_activa=entidad,
        plan_valor=extra.get("plan") or None,
        carrera_editar=extra.get("carrera"),
    )

    contexto[nombre_form] = form

    return render(
        request,
        "academico/gestion_academica.html",
        contexto,
    )


def _contexto_gestion(request, entidad_activa, plan_valor=None,
                     carrera_editar=None):
    """Construye el contexto completo de la gestión académica."""

    escuelas = Escuela.objects.order_by("nombre_escuela")

    carreras = (
        Carrera.objects
        .select_related("id_escuela")
        .order_by("nombre_carrera")
    )

    planes = (
        PlanEstudios.objects
        .select_related("codigo_carrera")
        .order_by("codigo_plan")
    )

    materias = Materia.objects.order_by("nombre_materia")

    grupos_optativos = GrupoOptativo.objects.order_by(
        "nombre_grupo"
    )

    plan_seleccionado = _buscar_plan(plan_valor)

    if plan_seleccionado is None:
        plan_seleccionado = (
            PlanEstudios.objects
            .order_by("codigo_plan")
            .first()
        )

    if plan_seleccionado is not None:
        materias_del_plan = list(
            PlanEstudiosMateria.objects
            .filter(codigo_plan=plan_seleccionado)
            .select_related("codigo_materia", "id_grupo_optativo")
            .order_by(
                "anio_materia",
                "cuatrimestre_materia",
                "orden_materia",
            )
        )
    else:
        materias_del_plan = []

    filas_plan = _cronograma_plan(plan_seleccionado)

    grupos_del_plan = []

    if plan_seleccionado is not None:
        grupos_del_plan = list(
            GrupoOptativo.objects
            .filter(codigo_plan=plan_seleccionado)
            .prefetch_related("ubicaciones", "materias")
            .order_by("nombre_grupo")
        )

    plan_inicial = (
        plan_seleccionado.codigo_plan
        if plan_seleccionado else None
    )

    return {
        "entidad_activa": entidad_activa,
        "instancia_editar": None,

        "form_escuela": EscuelaForm(),
        "form_carrera": CarreraForm(),
        "form_plan": PlanEstudiosForm(),
        "form_materia": MateriaForm(),
        "form_plan_materia": PlanEstudiosMateriaForm(
            plan_inicial=plan_inicial,
        ),
        "form_grupo_optativo": GrupoOptativoForm(
            plan=plan_seleccionado,
        ),
        "form_ubicacion": PlanEstudiosGrupoOptativoForm(
            plan=plan_seleccionado,
        ),

        "escuelas": escuelas,
        "carreras": carreras,
        "planes": planes,
        "materias": materias,
        "grupos_optativos": grupos_optativos,
        "grupos_del_plan": grupos_del_plan,

        "plan_seleccionado": plan_seleccionado,
        "materias_del_plan": materias_del_plan,
        "filas_plan": filas_plan,

        # Catálogo de resoluciones (checklist del ABM de carreras).
        **_contexto_resoluciones(carrera_editar),
    }
