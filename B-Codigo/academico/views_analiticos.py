"""
Generación del analítico: carga de datos, previsualización,
validación y descarga del documento.

Flujo:
    1. Buscar por legajo (o cargar todo a mano).
    2. «Continuar»: valida datos personales + parsea el Lincoln
       y muestra la previsualización (editable en tiempo real).
    3. «Validar analítico»: persiste TODO en la base de datos
       (datos personales, resoluciones, exámenes y el registro
       ANALITICO) y habilita la descarga.
    4. «Descargar analítico»: genera el .docx desde la base.

Si el legajo + la carrera ya existen, se avisa y se ofrecen dos
opciones: «Generar analítico» (revisar/actualizar) o «Modificar
la información» (pantalla de edición de graduados).
"""

import json
import re
import unicodedata
from datetime import date
from io import BytesIO
from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from .autenticacion import requiere_sesion
from .models import (
    Analitico,
    Carrera,
    CarreraResolucion,
    Ciudad,
    DatosNacimiento,
    Escuela,
    Graduado,
    GraduadoCarrera,
    GraduadoExamen,
    Examen,
    Materia,
    PlanEstudiosMateria,
    Provincia,
    Resolucion,
    Secundario,
    Titulo,
    TipoDocumentoAnalitico,
    TipoResolucion,
)
from .servicios.moduloAnalitico.generador import (
    contexto_analitico,
    render_docx,
    texto_resoluciones,
    examenes_ordenados_por_anio,
)
from .servicios.moduloAnalitico.lector_lincoln import (
    ErrorLincoln,
    leer_lincoln,
    matcheo_materia,
)
from .servicios.moduloAnalitico.utilidades_texto import (
    anio_con_punto,
    dni_con_puntos,
)
from .views_gestion import _redirigir_gestion

CLAVE_SESION_PREVIEW = "analitico_preview"


# ==================================================
# AYUDAS
# ==================================================

def _folio_de(respaldo):
    """
    Folio de un respaldo: los últimos 3 dígitos (ej. RG07205070 →
    «070»). Si no hay 3 dígitos al final (ej. una resolución),
    devuelve «—».
    """

    if not respaldo:
        return ""

    match = re.search(r"\d{3}$", str(respaldo).strip())

    return match.group(0) if match else "—"


def _limpiar(valor):
    return (valor or "").strip()


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.lower().strip()


def _slug(texto):
    texto = _normalizar(texto)
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    return texto.strip("_") or "analitico"


def _anio_de(valor):
    texto = _limpiar(valor)

    if not texto:
        return None

    match = re.search(r"\d{4}", texto)

    if not match:
        return None

    return int(match.group(0))


def _obtener_o_crear_provincia(nombre):
    nombre = _limpiar(nombre)

    if not nombre:
        return None

    provincia, _ = Provincia.objects.get_or_create(
        nombre_provincia=nombre,
        defaults={"nombre_provincia": nombre},
    )

    return provincia


def _obtener_o_crear_ciudad(nombre, id_provincia):
    nombre = _limpiar(nombre)

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


def _datos_precargados(graduado, registro):
    """Valores para precargar el formulario desde la base."""

    datos = {
        "legajo": graduado.legajo_graduado if graduado else "",
        "nombre": graduado.nombre if graduado else "",
        "apellido": graduado.apellido if graduado else "",
        "dni": graduado.dni if graduado else "",
        "anio_ingreso_uarg": (
            graduado.fecha_ingreso_universidad.year
            if graduado and graduado.fecha_ingreso_universidad
            else ""
        ),
        "carrera": registro.codigo_carrera_id if registro else "",
        "anio_ingreso_carrera": (
            registro.fecha_ingreso_carrera.year
            if registro else ""
        ),
        "fecha_egreso_carrera": (
            registro.fecha_egreso_carrera.isoformat()
            if registro else ""
        ),
        "promedio_sin_aplazo": (
            registro.promedio_sin_aplazo
            if registro else ""
        ),
        "promedio_con_aplazo": (
            registro.promedio_con_aplazo
            if registro else ""
        ),
        "fecha_nacimiento": "",
        "ciudad_nacimiento": "",
        "provincia_nacimiento": "",
        "nombre_secundario": "",
        "titulo_secundario": "",
        "ciudad_secundario": "",
        "provincia_secundario": "",
        "anio_egreso_secundario": "",
        "titulo_otorgado": "",
        "resoluciones_ministeriales": "",
        "otros_instrumentos": "",
    }

    if graduado:
        nacimiento = (
            DatosNacimiento.objects
            .filter(legajo_graduado=graduado)
            .select_related("id_ciudad", "id_provincia")
            .first()
        )

        if nacimiento:
            datos["fecha_nacimiento"] = (
                nacimiento.fecha_nacimiento.isoformat()
                if nacimiento.fecha_nacimiento else ""
            )
            datos["ciudad_nacimiento"] = nacimiento.id_ciudad.nombre_ciudad
            datos["provincia_nacimiento"] = (
                nacimiento.id_provincia.nombre_provincia
            )

        secundario = (
            Secundario.objects
            .filter(legajo_graduado=graduado)
            .select_related("id_ciudad", "id_provincia")
            .first()
        )

        if secundario:
            datos["nombre_secundario"] = secundario.nombre_secundario
            datos["titulo_secundario"] = secundario.titulo_secundario
            datos["ciudad_secundario"] = secundario.id_ciudad.nombre_ciudad
            datos["provincia_secundario"] = (
                secundario.id_provincia.nombre_provincia
            )
            datos["anio_egreso_secundario"] = (
                secundario.anio_egreso_secundario or ""
            )

    if registro:
        titulo = (
            Titulo.objects
            .filter(codigo_carrera=registro.codigo_carrera)
            .first()
        )

        if titulo:
            datos["titulo_otorgado"] = titulo.nombre_titulo

        ministeriales = list(
            Resolucion.objects
            .filter(
                resolucion__in=CarreraResolucion.objects.filter(
                    codigo_carrera=registro.codigo_carrera,
                ).values("resolucion")
            )
            .filter(tipo_resolucion=TipoResolucion.MINISTERIAL_NACIONAL)
            .values_list("resolucion", flat=True)
        )

        otros = list(
            Resolucion.objects
            .filter(
                resolucion__in=CarreraResolucion.objects.filter(
                    codigo_carrera=registro.codigo_carrera,
                ).values("resolucion")
            )
            .filter(tipo_resolucion=TipoResolucion.OTRO_INSTRUMENTO)
            .values_list("resolucion", flat=True)
        )

        datos["resoluciones_ministeriales"] = "; ".join(ministeriales)
        datos["otros_instrumentos"] = "; ".join(otros)

    return datos


def _validar_datos(datos_form):
    """
    Valida los datos personales/carrera del formulario.
    Devuelve (datos, errores) con tipos seguros listos para
    persistir.
    """

    errores = []

    datos = {}
    datos["legajo"] = _limpiar(datos_form.get("legajo"))
    datos["nombre"] = _limpiar(datos_form.get("nombre"))
    datos["apellido"] = _limpiar(datos_form.get("apellido"))
    dni_digitos = re.sub(r"\D", "", _limpiar(datos_form.get("dni")))
    datos["dni"] = dni_digitos
    datos["anio_ingreso_uarg"] = _anio_de(
        datos_form.get("anio_ingreso_uarg")
    )
    datos["carrera"] = _limpiar(datos_form.get("carrera"))
    datos["anio_ingreso_carrera"] = _anio_de(
        datos_form.get("anio_ingreso_carrera")
    )

    fecha_egreso_txt = _limpiar(datos_form.get("fecha_egreso_carrera"))
    fecha_ingreso_uarg_txt = _limpiar(
        datos_form.get("fecha_ingreso_uarg_completa")
    )

    for campo in (
        "nombre",
        "apellido",
        "dni",
        "carrera",
    ):
        if not datos[campo]:
            errores.append(f"El campo «{campo}» es obligatorio.")

    if not datos["legajo"]:
        errores.append("El campo «legajo» es obligatorio.")

    for campo in ("anio_ingreso_uarg", "anio_ingreso_carrera"):
        if datos[campo] is None:
            errores.append(f"El campo «{campo}» debe contener un año.")

    try:
        fecha_egreso = (
            date.fromisoformat(fecha_egreso_txt)
            if fecha_egreso_txt else None
        )
    except ValueError:
        fecha_egreso = None

    if fecha_egreso is None:
        errores.append("El campo «fecha_egreso_carrera» no es válido.")

    datos["fecha_egreso"] = fecha_egreso

    if fecha_ingreso_uarg_txt:
        try:
            fecha_ingreso_uarg = date.fromisoformat(fecha_ingreso_uarg_txt)
        except ValueError:
            fecha_ingreso_uarg = None
    else:
        fecha_ingreso_uarg = (
            date(datos["anio_ingreso_uarg"], 3, 1)
            if datos["anio_ingreso_uarg"] else None
        )

    datos["fecha_ingreso_universidad"] = fecha_ingreso_uarg

    # Promedios.
    for campo in ("promedio_sin_aplazo", "promedio_con_aplazo"):
        texto = _limpiar(datos_form.get(campo))

        try:
            valor = float(texto.replace(",", "."))
        except ValueError:
            valor = None

        if valor is None or not (0 <= valor <= 10):
            errores.append(
                f"El campo «{campo}» debe ser un número entre 0 y 10."
            )

        datos[campo] = valor

    # Nacimiento.
    fecha_nac_txt = _limpiar(datos_form.get("fecha_nacimiento"))

    try:
        datos["fecha_nacimiento"] = (
            date.fromisoformat(fecha_nac_txt) if fecha_nac_txt else None
        )
    except ValueError:
        datos["fecha_nacimiento"] = None
        errores.append("La fecha de nacimiento no es válida.")

    datos["ciudad_nacimiento"] = _limpiar(
        datos_form.get("ciudad_nacimiento")
    )
    datos["provincia_nacimiento"] = _limpiar(
        datos_form.get("provincia_nacimiento")
    )

    # Secundario.
    datos["nombre_secundario"] = _limpiar(
        datos_form.get("nombre_secundario")
    )
    datos["titulo_secundario"] = _limpiar(
        datos_form.get("titulo_secundario")
    )
    datos["ciudad_secundario"] = _limpiar(
        datos_form.get("ciudad_secundario")
    )
    datos["provincia_secundario"] = _limpiar(
        datos_form.get("provincia_secundario")
    )
    datos["anio_egreso_secundario"] = _anio_de(
        datos_form.get("anio_egreso_secundario")
    )

    datos["titulo_otorgado"] = _limpiar(
        datos_form.get("titulo_otorgado")
    )

    datos["resoluciones_institucionales"] = [
        r.strip()
        for r in re.split(
            r"[;,]",
            _limpiar(datos_form.get("resoluciones_institucionales")),
        )
        if r.strip()
    ]
    datos["resoluciones_ministeriales"] = _limpiar(
        datos_form.get("resoluciones_ministeriales")
    )
    datos["otros_instrumentos"] = _limpiar(
        datos_form.get("otros_instrumentos")
    )

    for campo in (
        "ciudad_nacimiento",
        "provincia_nacimiento",
        "nombre_secundario",
        "ciudad_secundario",
        "provincia_secundario",
        "titulo_secundario",
    ):
        if not datos[campo]:
            errores.append(f"El campo «{campo}» es obligatorio.")

    return datos, errores


def _materias_plan(carrera):
    """Materias del plan de la carrera (para el selector)."""

    ids = (
        PlanEstudiosMateria.objects
        .filter(codigo_plan__codigo_carrera=carrera)
        .values_list("codigo_materia_id", flat=True)
    )

    return list(
        Materia.objects
        .filter(codigo_materia__in=ids)
        .order_by("nombre_materia")
    )


def _guardar_resoluciones(carrera, datos):
    """Sincroniza CARRERA_RESOLUCION con la selección del form."""

    seleccionadas = set(datos["resoluciones_institucionales"])

    # Alta de las resoluciones tipeadas que no existen aún.
    for codigo in seleccionadas:
        Resolucion.objects.get_or_create(
            resolucion=codigo,
            defaults={
                "tipo_resolucion": TipoResolucion.INSTITUCIONAL,
            },
        )

    texto_ministeriales = datos["resoluciones_ministeriales"]
    ministeriales = [
        r.strip()
        for r in re.split(r"[;,]", texto_ministeriales)
        if r.strip()
    ]

    texto_otros = datos["otros_instrumentos"]
    otros = [
        r.strip()
        for r in re.split(r"[;,]", texto_otros)
        if r.strip()
    ]

    for codigo in ministeriales:
        Resolucion.objects.get_or_create(
            resolucion=codigo,
            defaults={
                "tipo_resolucion": TipoResolucion.MINISTERIAL_NACIONAL,
            },
        )

    for codigo in otros:
        Resolucion.objects.get_or_create(
            resolucion=codigo,
            defaults={
                "tipo_resolucion": TipoResolucion.OTRO_INSTRUMENTO,
            },
        )

    seleccionadas.update(ministeriales)
    seleccionadas.update(otros)

    actuales = set(
        CarreraResolucion.objects.filter(
            codigo_carrera=carrera
        ).values_list("resolucion", flat=True)
    )

    for resolucion in seleccionadas - actuales:
        CarreraResolucion.objects.create(
            codigo_carrera=carrera,
            resolucion_id=resolucion,
        )

    CarreraResolucion.objects.filter(
        codigo_carrera=carrera,
        resolucion__in=actuales - seleccionadas,
    ).delete()


# ==================================================
# VISTAS
# ==================================================

def _url_analitico(tipo_documento):
    if tipo_documento == TipoDocumentoAnalitico.EN_TRAMITE:
        return reverse("titulo_en_tramite")

    return reverse("generacion_analiticos")


def _sel_desde(request):
    graduado = Graduado.objects.filter(
        legajo_graduado=_limpiar(request.GET.get("legajo")),
    ).first()

    registro = (
        GraduadoCarrera.objects
        .filter(
            legajo_graduado=graduado,
            codigo_carrera=_limpiar(request.GET.get("carrera")),
        )
        .first()
        if graduado else None
    )

    return graduado, registro


def _preview_con_session(request, tipo_documento):
    datos_session = request.session.get(CLAVE_SESION_PREVIEW)

    if (
        datos_session
        and datos_session.get("tipo_documento") == tipo_documento.value
    ):
        filas, materias = _filas_para_mostrar(datos_session)

        return render(
            request,
            "academico/generacion_analiticos.html",
            _contexto_preview(
                request,
                tipo_documento,
                datos_session["datos"],
                filas,
                materias,
                validado=False,
                modo_db=False,
            ),
        )

    return None


def _preview_con_bd(request, tipo_documento, graduado, registro,
                    validado):
    contexto = contexto_analitico(
        graduado,
        registro.codigo_carrera,
        tipo_documento,
    )

    filas = [
        {**fila, "matcheada": True}
        for fila in contexto["filas"]
    ]

    materias = _materias_plan(registro.codigo_carrera)
    datos = _datos_precargados(graduado, registro)

    return render(
        request,
        "academico/generacion_analiticos.html",
        _contexto_preview(
            request,
            tipo_documento,
            datos,
            filas,
            materias,
            validado=validado,
            modo_db=True,
        ),
    )


@requiere_sesion
def generacion_analiticos(request):
    """Generar analítico: carga desde cero (sin buscador)."""
    url = reverse("generacion_analiticos")
    tipo_documento = TipoDocumentoAnalitico.TITULO

    legajo_sel = _limpiar(request.GET.get("legajo"))
    carrera_sel = _limpiar(request.GET.get("carrera"))

    if request.method == "POST":
        accion = request.POST.get("accion", "")

        if accion == "continuar":
            return _continuar(request, tipo_documento)

        if accion == "validar":
            return _validar(request, tipo_documento)

        if accion == "descargar":
            return _descargar(request, tipo_documento)

        return redirect(url)

    modo = request.GET.get("modo", "carga")

    graduado, registro = _sel_desde(request)

    if modo == "preview":
        analitico_existe = (
            Analitico.objects
            .filter(
                legajo_graduado=graduado,
                codigo_carrera=(
                    registro.codigo_carrera if registro else None
                ),
                tipo_documento=tipo_documento,
            )
            .exists()
            if registro else False
        )

        if not analitico_existe:
            preview = _preview_con_session(request, tipo_documento)

            if preview is not None:
                return preview

            if graduado is not None and registro is not None:
                return _preview_con_bd(
                    request,
                    tipo_documento,
                    graduado,
                    registro,
                    validado=False,
                )

            messages.error(
                request,
                "Primero cargá los datos y presioná «Continuar».",
            )

            return redirect(url)

        return _preview_con_bd(
            request,
            tipo_documento,
            graduado,
            registro,
            validado=True,
        )

    # GET: aviso de que el graduado ya existe.
    if modo == "elegir" and graduado is not None and registro is not None:
        return render(
            request,
            "academico/generacion_analiticos.html",
            {
                "tipo_documento": tipo_documento,
                "vista": "elegir",
                "graduado": graduado,
                "registro": registro,
                "legajo": legajo_sel,
                "carrera": carrera_sel,
                "analitico_previo": Analitico.objects.filter(
                    legajo_graduado=graduado,
                    codigo_carrera=registro.codigo_carrera,
                    tipo_documento=tipo_documento,
                ).exists(),
            },
        )

    # GET: formulario de carga (nunca buscador).
    if graduado is not None and registro is not None:
        datos = _datos_precargados(graduado, registro)
    else:
        datos = {
            "legajo": legajo_sel,
            "carrera": carrera_sel,
            "nombre": "",
            "apellido": "",
            "dni": "",
            "anio_ingreso_uarg": "",
            "anio_ingreso_carrera": "",
            "fecha_egreso_carrera": "",
            "promedio_sin_aplazo": "",
            "promedio_con_aplazo": "",
            "fecha_nacimiento": "",
            "ciudad_nacimiento": "",
            "provincia_nacimiento": "",
            "nombre_secundario": "",
            "titulo_secundario": "",
            "ciudad_secundario": "",
            "provincia_secundario": "",
            "anio_egreso_secundario": "",
            "titulo_otorgado": "",
            "resoluciones_ministeriales": "",
            "otros_instrumentos": "",
            "resoluciones_institucionales": [],
        }

    return render(
        request,
        "academico/generacion_analiticos.html",
        {
            **_contexto_formulario(request, tipo_documento, datos),
            "vista": "carga",
        },
    )


@requiere_sesion
def titulo_en_tramite(request):
    """Título en trámite: sólo buscar y generar el documento."""
    url = reverse("titulo_en_tramite")
    tipo_documento = TipoDocumentoAnalitico.EN_TRAMITE

    if request.method == "POST":
        accion = request.POST.get("accion", "")

        if accion == "buscar":
            legajo = _limpiar(request.POST.get("legajo"))
            carrera = _limpiar(request.POST.get("carrera"))

            if not legajo or not carrera:
                messages.error(
                    request,
                    "Ingresá legajo y carrera para buscar.",
                )

                return redirect(url)

            destino = f"{url}?" + urlencode({
                "modo": "preview",
                "legajo": legajo,
                "carrera": carrera,
            })

            graduado = Graduado.objects.filter(
                legajo_graduado=legajo,
            ).first()

            registro = (
                GraduadoCarrera.objects
                .filter(
                    legajo_graduado=graduado,
                    codigo_carrera_id=carrera,
                )
                .first()
                if graduado else None
            )

            if graduado is None or registro is None:
                messages.error(
                    request,
                    "No hay un graduado con ese legajo en esa carrera. "
                    "Cargá los datos desde «Generar analítico».",
                )

                return redirect(url)

            return redirect(destino)

        if accion == "validar":
            return _validar(request, tipo_documento)

        if accion == "descargar":
            return _descargar(request, tipo_documento)

        return redirect(url)

    modo = request.GET.get("modo", "buscar")

    graduado, registro = _sel_desde(request)

    if modo == "preview":
        analitico_existe = (
            Analitico.objects
            .filter(
                legajo_graduado=graduado,
                codigo_carrera=(
                    registro.codigo_carrera if registro else None
                ),
                tipo_documento=tipo_documento,
            )
            .exists()
            if registro else False
        )

        if graduado is None or registro is None:
            messages.error(
                request,
                "No hay un graduado con ese legajo en esa carrera.",
            )

            return redirect(url)

        return _preview_con_bd(
            request,
            tipo_documento,
            graduado,
            registro,
            validado=analitico_existe,
        )

    carreras = Carrera.objects.order_by("nombre_carrera")

    return render(
        request,
        "academico/titulo_en_tramite.html",
        {
            "tipo_documento": tipo_documento,
            "carreras": carreras,
        },
    )


def _armar_filas(examenes, carrera):
    """Arma las filas (y la lista de materias del plan)."""

    materias_plan = _materias_plan(carrera)

    filas = []

    for indice, examen in enumerate(examenes, start=1):
        materia = examen.get("materia")

        if materia is None and examen.get("materia_codigo"):
            materia = next(
                (
                    m for m in materias_plan
                    if m.codigo_materia == examen["materia_codigo"]
                ),
                None,
            )

        filas.append({
            "indice": indice,
            "orden": f"{indice:02d}",
            "anio": (
                examen.get("anio") or examen.get("anio_cursado") or ""
            ),
            "espacio": (
                materia.nombre_materia
                if materia else examen.get("nombre_materia", "")
            ),
            "nota": examen.get("nota"),
            "nota_txt": examen.get("nota_txt", ""),
            "nota_original": examen.get("nota"),
            "fecha_examen": examen.get("fecha_examen", ""),
            "tipo": examen.get("tipo", "Examen"),
            "respaldo": examen.get("acta_respaldatoria", ""),
            "folio": _folio_de(examen.get("acta_respaldatoria", "")),
            "materia_codigo": (
                materia.codigo_materia if materia else ""
            ),
            "matcheada": bool(materia),
        })

    return filas, materias_plan


def _filas_para_mostrar(datos_session):
    filas, materias = _armar_filas(
        datos_session["examenes"],
        Carrera.objects.get(
            codigo_carrera=datos_session["carrera"],
        ),
    )

    return filas, materias


def _contexto_formulario(request, tipo_documento, datos, advertencias=None):
    carreras = Carrera.objects.select_related("id_escuela").order_by(
        "nombre_carrera"
    )

    titulos = Titulo.objects.select_related("codigo_carrera").order_by(
        "nombre_titulo"
    )

    provincias = Provincia.objects.order_by("nombre_provincia")
    ciudades = Ciudad.objects.order_by("nombre_ciudad")

    return {
        "tipo_documento": tipo_documento,
        "datos": datos,
        "advertencias": advertencias or [],
        "carreras": carreras,
        "titulos": titulos,
        "provincias": [p.nombre_provincia for p in provincias],
        "ciudades": [c.nombre_ciudad for c in ciudades],
    }


def _contexto_preview(request, tipo_documento, datos, filas, materias,
                      validado, modo_db):
    titulos = Titulo.objects.select_related("codigo_carrera").order_by(
        "nombre_titulo"
    )

    return {
        "tipo_documento": tipo_documento,
        "vista": "preview",
        "datos": datos,
        "filas": filas,
        "materias_plan": materias,
        "validado": validado,
        "modo_db": modo_db,
        "titulos": titulos,
        "provincias": [
            p.nombre_provincia
            for p in Provincia.objects.order_by("nombre_provincia")
        ],
        "ciudades": [
            c.nombre_ciudad
            for c in Ciudad.objects.order_by("nombre_ciudad")
        ],
    }


def _continuar(request, tipo_documento):
    url = _url_analitico(tipo_documento)

    datos, errores = _validar_datos(request.POST)

    if errores:
        for error in errores:
            messages.error(request, error)

        return render(
            request,
            "academico/generacion_analiticos.html",
            {
                **_contexto_formulario(request, tipo_documento, datos),
                "vista": "carga",
            },
        )

    carrera = Carrera.objects.filter(codigo_carrera=datos["carrera"]).first()

    if carrera is None:
        messages.error(request, "La carrera elegida no existe.")

        return render(
            request,
            "academico/generacion_analiticos.html",
            {
                **_contexto_formulario(request, tipo_documento, datos),
                "vista": "carga",
            },
        )

    materias = _materias_plan(carrera)

    # --- Exámenes: del Lincoln subido o de la base.
    examenes = []

    lincoln_file = request.FILES.get("archivo_notas")

    if lincoln_file:
        try:
            lincoln = leer_lincoln(lincoln_file)
        except ErrorLincoln as error:
            messages.error(request, str(error))

            return render(
                request,
                "academico/generacion_analiticos.html",
                {
                    **_contexto_formulario(request, tipo_documento, datos),
                    "vista": "carga",
                },
            )

        for examen in lincoln["examenes"]:
            materia = matcheo_materia(examen, materias)

            examenes.append({
                "nombre_materia": examen["nombre_materia"],
                "fecha_examen": (
                    examen["fecha_examen"].isoformat()
                    if examen["fecha_examen"] else ""
                ),
                "nota": examen["nota"],
                "tipo": examen["tipo"],
                "acta_respaldatoria": examen["acta_respaldatoria"],
                "anio_cursado": examen["anio_cursado"],
                "materia": materia,
                "materia_codigo": (
                    materia.codigo_materia if materia else ""
                ),
            })

        if lincoln["descartados"]:
            messages.warning(
                request,
                "Registros descartados del Lincoln: "
                + ", ".join(lincoln["descartados"])
                + ".",
            )

    else:
        graduado_db = Graduado.objects.filter(
            legajo_graduado=datos["legajo"]
        ).first()

        if graduado_db:
            materias_por_codigo = {
                m.codigo_materia: m for m in materias
            }

            for fila in examenes_ordenados_por_anio(graduado_db, carrera):
                materia = materias_por_codigo.get(fila["materia_codigo"])

                examenes.append({
                    "nombre_materia": fila["espacio"],
                    "fecha_examen": fila["fecha_examen"],
                    "nota": fila["nota"],
                    "tipo": fila["tipo"],
                    "acta_respaldatoria": fila["respaldo"],
                    "anio_cursado": None,
                    "materia": materia,
                    "materia_codigo": (
                        materia.codigo_materia if materia else ""
                    ),
                })

    if not examenes:
        messages.error(
            request,
            "No hay exámenes para generar el analítico. "
            "Adjuntá el Certificado Lincoln.",
        )

        return render(
            request,
            "academico/generacion_analiticos.html",
            {
                **_contexto_formulario(request, tipo_documento, datos),
                "vista": "carga",
            },
        )

    request.session[CLAVE_SESION_PREVIEW] = {
        "tipo_documento": tipo_documento.value,
        "legajo": datos["legajo"],
        "carrera": datos["carrera"],
        "datos": {
            **datos,
            "fecha_egreso": datos["fecha_egreso"].isoformat(),
            "fecha_nacimiento": (
                datos["fecha_nacimiento"].isoformat()
                if datos["fecha_nacimiento"] else ""
            ),
            "fecha_ingreso_universidad": (
                datos["fecha_ingreso_universidad"].isoformat()
                if datos["fecha_ingreso_universidad"] else ""
            ),
        },
        "examenes": [
            {
                "nombre_materia": examen["nombre_materia"],
                "fecha_examen": examen["fecha_examen"],
                "nota": examen["nota"],
                "tipo": examen["tipo"],
                "acta_respaldatoria": examen["acta_respaldatoria"],
                "anio_cursado": examen.get("anio_cursado"),
                "materia_codigo": examen.get("materia_codigo") or "",
            }
            for examen in examenes
        ],
    }
    request.session.modified = True

    destino = (
        f"{url}?{urlencode({'modo': 'preview', 'legajo': datos['legajo'], 'carrera': datos['carrera']})}"
    )

    # Si el graduado ya está guardado en el sistema, preguntar
    # antes de tocar nada.
    graduado = Graduado.objects.filter(
        legajo_graduado=datos["legajo"]
    ).first()

    registro = (
        GraduadoCarrera.objects
        .filter(
            legajo_graduado=graduado,
            codigo_carrera_id=datos["carrera"],
        )
        .first()
        if graduado else None
    )

    if graduado is not None and registro is not None:
        return render(
            request,
            "academico/generacion_analiticos.html",
            {
                "tipo_documento": tipo_documento,
                "vista": "elegir",
                "graduado": graduado,
                "registro": registro,
                "legajo": datos["legajo"],
                "carrera": datos["carrera"],
                "analitico_previo": Analitico.objects.filter(
                    legajo_graduado=graduado,
                    codigo_carrera_id=datos["carrera"],
                    tipo_documento=tipo_documento,
                ).exists(),
            },
        )


    return redirect(destino)


def _filas_desde_post(request):
    indices = request.POST.getlist("fila_indice")
    espacios = request.POST.getlist("fila_espacio")
    notas = request.POST.getlist("fila_nota")
    fechas = request.POST.getlist("fila_fecha")
    tipos = request.POST.getlist("fila_tipo")
    actas = request.POST.getlist("fila_respaldo")
    anios = request.POST.getlist("fila_anio")
    codigos = request.POST.getlist("fila_materia")

    filas = []

    for i in range(len(indices)):
        nota_txt = notas[i].strip()

        try:
            nota = int(nota_txt)
        except ValueError:
            nota = None

        filas.append({
            "orden": indices[i],
            "espacio": espacios[i].strip(),
            "nota": nota,
            "nota_txt": nota_txt,
            "fecha_examen": fechas[i].strip(),
            "tipo": tipos[i].strip() or "Examen",
            "acta_respaldatoria": actas[i].strip(),
            "anio": anios[i].strip(),
            "materia_codigo": codigos[i].strip(),
        })

    return filas


def _validar(request, tipo_documento):
    url = _url_analitico(tipo_documento)

    datos, errores = _validar_datos(request.POST)

    filas = _filas_desde_post(request)

    errores = list(errores)

    # El analítico se genera con los espacios en blanco
    # que falten: no se exige acta ni nota por fila.
    carrera_obj = Carrera.objects.filter(
        codigo_carrera=datos["carrera"]
    ).first()

    materias_plan = (
        _materias_plan(carrera_obj)
        if carrera_obj is not None
        else []
    )

    por_codigo = {m.codigo_materia: m for m in materias_plan}

    sin_match = []

    for i, fila in enumerate(filas):
        if fila["materia_codigo"] not in por_codigo:
            # Intentar re-matcheo por nombre contra el plan.
            nombre = _normalizar(fila["espacio"])
            match = next(
                (
                    m for m in materias_plan
                    if _normalizar(m.nombre_materia) == nombre
                ),
                None,
            )

            if match is not None:
                fila["materia_codigo"] = match.codigo_materia
            else:
                sin_match.append(f"«{fila['espacio']}»")

    if errores or sin_match:
        for error in errores:
            messages.error(request, error)

        if sin_match:
            messages.error(
                request,
                "Asigná una materia del plan a: "
                + ", ".join(sin_match)
                + ".",
            )

        carrera_obj = Carrera.objects.filter(
            codigo_carrera=datos["carrera"]
        ).first()

        for fila in filas:
            materia = por_codigo.get(fila["materia_codigo"])
            fila["matcheada"] = bool(materia)

        contexto = _contexto_preview(
            request,
            tipo_documento,
            datos,
            filas,
            materias_plan,
            validado=False,
            modo_db=False,
        )
        contexto["errores_revalidar"] = True

        return render(
            request,
            "academico/generacion_analiticos.html",
            contexto,
        )

    carrera = Carrera.objects.get(codigo_carrera=datos["carrera"])

    with transaction.atomic():
        fecha_egreso = datos["fecha_egreso"]

        graduado, _ = Graduado.objects.update_or_create(
            legajo_graduado=datos["legajo"],
            defaults={
                "dni": datos["dni"],
                "nombre": datos["nombre"],
                "apellido": datos["apellido"],
                "fecha_ingreso_universidad": (
                    datos["fecha_ingreso_universidad"]
                    or date(datos["anio_ingreso_uarg"], 3, 1)
                ),
            },
        )

        registro, _ = GraduadoCarrera.objects.update_or_create(
            legajo_graduado=graduado,
            codigo_carrera=carrera,
            defaults={
                "fecha_ingreso_carrera": date(
                    datos["anio_ingreso_carrera"],
                    3,
                    1,
                ),
                "fecha_egreso_carrera": fecha_egreso,
                "promedio_sin_aplazo": datos["promedio_sin_aplazo"],
                "promedio_con_aplazo": datos["promedio_con_aplazo"],
            },
        )

        provincia_nac = _obtener_o_crear_provincia(
            datos["provincia_nacimiento"]
        )
        ciudad_nac = _obtener_o_crear_ciudad(
            datos["ciudad_nacimiento"],
            provincia_nac,
        )
        provincia_sec = _obtener_o_crear_provincia(
            datos["provincia_secundario"]
        )
        ciudad_sec = _obtener_o_crear_ciudad(
            datos["ciudad_secundario"],
            provincia_sec,
        )

        DatosNacimiento.objects.update_or_create(
            legajo_graduado=graduado,
            defaults={
                "fecha_nacimiento": datos["fecha_nacimiento"],
                "id_provincia": provincia_nac,
                "id_ciudad": ciudad_nac,
            },
        )

        secundario, _ = Secundario.objects.get_or_create(
            nombre_secundario=datos["nombre_secundario"],
            defaults={
                "legajo_graduado": graduado,
                "id_provincia": provincia_sec,
                "id_ciudad": ciudad_sec,
                "titulo_secundario": datos["titulo_secundario"],
                "anio_egreso_secundario": (
                    datos["anio_egreso_secundario"]
                ),
            },
        )

        secundario.legajo_graduado = graduado
        secundario.id_provincia = provincia_sec
        secundario.id_ciudad = ciudad_sec
        secundario.titulo_secundario = datos["titulo_secundario"]
        secundario.anio_egreso_secundario = (
            datos["anio_egreso_secundario"]
        )
        secundario.save()

        titulo_otorgado = datos["titulo_otorgado"]

        if titulo_otorgado:
            Titulo.objects.get_or_create(
                nombre_titulo=titulo_otorgado,
                defaults={"codigo_carrera": carrera},
            )

        _guardar_resoluciones(carrera, datos)

        # --- Exámenes: reemplazar los del graduado.
        GraduadoExamen.objects.filter(
            legajo_graduado=graduado,
        ).delete()

        for fila in filas:
            materia = por_codigo[fila["materia_codigo"]]

            fecha = (
                date.fromisoformat(fila["fecha_examen"])
                if fila["fecha_examen"] else None
            )

            # Examen: una acta puede respaldar varias materias,
            # por eso la unicidad es (acta, materia).
            acta = fila["acta_respaldatoria"]
            examen_defaults = {
                "tipo_examen": fila["tipo"],
                "fecha_examen": fecha,
            }

            if acta:
                examen, _ = Examen.objects.update_or_create(
                    acta_respaldatoria=acta,
                    codigo_materia=materia,
                    defaults=examen_defaults,
                )

            else:
                examen = Examen.objects.create(
                    acta_respaldatoria=acta,
                    codigo_materia=materia,
                    **examen_defaults,
                )

            resultado = (
                "Aprobado"
                if fila["nota"] is None or fila["nota"] >= 6
                else "Reprobado"
            )

            GraduadoExamen.objects.create(
                id_examen=examen,
                legajo_graduado=graduado,
                nota=fila["nota"],
                resultado=resultado,
            )

        usuario = getattr(request, "usuario_actual", None)

        Analitico.objects.update_or_create(
            legajo_graduado=graduado,
            codigo_carrera=carrera,
            tipo_documento=tipo_documento,
            defaults={
                "anio_ingreso_uarg": datos["anio_ingreso_uarg"],
                "id_usuario": (
                    usuario if usuario and getattr(
                        usuario, "id_usuario", None,
                    ) else None
                ),
            },
        )

    datos_session = request.session.get(CLAVE_SESION_PREVIEW)

    if datos_session:
        datos_session["validado"] = True
        request.session[CLAVE_SESION_PREVIEW] = datos_session
        request.session.modified = True

    messages.success(request, "Analítico validado y guardado.")

    destino = (
        f"{url}?{urlencode({'modo': 'preview', 'legajo': datos['legajo'], 'carrera': datos['carrera']})}"
    )

    return redirect(destino)


def _descargar(request, tipo_documento):
    from django.shortcuts import get_object_or_404

    legajo = _limpiar(request.POST.get("legajo"))
    carrera_codigo = _limpiar(request.POST.get("carrera"))

    graduado = get_object_or_404(Graduado, legajo_graduado=legajo)
    carrera = get_object_or_404(Carrera, codigo_carrera=carrera_codigo)

    if not Analitico.objects.filter(
        legajo_graduado=graduado,
        codigo_carrera=carrera,
        tipo_documento=tipo_documento,
    ).exists():
        messages.error(
            request,
            "El analítico todavía no fue validado.",
        )

        return redirect(
            f"{_url_analitico(tipo_documento)}?"
            + urlencode({
                "modo": "preview",
                "legajo": legajo,
                "carrera": carrera_codigo,
            })
        )

    contexto = contexto_analitico(graduado, carrera, tipo_documento)

    contenido = render_docx(contexto)

    nombre = (
        f"Analitico_{_slug(graduado.apellido)}_"
        f"{_slug(graduado.nombre)}_{graduado.legajo_graduado}.docx"
    )

    respuesta = HttpResponse(
        contenido,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    )
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'

    return respuesta
