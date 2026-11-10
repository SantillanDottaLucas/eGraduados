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
    MateriaForm,
    PlanEstudiosForm,
    PlanEstudiosMateriaForm,
)
from .models import (
    Carrera,
    Escuela,
    Graduado,
    GraduadoCarrera,
    GrupoOptativo,
    Materia,
    PlanEstudios,
    PlanEstudiosMateria,
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
)


# ==================================================
# AYUDAS GENERALES
# ==================================================

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

            # El DNI no puede pertenecer a otro legajo.
            if not validar_dni_unico(datos["dni"], legajo):
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

                messages.success(
                    request,
                    (
                        f"Datos de {graduado} actualizados "
                        "correctamente."
                    ),
                )

                return redirect(_url_lista_con_filtros(volver))

    else:
        form = EdicionGraduadoForm(
            initial={
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
            }
        )

    contexto = {
        "form": form,
        "graduado": graduado,
        "registro": registro,
        "volver": volver,
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

    materias_del_plan = []

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

    contexto = {
        "entidad_activa": entidad_activa,
        "instancia_editar": instancia_editar,

        "form_escuela": form_escuela,
        "form_carrera": form_carrera,
        "form_plan": form_plan,
        "form_materia": form_materia,
        "form_plan_materia": form_plan_materia,

        "escuelas": escuelas,
        "carreras": carreras,
        "planes": planes,
        "materias": materias,
        "grupos_optativos": grupos_optativos,

        "plan_seleccionado": plan_seleccionado,
        "materias_del_plan": materias_del_plan,
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
            carrera = form.save()
            messages.success(
                request,
                f"Carrera {carrera.nombre_carrera} guardada.",
            )

            return _redirigir_gestion("carrera")

        return _re_render_gestion(
            request, "carrera", form, "form_carrera"
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
    )

    contexto[nombre_form] = form

    return render(
        request,
        "academico/gestion_academica.html",
        contexto,
    )


def _contexto_gestion(request, entidad_activa, plan_valor=None):
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

    materias_del_plan = []

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

        "escuelas": escuelas,
        "carreras": carreras,
        "planes": planes,
        "materias": materias,
        "grupos_optativos": grupos_optativos,

        "plan_seleccionado": plan_seleccionado,
        "materias_del_plan": materias_del_plan,
    }
