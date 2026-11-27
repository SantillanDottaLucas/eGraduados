"""
Generación del analítico: carga de datos, previsualización,
validación y descarga del documento.

Flujo:
    1. Buscar por DNI (o cargar todo a mano).
    2. «Continuar»: valida datos personales + parsea el Lincoln
       y muestra la previsualización (editable en tiempo real).
    3. «Validar analítico»: persiste TODO en la base de datos
       (datos personales, resoluciones, exámenes y el registro
       ANALITICO) y habilita la descarga.
    4. «Descargar analítico»: genera el .docx desde la base.

Si el DNI + la carrera ya existen, se avisa y se ofrecen dos
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
    OrigenPromedio,
    Provincia,
    Resolucion,
    Secundario,
    Titulo,
    TipoDocumentoAnalitico,
    TipoResolucion,
)
from .servicios.archivos import validar_archivo
from .servicios.auditoria import registrar_auditoria
from .servicios.provincias import provincias_sugeridas
from .servicios.validaciones import validar_datos_graduado
from .servicios.moduloAnalitico.generador import (
    contexto_analitico,
    render_docx,
    texto_resoluciones,
    examenes_ordenados,
)
from .servicios.moduloAnalitico.lector_lincoln import (
    ErrorLincoln,
    leer_lincoln,
    matcheo_materia,
)
from .servicios.moduloAnalitico.plan_estudios import (
    aplicar_plan_a_filas,
    verificar_filas,
)
from .servicios.moduloAnalitico.promedios import (
    calcular_promedios,
    mismo_promedio,
    promedios_desde_filas,
)
from .servicios.moduloAnalitico.utilidades_texto import (
    anio_con_punto,
    dni_con_puntos,
    tipo_examen_legible,
)
from .views_gestion import _redirigir_gestion

CLAVE_SESION_PREVIEW = "analitico_preview"
CLAVE_SESION_BORRADOR = "analitico_borrador"
CLAVE_PROMEDIOS_CALCULADOS = "promedios_calculados"

# Campos del formulario que se guardan en el borrador. El Excel queda
# afuera: los navegadores no permiten rellenar un <input type="file">.
CAMPOS_BORRADOR = (
    "nombre",
    "apellido",
    "dni",
    "anio_ingreso_uarg",
    "carrera",
    "anio_ingreso_carrera",
    "fecha_egreso_carrera",
    "promedio_sin_aplazo",
    "promedio_con_aplazo",
    "fecha_nacimiento",
    "ciudad_nacimiento",
    "provincia_nacimiento",
    "nombre_secundario",
    "titulo_secundario",
    "ciudad_secundario",
    "provincia_secundario",
    "anio_egreso_secundario",
    "titulo_otorgado",
    "resoluciones_institucionales",
    "resoluciones_ministeriales",
    "otros_instrumentos",
)

CAMPOS_REPETIBLES_BORRADOR = (
    "resoluciones_institucionales",
    "resoluciones_ministeriales",
    "otros_instrumentos",
)


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


def _lista_resoluciones(datos_form, campo):
    """
    Devuelve una lista limpia de resoluciones de un campo.

    Acepta campos repetibles (``getlist``), listas y el formato
    histórico de un solo input con valores separados por coma o
    punto y coma.
    """

    if hasattr(datos_form, "getlist"):
        valores = list(datos_form.getlist(campo))
    else:
        valor = datos_form.get(campo)
        valores = list(valor) if isinstance(valor, (list, tuple)) else [valor]

    resultado = []

    for valor in valores:
        for parte in re.split(r"[;,]", _limpiar(valor)):
            texto = parte.strip()

            if texto and texto not in resultado:
                resultado.append(texto)

    return resultado


def _guardar_borrador(request, tipo_documento):
    """
    Guarda en sesión lo que la persona escribió en el formulario.

    Se usa cuando el envío no llega a destino (validación, POST sin
    acción, archivo inválido, etc.). Los valores se toman del POST
    crudo para que la sesión siga siendo serializable y para no
    perder lo que el usuario efectivamente tecleó.

    Devuelve ``True`` si guardó algo; un POST de la previsualización
    (que no trae estos campos) no debe pisar un borrador existente.
    """

    if not any(campo in request.POST for campo in (
        "nombre",
        "apellido",
        "dni",
    )):
        return False

    datos = {}

    for campo in CAMPOS_BORRADOR:
        if campo in CAMPOS_REPETIBLES_BORRADOR:
            datos[campo] = [
                valor for valor in request.POST.getlist(campo)
                if _limpiar(valor)
            ]
        else:
            datos[campo] = _limpiar(request.POST.get(campo))

    usuario = getattr(request, "usuario_actual", None)

    request.session[CLAVE_SESION_BORRADOR] = {
        "usuario_id": getattr(usuario, "id_usuario", None),
        "tipo_documento": tipo_documento.value,
        "dni": datos["dni"],
        "carrera": datos["carrera"],
        "datos": datos,
    }

    return True


def _recuperar_borrador(request, tipo_documento, dni=None, carrera=None):
    """
    Devuelve el borrador de esta persona y trámite, o ``None``.

    Los filtros opcionales de dni/carrera evitan que un borrador
    anterior se mezcle cuando se abre un graduado distinto.
    """

    borrador = request.session.get(CLAVE_SESION_BORRADOR)

    if not borrador:
        return None

    usuario = getattr(request, "usuario_actual", None)

    if (
        borrador.get("tipo_documento") != tipo_documento.value
        or borrador.get("usuario_id") != getattr(
            usuario, "id_usuario", None
        )
    ):
        return None

    if dni is not None and borrador.get("dni") != dni:
        return None

    if carrera is not None and borrador.get("carrera") != carrera:
        return None

    datos = dict(borrador.get("datos") or {})

    for campo in CAMPOS_REPETIBLES_BORRADOR:
        datos[campo] = datos.get(campo) or []

    return datos


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
        id_provincia=id_provincia,
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
        "nombre": graduado.nombre if graduado else "",
        "apellido": graduado.apellido if graduado else "",
        "dni": graduado.dni if graduado else "",
        "legajo": graduado.legajo if graduado else "",
        "anio_ingreso_uarg": (
            graduado.anio_ingreso_universidad
            if graduado and graduado.anio_ingreso_universidad
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
        "resoluciones_ministeriales": [],
        "otros_instrumentos": [],
        "resoluciones_institucionales": [],
    }

    if graduado:
        nacimiento = (
            DatosNacimiento.objects
            .filter(dni_graduado=graduado)
            .select_related("id_ciudad", "id_provincia")
            .first()
        )

        if nacimiento:
            datos["fecha_nacimiento"] = (
                nacimiento.fecha_nacimiento.isoformat()
                if nacimiento.fecha_nacimiento else ""
            )
            datos["ciudad_nacimiento"] = (
                nacimiento.id_ciudad.nombre_ciudad
                if nacimiento.id_ciudad else ""
            )
            datos["provincia_nacimiento"] = (
                nacimiento.id_provincia.nombre_provincia
                if nacimiento.id_provincia else ""
            )

        secundario = (
            Secundario.objects
            .filter(dni_graduado=graduado)
            .select_related("id_ciudad", "id_provincia")
            .first()
        )

        if secundario:
            datos["nombre_secundario"] = secundario.nombre_secundario
            datos["titulo_secundario"] = secundario.titulo_secundario
            datos["ciudad_secundario"] = (
                secundario.id_ciudad.nombre_ciudad
                if secundario.id_ciudad else ""
            )
            datos["provincia_secundario"] = (
                secundario.id_provincia.nombre_provincia
                if secundario.id_provincia else ""
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

        institucionales = list(
            Resolucion.objects
            .filter(
                resolucion__in=CarreraResolucion.objects.filter(
                    codigo_carrera=registro.codigo_carrera,
                ).values("resolucion")
            )
            .filter(tipo_resolucion=TipoResolucion.INSTITUCIONAL)
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

        datos["resoluciones_ministeriales"] = ministeriales
        datos["otros_instrumentos"] = otros
        datos["resoluciones_institucionales"] = institucionales

    return datos


def _validar_datos(datos_form):
    """
    Valida los datos personales/carrera del formulario.
    Devuelve (datos, errores) con tipos seguros listos para
    persistir.
    """

    errores = []

    datos = {}
    datos["dni"] = _limpiar(datos_form.get("dni"))
    datos["nombre"] = _limpiar(datos_form.get("nombre"))
    datos["apellido"] = _limpiar(datos_form.get("apellido"))
    datos["legajo"] = None
    datos["anio_ingreso_uarg"] = _anio_de(
        datos_form.get("anio_ingreso_uarg")
    )
    datos["carrera"] = _limpiar(datos_form.get("carrera"))
    datos["anio_ingreso_carrera"] = _anio_de(
        datos_form.get("anio_ingreso_carrera")
    )

    fecha_egreso_txt = _limpiar(datos_form.get("fecha_egreso_carrera"))

    for campo in (
        "nombre",
        "apellido",
        "carrera",
    ):
        if not datos[campo]:
            errores.append(f"El campo «{campo}» es obligatorio.")

    if not datos["dni"]:
        errores.append("El campo «DNI» es obligatorio.")

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
    datos["fecha_egreso_carrera"] = (
        fecha_egreso.isoformat() if fecha_egreso else ""
    )

    # Promedios: se validan sólo si vienen informados. En la
    # previsualización se completan con el cálculo de exámenes.
    for campo in ("promedio_sin_aplazo", "promedio_con_aplazo"):
        texto = _limpiar(datos_form.get(campo))

        if not texto:
            datos[campo] = None
            continue

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

    datos["resoluciones_institucionales"] = _lista_resoluciones(
        datos_form, "resoluciones_institucionales"
    )
    datos["resoluciones_ministeriales"] = _lista_resoluciones(
        datos_form, "resoluciones_ministeriales"
    )
    datos["otros_instrumentos"] = _lista_resoluciones(
        datos_form, "otros_instrumentos"
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

    # Reglas de negocio compartidas con la edición y la carga Excel.
    normalizados, errores_negocio = validar_datos_graduado(
        {
            "dni": datos["dni"],
            "anio_ingreso_universidad": datos["anio_ingreso_uarg"],
            "anio_ingreso_carrera": datos["anio_ingreso_carrera"],
            "fecha_nacimiento": datos.get("fecha_nacimiento"),
            "fecha_ingreso_carrera": (
                date(datos["anio_ingreso_carrera"], 3, 1)
                if datos["anio_ingreso_carrera"] else None
            ),
            "fecha_egreso_carrera": fecha_egreso,
        },
        exigir_anio_uarg=True,
    )

    # Si la validación falla, los normalizados quedan vacíos: conservar
    # lo que escribió la persona para no borrarle los campos al volver
    # a mostrar el formulario. Los valores normalizados se usan cuando
    # no hay errores (que es cuando se persiste).
    datos["dni"] = normalizados["dni"] or datos["dni"]
    datos["legajo"] = normalizados["legajo"]
    errores.extend(errores_negocio)

    return datos, errores


def _materias_disponibles():
    """
    Catálogo completo de materias para el selector.

    El plan no restringe el selector: cualquier materia cargada por
    el usuario puede asignarse a una fila del analítico. Sólo se usa
    para verificar, ordenar y obtener el año.
    """

    return list(Materia.objects.order_by("nombre_materia"))


def _codigo_materia_generado(nombre):
    """Código estable para una materia nueva leída del Lincoln."""

    base = _slug(nombre) if nombre else "materia"
    codigo = f"L-{base}"[:50]
    sufijo = 2

    while Materia.objects.filter(codigo_materia=codigo).exists():
        codigo = f"L-{base}-{sufijo}"[:50]
        sufijo += 1

    return codigo


def _resolver_materia(codigo, nombre):
    """
    Devuelve la materia del catálogo para una fila del Lincoln.

    Busca por código y, si no, por nombre normalizado. Si no existe,
    la crea con el código/nombre leídos del Lincoln. Que la materia
    no esté en el plan se avisa, pero no bloquea la validación.
    """

    codigo = _limpiar(codigo)
    nombre = _limpiar(nombre)

    if codigo:
        materia = Materia.objects.filter(codigo_materia=codigo).first()

        if materia is not None:
            return materia

    if nombre:
        objetivo = _normalizar(nombre)

        for materia in Materia.objects.all():
            if _normalizar(materia.nombre_materia) == objetivo:
                return materia

    codigo_final = codigo or _codigo_materia_generado(nombre)

    materia, _ = Materia.objects.get_or_create(
        codigo_materia=codigo_final,
        defaults={"nombre_materia": nombre or codigo_final},
    )

    return materia


def _guardar_resoluciones(carrera, datos):
    """Sincroniza CARRERA_RESOLUCION con la selección del form."""

    institucionales = _lista_resoluciones(
        datos, "resoluciones_institucionales"
    )
    seleccionadas = set(institucionales)

    # Alta de las resoluciones tipeadas que no existen aún.
    for codigo in institucionales:
        Resolucion.objects.get_or_create(
            resolucion=codigo,
            defaults={
                "tipo_resolucion": TipoResolucion.INSTITUCIONAL,
            },
        )

    ministeriales = _lista_resoluciones(
        datos, "resoluciones_ministeriales"
    )
    otros = _lista_resoluciones(datos, "otros_instrumentos")

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
        pk=_limpiar(request.GET.get("dni")),
    ).first()

    registro = (
        GraduadoCarrera.objects
        .filter(
            dni_graduado=graduado,
            codigo_carrera=_limpiar(request.GET.get("carrera")),
        )
        .first()
        if graduado else None
    )

    return graduado, registro


def _preview_con_session(request, tipo_documento, dni, carrera):
    """
    Recupera la previsualización guardada en sesión.

    Se exige que coincidan usuario, tipo de documento, dni y
    carrera: así una sesión no muestra los datos de otra persona ni
    de otro trámite.
    """

    datos_session = request.session.get(CLAVE_SESION_PREVIEW)

    if not datos_session:
        return None

    usuario = getattr(request, "usuario_actual", None)
    usuario_id = getattr(usuario, "id_usuario", None)

    if (
        datos_session.get("tipo_documento") != tipo_documento.value
        or datos_session.get("usuario_id") != usuario_id
        or datos_session.get("dni") != dni
        or datos_session.get("carrera") != carrera
    ):
        return None

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
            advertencias=datos_session.get("advertencias"),
            promedios_calculados=datos_session.get(
                "promedios_calculados"
            ),
        ),
    )


def _datos_para_session(datos):
    """Convierte fechas a texto para poder guardarlas en sesión."""

    serializados = dict(datos)

    for campo in (
        "fecha_egreso",
        "fecha_egreso_carrera",
        "fecha_nacimiento",
    ):
        valor = serializados.get(campo)
        serializados[campo] = (
            valor.isoformat()
            if hasattr(valor, "isoformat")
            else (valor or "")
        )

    return serializados


def _filas_a_session(filas):
    """
    Convierte las filas editadas de la previsualización al formato de
    ``CLAVE_SESION_PREVIEW["examenes"]``.

    Se conservan tanto el valor crudo del Lincoln (para contrastar con
    el plan) como la corrección hecha por el usuario en el selector.
    """

    return [
        {
            "nombre_materia": fila.get("espacio") or "",
            "codigo_lincoln": (
                fila.get("codigo_lincoln")
                or fila.get("materia_codigo") or ""
            ),
            "nombre_lincoln": (
                fila.get("nombre_lincoln")
                or fila.get("espacio") or ""
            ),
            "fecha_examen": fila.get("fecha_examen") or "",
            "nota": fila.get("nota"),
            "nota_txt": (
                fila.get("nota_txt")
                if fila.get("nota_txt") is not None
                else (
                    "" if fila.get("nota") is None
                    else str(fila["nota"])
                )
            ),
            "tipo": fila.get("tipo") or "Examen",
            "acta_respaldatoria": (
                fila.get("respaldo")
                or fila.get("acta_respaldatoria") or ""
            ),
            "anio": fila.get("anio") or "",
            "anio_cursado": (
                fila.get("anio_cursado")
                or _entero_o_none(fila.get("anio"))
            ),
            "materia_codigo": fila.get("materia_codigo") or "",
            "es_requisito": bool(fila.get("es_requisito")),
            "orden": fila.get("orden_num") or fila.get("orden"),
        }
        for fila in filas
    ]


def _render_preview_no_guardada(request, tipo_documento, filas):
    """
    Vuelve a dibujar la previsualización sin tocar la sesión.

    Se usa cuando la acción no se pudo completar (nombre vacío, fila no
    encontrada, datos inválidos) para no perder las ediciones del POST.
    """

    datos, _ = _validar_datos(request.POST)
    carrera = Carrera.objects.filter(
        codigo_carrera=datos["carrera"]
    ).first()
    materias = _materias_disponibles()
    filas = _preparar_filas(carrera, filas, materias)
    calculado = promedios_desde_filas(filas, carrera)

    contexto = _contexto_preview(
        request,
        tipo_documento,
        datos,
        filas,
        materias,
        validado=False,
        modo_db=False,
        advertencias=calculado.advertencias,
        promedios_calculados={
            "sin_aplazo": calculado.promedio_sin_aplazo,
            "con_aplazo": calculado.promedio_con_aplazo,
        },
    )
    contexto["errores_revalidar"] = True

    return render(
        request,
        "academico/generacion_analiticos.html",
        contexto,
    )


def _guardar_preview_editada(request, tipo_documento, filas):
    """
    Persiste en sesión la grilla resultante de agregar/quitar una fila.

    No crea materias ni exámenes: eso sigue ocurriendo al validar. La
    previsualización se marca como no validada para obligar a revalidar.
    """

    datos, errores = _validar_datos(request.POST)
    carrera = Carrera.objects.filter(
        codigo_carrera=datos["carrera"]
    ).first()

    if errores or carrera is None:
        if carrera is None:
            errores.append("La carrera elegida no existe.")

        for error in errores:
            messages.error(request, error)

        return _render_preview_no_guardada(request, tipo_documento, filas)

    materias = _materias_disponibles()
    filas = _preparar_filas(carrera, filas, materias)
    calculado = promedios_desde_filas(filas, carrera)

    graduado = Graduado.objects.filter(
        pk=datos["dni"]
    ).first()
    registro = (
        GraduadoCarrera.objects.filter(
            dni_graduado=graduado,
            codigo_carrera_id=datos["carrera"],
        ).first()
        if graduado else None
    )

    datos.update(_promedio_para_preview(datos, calculado, registro))

    usuario = getattr(request, "usuario_actual", None)

    request.session[CLAVE_SESION_PREVIEW] = {
        "tipo_documento": tipo_documento.value,
        "usuario_id": getattr(usuario, "id_usuario", None),
        "dni": datos["dni"],
        "carrera": datos["carrera"],
        "advertencias": list(calculado.advertencias),
        "promedios_calculados": {
            "sin_aplazo": calculado.promedio_sin_aplazo,
            "con_aplazo": calculado.promedio_con_aplazo,
        },
        "datos": _datos_para_session(datos),
        "examenes": _filas_a_session(filas),
    }
    request.session.modified = True

    return _preview_con_session(
        request,
        tipo_documento,
        datos["dni"],
        datos["carrera"],
    )


def _agregar_materia(request, tipo_documento):
    """Agrega una fila escrita a mano a la previsualización."""

    filas = _filas_desde_post(request)
    nombre = _limpiar(request.POST.get("nueva_materia"))
    codigo = _limpiar(request.POST.get("nuevo_codigo"))

    if not nombre:
        messages.error(
            request,
            "Ingresá el nombre de la materia que querés agregar.",
        )

        return _render_preview_no_guardada(
            request, tipo_documento, filas
        )

    nota = _entero_o_none(_limpiar(request.POST.get("nueva_nota")))
    anio = _limpiar(request.POST.get("nuevo_anio"))

    # La materia nueva siempre se agrega al final; el orden se ajusta
    # después con las flechas de la previsualización.
    orden = len(filas) + 1

    filas.append({
        "indice": str(orden),
        "espacio": nombre,
        "materia_codigo": codigo,
        "codigo_lincoln": "",
        "nombre_lincoln": nombre,
        "nota": nota,
        "nota_txt": "" if nota is None else str(nota),
        "fecha_examen": _limpiar(request.POST.get("nueva_fecha")),
        "tipo": _limpiar(request.POST.get("nuevo_tipo")) or "Examen",
        "respaldo": _limpiar(request.POST.get("nuevo_acta")),
        "anio": anio,
        "anio_cursado": _entero_o_none(anio),
        "orden": f"{orden:02d}" if orden else "",
        "orden_num": orden,
        "es_requisito": _limpiar(
            request.POST.get("nueva_requisito")
        ) in ("si", "on", "1", "true"),
    })

    filas = _normalizar_orden(filas)

    messages.success(
        request,
        f"«{nombre}» se agregó a la previsualización. "
        "Volvé a validar el analítico para guardarla.",
    )

    return _guardar_preview_editada(request, tipo_documento, filas)


def _quitar_materia(request, tipo_documento):
    """Quita una fila de la previsualización (no del catálogo)."""

    filas = _filas_desde_post(request)
    objetivo = _limpiar(request.POST.get("fila_a_quitar"))

    restantes = [
        fila for fila in filas
        if str(fila.get("indice")) != objetivo
    ]

    if len(restantes) == len(filas):
        messages.error(
            request,
            "No se encontró la fila que querés quitar.",
        )

        return _render_preview_no_guardada(
            request, tipo_documento, filas
        )

    restantes = _normalizar_orden(restantes)

    messages.success(
        request,
        "La fila se quitó de la previsualización. "
        "Volvé a validar el analítico para guardar el cambio.",
    )

    return _guardar_preview_editada(request, tipo_documento, restantes)


def _preview_con_bd(request, tipo_documento, graduado, registro,
                    validado):
    contexto = contexto_analitico(
        graduado,
        registro.codigo_carrera,
        tipo_documento,
    )

    filas = [
        {**fila, "indice": indice, "matcheada": True}
        for indice, fila in enumerate(contexto["filas"], start=1)
    ]

    materias = _materias_disponibles()
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


def _preview_en_tramite_ro(request, graduado, registro, validado):
    """
    Preview de sólo lectura del título en trámite: muestra el
    documento desde la base y permite generar/descargar.
    """

    tipo_documento = TipoDocumentoAnalitico.EN_TRAMITE
    carrera = registro.codigo_carrera

    contexto = contexto_analitico(graduado, carrera, tipo_documento)

    filas = contexto["filas"]
    datos = _datos_precargados(graduado, registro)

    # Asegurar nombre/upper y formatos legibles para el RO.
    datos = dict(datos)
    datos["nombre"] = datos.get("nombre", "").upper()
    datos["apellido"] = datos.get("apellido", "").upper()

    registro_header = (
        f"{datos['apellido']}, {datos['nombre']} "
        f"· DNI {datos['dni']}"
    )

    return render(
        request,
        "academico/analitico_preview_ro.html",
        {
            "tipo_documento": tipo_documento,
            "datos": datos,
            "filas": filas,
            "validado": validado,
            "discrepancias_plan": _discrepancias_plan(filas),
            "dni_puntos": contexto["dni_con_puntos"],
            "fecha_egreso_formateada": contexto["fecha_egreso_larga"],
            "carrera_nombre": carrera.nombre_carrera,
            "registro_header": registro_header,
            "resoluciones_institucionales": contexto[
                "texto_resoluciones_institucionales"
            ],
        },
    )


@requiere_sesion
def generacion_analiticos(request):
    """Generar analítico: carga desde cero (sin buscador)."""
    url = reverse("generacion_analiticos")
    tipo_documento = TipoDocumentoAnalitico.TITULO

    dni_sel = _limpiar(request.GET.get("dni"))
    carrera_sel = _limpiar(request.GET.get("carrera"))

    if request.method == "POST":
        accion = request.POST.get("accion", "")

        if accion == "descartar_borrador":
            request.session.pop(CLAVE_SESION_BORRADOR, None)
            messages.info(request, "Borrador descartado.")

            return redirect(url)

        if accion == "continuar":
            return _continuar(request, tipo_documento)

        if accion == "validar":
            return _validar(request, tipo_documento)

        if accion == "recalcular":
            return _recalcular(request, tipo_documento)

        if accion == "agregar_materia":
            return _agregar_materia(request, tipo_documento)

        if accion == "quitar_materia":
            return _quitar_materia(request, tipo_documento)

        if accion == "descargar":
            return _descargar(request, tipo_documento)

        messages.error(
            request,
            "No se recibió la acción del botón. Volvé a presionarlo; "
            "si vuelve a pasar, actualizá la página.",
        )

        return _post_sin_accion(request, tipo_documento)

    modo = request.GET.get("modo", "carga")

    graduado, registro = _sel_desde(request)

    if modo == "preview":
        analitico_existe = (
            Analitico.objects
            .filter(
                dni_graduado=graduado,
                codigo_carrera=(
                    registro.codigo_carrera if registro else None
                ),
                tipo_documento=tipo_documento,
            )
            .exists()
            if registro else False
        )

        if not analitico_existe:
            preview = _preview_con_session(
                request,
                tipo_documento,
                dni_sel,
                carrera_sel,
            )

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
                "dni": dni_sel,
                "carrera": carrera_sel,
                "analitico_previo": Analitico.objects.filter(
                    dni_graduado=graduado,
                    codigo_carrera=registro.codigo_carrera,
                    tipo_documento=tipo_documento,
                ).exists(),
            },
        )

    # GET: formulario de carga (nunca buscador). El borrador tiene
    # prioridad sobre los datos de la BD cuando coincide el trámite.
    datos_borrador = _recuperar_borrador(
        request,
        tipo_documento,
        dni=dni_sel or None,
        carrera=carrera_sel or None,
    )
    hay_borrador = datos_borrador is not None

    if datos_borrador is not None:
        datos = datos_borrador
    elif graduado is not None and registro is not None:
        datos = _datos_precargados(graduado, registro)
    else:
        datos = {
            "carrera": carrera_sel,
            "nombre": "",
            "apellido": "",
            "dni": dni_sel or "",
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

    return _render_carga(
        request,
        tipo_documento,
        datos,
        hay_borrador=hay_borrador,
    )


@requiere_sesion
def titulo_en_tramite(request):
    """Título en trámite: sólo buscar y generar el documento."""
    url = reverse("titulo_en_tramite")
    tipo_documento = TipoDocumentoAnalitico.EN_TRAMITE

    if request.method == "POST":
        accion = request.POST.get("accion", "")

        if accion == "buscar":
            dni = _limpiar(request.POST.get("dni"))
            carrera = _limpiar(request.POST.get("carrera"))

            if not dni or not carrera:
                messages.error(
                    request,
                    "Ingresá DNI y carrera para buscar.",
                )

                return redirect(url)

            destino = f"{url}?" + urlencode({
                "modo": "preview",
                "dni": dni,
                "carrera": carrera,
            })

            graduado = Graduado.objects.filter(
                pk=dni,
            ).first()

            registro = (
                GraduadoCarrera.objects
                .filter(
                    dni_graduado=graduado,
                    codigo_carrera_id=carrera,
                )
                .first()
                if graduado else None
            )

            if graduado is None or registro is None:
                messages.error(
                    request,
                    "No hay un graduado con ese DNI en esa carrera. "
                    "Cargá los datos desde «Generar analítico».",
                )

                return redirect(url)

            return redirect(destino)

        if accion == "generar":
            # El documento es de sólo lectura; «generar» sólo
            # registra el documento como validado para habilitar
            # la descarga.
            dni = _limpiar(request.POST.get("dni"))
            carrera = _limpiar(request.POST.get("carrera"))

            graduado = Graduado.objects.filter(
                pk=dni,
            ).first()

            registro = (
                GraduadoCarrera.objects
                .filter(
                    dni_graduado=graduado,
                    codigo_carrera_id=carrera,
                )
                .first()
                if graduado else None
            )

            if graduado is None or registro is None:
                messages.error(
                    request,
                    "No hay un graduado con ese DNI en esa carrera.",
                )

                return redirect(url)

            if graduado.anio_ingreso_universidad is None:
                messages.error(
                    request,
                    "El graduado no tiene año de ingreso a la UARG. "
                    "Cargalo desde «Generar analítico» antes de "
                    "emitir el título en trámite.",
                )

                return redirect(url)

            usuario = getattr(request, "usuario_actual", None)

            Analitico.objects.update_or_create(
                dni_graduado=graduado,
                codigo_carrera_id=carrera,
                tipo_documento=tipo_documento,
                defaults={
                    "anio_ingreso_uarg": (
                        graduado.anio_ingreso_universidad
                    ),
                    "id_usuario": (
                        usuario if usuario and getattr(
                            usuario, "id_usuario", None,
                        ) else None
                    ),
                },
            )

            messages.success(
                request,
                "Título en trámite generado. Ya podés descargarlo.",
            )

            destino = f"{url}?" + urlencode({
                "modo": "preview",
                "dni": dni,
                "carrera": carrera,
            })

            return redirect(destino)

        if accion == "validar":
            return _validar(request, tipo_documento)

        if accion == "recalcular":
            return _recalcular(request, tipo_documento)

        if accion == "agregar_materia":
            return _agregar_materia(request, tipo_documento)

        if accion == "quitar_materia":
            return _quitar_materia(request, tipo_documento)

        if accion == "descargar":
            return _descargar(request, tipo_documento)

        messages.error(
            request,
            "No se recibió la acción del botón. Volvé a presionarlo; "
            "si vuelve a pasar, actualizá la página.",
        )

        return redirect(url)

    modo = request.GET.get("modo", "buscar")

    graduado, registro = _sel_desde(request)

    if modo == "preview":
        analitico_existe = (
            Analitico.objects
            .filter(
                dni_graduado=graduado,
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
                "No hay un graduado con ese DNI en esa carrera.",
            )

            return redirect(url)

        return _preview_en_tramite_ro(
            request,
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


def _armar_filas(examenes, carrera=None):
    """
    Arma las filas y el catálogo de materias para el selector.

    Los valores crudos del Lincoln se conservan aparte para contrastarlos
    con el plan aunque el usuario haya corregido el selector de materia.
    El plan sugiere orden y año, pero lo que ya guardó la grilla tiene
    prioridad; las discrepancias se adjuntan a cada fila.
    """

    materias = _materias_disponibles()

    filas = []

    for indice, examen in enumerate(examenes, start=1):
        materia = examen.get("materia")

        if materia is None and examen.get("materia_codigo"):
            materia = next(
                (
                    m for m in materias
                    if m.codigo_materia == examen["materia_codigo"]
                ),
                None,
            )

        # Si la fila todavía no tiene orden (certificado recién leído),
        # se deja vacío para que el plan lo sugiera. Si viene de la grilla
        # o de la base, se respeta la posición que ya tiene.
        orden_num = examen.get("orden")

        filas.append({
            "indice": indice,
            "orden": f"{orden_num:02d}" if orden_num else "",
            "orden_num": orden_num,
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
            "tipo": tipo_examen_legible(examen.get("tipo", "Examen"))
            or "Examen",
            "respaldo": examen.get("acta_respaldatoria", ""),
            "folio": _folio_de(examen.get("acta_respaldatoria", "")),
            "materia_codigo": (
                materia.codigo_materia
                if materia else examen.get("materia_codigo", "")
            ),
            "codigo_lincoln": (
                examen.get("codigo_lincoln")
                or examen.get("materia_codigo", "")
            ),
            "nombre_lincoln": (
                examen.get("nombre_lincoln")
                or examen.get("nombre_materia", "")
            ),
            "matcheada": bool(materia),
            "es_requisito": bool(examen.get("es_requisito")),
        })

    return (
        aplicar_plan_a_filas(carrera, filas, respetar_edicion=True),
        materias,
    )


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

    datos = dict(datos)

    for campo in (
        "resoluciones_institucionales",
        "resoluciones_ministeriales",
        "otros_instrumentos",
    ):
        datos[campo] = _lista_resoluciones(datos, campo)

    ciudades = Ciudad.objects.order_by("nombre_ciudad")

    return {
        "tipo_documento": tipo_documento,
        "datos": datos,
        "advertencias": advertencias or [],
        "carreras": carreras,
        "titulos": titulos,
        "provincias": provincias_sugeridas(),
        "ciudades": [c.nombre_ciudad for c in ciudades],
    }


def _render_carga(request, tipo_documento, datos, hay_borrador=False):
    """Dibuja el formulario de carga con el estado del borrador."""

    return render(
        request,
        "academico/generacion_analiticos.html",
        {
            **_contexto_formulario(request, tipo_documento, datos),
            "vista": "carga",
            "hay_borrador": hay_borrador,
        },
    )


def _render_carga_con_borrador(request, tipo_documento, datos):
    """Graba el borrador del POST y vuelve a mostrar el formulario."""

    guardado = _guardar_borrador(request, tipo_documento)

    return _render_carga(
        request,
        tipo_documento,
        datos,
        hay_borrador=guardado,
    )


def _post_sin_accion(request, tipo_documento):
    """
    Un POST sin «accion» significa que el botón submit no llegó (por
    ejemplo, si se deshabilitó durante el evento submit). En lugar
    de redirigir a un formulario vacío, se vuelve a mostrar lo que
    la persona había cargado.
    """

    # Si el POST viene de la previsualización, conservarla desde la
    # sesión en vez de devolver la pantalla de carga.
    if request.POST.getlist("fila_indice"):
        preview = _preview_con_session(
            request,
            tipo_documento,
            _limpiar(request.POST.get("dni")),
            _limpiar(request.POST.get("carrera")),
        )

        if preview is not None:
            return preview

    datos, _ = _validar_datos(request.POST)

    return _render_carga_con_borrador(request, tipo_documento, datos)


def _fecha_iso(valor):
    """Convierte una fecha a ISO para los <input type="date">."""

    if hasattr(valor, "isoformat"):
        return valor.isoformat()

    return valor or ""


CAMPOS_REQUERIDOS_ETIQUETAS = (
    ("nombre", "Nombre"),
    ("apellido", "Apellido"),
    ("dni", "DNI"),
    ("anio_ingreso_uarg", "Año de ingreso a UARG"),
    ("anio_ingreso_carrera", "Año de ingreso a la carrera"),
    ("fecha_egreso_carrera", "Fecha de egreso de la carrera"),
    ("fecha_nacimiento", "Fecha de nacimiento"),
    ("anio_egreso_secundario", "Año de egreso del secundario"),
    ("ciudad_nacimiento", "Ciudad de nacimiento"),
    ("provincia_nacimiento", "Provincia de nacimiento"),
    ("nombre_secundario", "Secundario"),
    ("ciudad_secundario", "Ciudad del secundario"),
    ("provincia_secundario", "Provincia del secundario"),
    ("titulo_secundario", "Título secundario"),
    ("titulo_otorgado", "Título a otorgar"),
)

CAMPOS_FILA_ETIQUETAS = (
    ("anio", "Año"),
    ("espacio", "Espacio curricular"),
    ("nota", "Nota"),
    ("fecha_examen", "Fecha"),
    ("tipo", "Tipo"),
    ("respaldo", "Acta respaldatoria"),
)


def _vacio(valor):
    return valor is None or (
        isinstance(valor, str) and not valor.strip()
    )


def _campos_faltantes(datos, filas):
    """
    Lista los campos vacíos que el usuario debe completar.

    No usa mensajes flash: la previsualización muestra este resumen
    y resalta las celdas correspondientes.
    """

    generales = [
        etiqueta
        for campo, etiqueta in CAMPOS_REQUERIDOS_ETIQUETAS
        if _vacio(datos.get(campo))
    ]

    por_fila = []

    for fila in filas:
        faltantes = [
            etiqueta
            for campo, etiqueta in CAMPOS_FILA_ETIQUETAS
            if _vacio(fila.get(campo))
        ]

        # Si hay acta pero no se pueden tomar los últimos 3 dígitos,
        # el folio tampoco se puede generar.
        if (
            not _vacio(fila.get("respaldo"))
            and fila.get("folio") in ("", "—")
        ):
            faltantes.append("Folio (revisar acta)")

        if faltantes:
            por_fila.append({
                "orden": fila.get("orden_num") or fila.get("orden"),
                "espacio": fila.get("espacio") or "Sin nombre",
                "faltantes": faltantes,
            })

    return {
        "generales": generales,
        "filas": por_fila,
    }


ETIQUETAS_DISCREPANCIA = {
    "sin_plan": "Sin plan vigente",
    "sin_codigo": "Sin código",
    "codigo_no_en_plan": "Código fuera del plan",
    "codigo_distinto": "Código distinto (por nombre)",
    "nombre_distinto": "Nombre distinto",
    "plan_incompleto": "Plan incompleto",
    "plan_no_vigente": "Plan no vigente",
}


def _discrepancias_plan(filas):
    """
    Avisos del contraste con el plan, listos para la previsualización.

    Son informativos: nunca se agregan a los errores del formulario ni
    impiden validar o descargar. Los avisos globales («sin plan» y
    «plan no vigente») se muestran una sola vez.
    """

    discrepancias = []
    sin_plan_visto = False
    plan_no_vigente_visto = False

    for fila in filas:
        verificacion = fila.get("verificacion")

        if not verificacion:
            continue

        if (
            verificacion.get("plan_no_vigente")
            and not plan_no_vigente_visto
        ):
            plan_no_vigente_visto = True

            discrepancias.append({
                "etiqueta": "Plan no vigente",
                "fila": "—",
                "codigo_lincoln": "",
                "nombre_lincoln": "",
                "codigo_esperado": "",
                "nombre_esperado": "",
                "mensaje": (
                    f"Se usó el plan {verificacion.get('plan_codigo', '')} "
                    "aunque no está marcado como vigente para la "
                    "carrera. Marcá uno en Gestión académica si "
                    "corresponde."
                ),
            })

        if verificacion.get("estado") == "ok":
            continue

        estado = verificacion["estado"]

        if estado == "sin_plan" and sin_plan_visto:
            continue

        if estado == "sin_plan":
            sin_plan_visto = True

        discrepancias.append({
            **verificacion,
            "etiqueta": ETIQUETAS_DISCREPANCIA.get(
                estado, "Discrepancia"
            ),
        })

    return discrepancias


def _preparar_filas(carrera, filas, materias):
    """
    Resuelve la materia del catálogo y completa las filas del POST.

    No crea materias: eso ocurre al validar. La verificación del plan se
    hace siempre con los valores crudos del Lincoln, que viajan en campos
    ocultos de la grilla. El orden y el año editados se respetan; el plan
    sólo completa lo que quedó vacío.
    """

    por_codigo = {m.codigo_materia: m for m in materias}

    for fila in filas:
        materia = por_codigo.get(fila.get("materia_codigo"))

        if materia is None:
            nombre = _normalizar(fila.get("espacio"))
            materia = next(
                (
                    m for m in materias
                    if _normalizar(m.nombre_materia) == nombre
                ),
                None,
            )

        if materia is not None:
            fila["materia_codigo"] = materia.codigo_materia
            fila["espacio"] = materia.nombre_materia

        fila["materia_obj"] = materia
        fila["matcheada"] = materia is not None

    return aplicar_plan_a_filas(carrera, filas, respetar_edicion=True)


def _contexto_preview(request, tipo_documento, datos, filas, materias,
                      validado, modo_db, advertencias=None,
                      promedios_calculados=None):
    titulos = Titulo.objects.select_related("codigo_carrera").order_by(
        "nombre_titulo"
    )

    datos_formulario = dict(datos)

    for campo in (
        "resoluciones_institucionales",
        "resoluciones_ministeriales",
        "otros_instrumentos",
    ):
        datos_formulario[campo] = _lista_resoluciones(datos, campo)

    datos_formulario["fecha_nacimiento"] = _fecha_iso(
        datos.get("fecha_nacimiento")
    )
    datos_formulario["fecha_egreso_carrera"] = _fecha_iso(
        datos.get("fecha_egreso_carrera") or datos.get("fecha_egreso")
    )

    # Los <input type="number"> exigen punto decimal: la
    # localización de Django usaría coma.
    for campo in ("promedio_sin_aplazo", "promedio_con_aplazo"):
        valor = datos.get(campo)

        if valor is not None and valor != "":
            datos_formulario[campo] = f"{float(valor):.2f}"
        else:
            datos_formulario[campo] = ""

    return {
        "tipo_documento": tipo_documento,
        "vista": "preview",
        "datos": datos_formulario,
        "filas": filas,
        "materias": materias,
        "validado": validado,
        "modo_db": modo_db,
        "advertencias": advertencias or [],
        "discrepancias_plan": _discrepancias_plan(filas),
        "campos_faltantes": _campos_faltantes(
            datos_formulario,
            filas,
        ),
        "promedios_calculados": promedios_calculados or {},
        "titulos": titulos,
        "provincias": provincias_sugeridas(),
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

        return _render_carga_con_borrador(request, tipo_documento, datos)

    carrera = Carrera.objects.filter(codigo_carrera=datos["carrera"]).first()

    if carrera is None:
        messages.error(request, "La carrera elegida no existe.")

        return _render_carga_con_borrador(request, tipo_documento, datos)

    materias = _materias_disponibles()

    # --- Exámenes: del Lincoln subido o de la base.
    examenes = []

    lincoln_file = request.FILES.get("archivo_notas")

    if lincoln_file:
        error_archivo = validar_archivo(lincoln_file, ["xls", "xlsx"])

        if error_archivo:
            messages.error(request, error_archivo)

            return _render_carga_con_borrador(request, tipo_documento, datos)

        try:
            lincoln = leer_lincoln(lincoln_file)
        except ErrorLincoln as error:
            messages.error(request, str(error))

            return _render_carga_con_borrador(request, tipo_documento, datos)

        for indice, examen in enumerate(
            lincoln["examenes"],
            start=1,
        ):
            materia = matcheo_materia(examen, materias)

            examenes.append({
                "nombre_materia": examen["nombre_materia"],
                "codigo_lincoln": examen["codigo_materia"],
                "nombre_lincoln": examen["nombre_materia"],
                "fecha_examen": (
                    examen["fecha_examen"].isoformat()
                    if examen["fecha_examen"] else ""
                ),
                "nota": examen["nota"],
                "tipo": examen["tipo"],
                "acta_respaldatoria": examen["acta_respaldatoria"],
                # El año de calendario del certificado no es el año de
                # cursada: la grilla muestra el año del plan como
                # sugerencia y el usuario puede cambiarlo.
                "anio_cursado": None,
                "materia": materia,
                "materia_codigo": (
                    materia.codigo_materia
                    if materia else examen["codigo_materia"]
                ),
                "es_requisito": False,
                # Sin orden inicial: el plan sugiere las posiciones en
                # la primera previsualización.
                "orden": None,
            })

    else:
        graduado_db = Graduado.objects.filter(
            pk=datos["dni"]
        ).first()

        if graduado_db:
            materias_por_codigo = {
                m.codigo_materia: m for m in materias
            }

            for fila in examenes_ordenados(graduado_db, carrera):
                materia = materias_por_codigo.get(fila["materia_codigo"])

                verificacion = fila.get("verificacion", {})

                examenes.append({
                    "nombre_materia": fila["espacio"],
                    "codigo_lincoln": (
                        verificacion.get("codigo_lincoln")
                        or fila["materia_codigo"]
                    ),
                    "nombre_lincoln": (
                        verificacion.get("nombre_lincoln")
                        or fila["espacio"]
                    ),
                    "fecha_examen": fila["fecha_examen"],
                    "nota": fila["nota"],
                    "tipo": fila["tipo"],
                    "acta_respaldatoria": fila["respaldo"],
                    "anio_cursado": fila["anio"] or None,
                    "materia": materia,
                    "materia_codigo": (
                        materia.codigo_materia
                        if materia else fila["materia_codigo"]
                    ),
                    "es_requisito": fila.get("es_requisito", False),
                    "orden": fila.get("orden_num"),
                })

    if not examenes:
        messages.error(
            request,
            "No hay exámenes para generar el analítico. "
            "Adjuntá el Certificado Lincoln.",
        )

        return _render_carga_con_borrador(request, tipo_documento, datos)

    # --- Promedios: se calculan desde los exámenes del trámite.
    graduado = Graduado.objects.filter(
        pk=datos["dni"]
    ).first()

    registro = (
        GraduadoCarrera.objects
        .filter(
            dni_graduado=graduado,
            codigo_carrera_id=datos["carrera"],
        )
        .first()
        if graduado else None
    )

    calculado = promedios_desde_filas(examenes, carrera)
    datos.update(_promedio_para_preview(datos, calculado, registro))

    advertencias = list(calculado.advertencias)

    usuario = getattr(request, "usuario_actual", None)

    request.session[CLAVE_SESION_PREVIEW] = {
        "tipo_documento": tipo_documento.value,
        "usuario_id": getattr(usuario, "id_usuario", None),
        "dni": datos["dni"],
        "carrera": datos["carrera"],
        "advertencias": advertencias,
        "promedios_calculados": {
            "sin_aplazo": calculado.promedio_sin_aplazo,
            "con_aplazo": calculado.promedio_con_aplazo,
        },
        "datos": _datos_para_session(datos),
        "examenes": [
            {
                "nombre_materia": examen["nombre_materia"],
                "codigo_lincoln": (
                    examen.get("codigo_lincoln")
                    or examen.get("materia_codigo") or ""
                ),
                "nombre_lincoln": (
                    examen.get("nombre_lincoln")
                    or examen.get("nombre_materia") or ""
                ),
                "fecha_examen": examen["fecha_examen"],
                "nota": examen["nota"],
                "tipo": examen["tipo"],
                "acta_respaldatoria": examen["acta_respaldatoria"],
                "anio_cursado": examen.get("anio_cursado"),
                "materia_codigo": examen.get("materia_codigo") or "",
                "es_requisito": examen.get("es_requisito", False),
                "orden": examen.get("orden"),
            }
            for examen in examenes
        ],
    }
    request.session.modified = True

    # Los datos ya están en la previsualización: el borrador cumplió
    # su objetivo y no debe reaparecer al volver a la carga.
    request.session.pop(CLAVE_SESION_BORRADOR, None)

    destino = (
        f"{url}?{urlencode({'modo': 'preview', 'dni': datos['dni'], 'carrera': datos['carrera']})}"
    )

    # Si el graduado ya está guardado en el sistema, preguntar
    # antes de tocar nada.
    if graduado is not None and registro is not None:
        return render(
            request,
            "academico/generacion_analiticos.html",
            {
                "tipo_documento": tipo_documento,
                "vista": "elegir",
                "graduado": graduado,
                "registro": registro,
                "dni": datos["dni"],
                "carrera": datos["carrera"],
                "analitico_previo": Analitico.objects.filter(
                    dni_graduado=graduado,
                    codigo_carrera_id=datos["carrera"],
                    tipo_documento=tipo_documento,
                ).exists(),
            },
        )


    return redirect(destino)


def _entero_o_none(valor):
    texto = _limpiar(valor)

    if not texto:
        return None

    try:
        return int(float(texto))
    except (TypeError, ValueError):
        return None


def _normalizar_orden(filas):
    """
    Ordena las filas según el orden manual ingresado por el usuario.

    Se usa el número que el usuario escribió en la columna «Orden»:
    ese orden es el que se guarda al validar y el que lleva el
    documento. Las filas sin orden van al final y se renumera 1..N
    para que la grilla quede prolija.
    """

    ordenadas = sorted(
        enumerate(filas),
        key=lambda par: (
            par[1].get("orden_num") is None,
            par[1].get("orden_num") or 0,
            par[0],
        ),
    )

    resultado = []

    for posicion, (_, fila) in enumerate(ordenadas, start=1):
        fila["orden_num"] = posicion
        fila["orden"] = f"{posicion:02d}"
        resultado.append(fila)

    return resultado


def _filas_desde_post(request):
    indices = request.POST.getlist("fila_indice")
    espacios = request.POST.getlist("fila_espacio")
    notas = request.POST.getlist("fila_nota")
    fechas = request.POST.getlist("fila_fecha")
    tipos = request.POST.getlist("fila_tipo")
    actas = request.POST.getlist("fila_respaldo")
    anios = request.POST.getlist("fila_anio")
    codigos = request.POST.getlist("fila_materia")
    ordenes = request.POST.getlist("fila_orden")
    codigos_lincoln = request.POST.getlist("fila_codigo_lincoln")
    nombres_lincoln = request.POST.getlist("fila_nombre_lincoln")

    filas = []

    for i in range(len(indices)):
        nota_txt = notas[i].strip()

        try:
            nota = int(nota_txt)
        except ValueError:
            nota = None

        clave = indices[i].strip() or str(i + 1)

        orden_txt = ordenes[i].strip() if i < len(ordenes) else ""
        orden_num = _entero_o_none(orden_txt)

        requisito = request.POST.get(
            f"fila_requisito_{clave}"
        ) in ("si", "on", "1", "true")

        filas.append({
            "indice": clave,
            "orden": f"{orden_num:02d}" if orden_num else "",
            "orden_num": orden_num,
            "espacio": espacios[i].strip(),
            "nota": nota,
            "nota_txt": nota_txt,
            "fecha_examen": fechas[i].strip(),
            "tipo": tipos[i].strip() or "Examen",
            "acta_respaldatoria": actas[i].strip(),
            "anio": anios[i].strip(),
            "anio_cursado": _entero_o_none(anios[i]),
            "materia_codigo": codigos[i].strip(),
            "codigo_lincoln": (
                codigos_lincoln[i].strip()
                if i < len(codigos_lincoln) else ""
            ),
            "nombre_lincoln": (
                nombres_lincoln[i].strip()
                if i < len(nombres_lincoln) else ""
            ),
            "es_requisito": requisito,
        })

    return _normalizar_orden(filas)


# ==================================================
# PROMEDIOS
# ==================================================

def _promedio_para_preview(datos, calculado, registro):
    """
    Resuelve qué promedios mostrar en la previsualización.

    El valor calculado desde los exámenes manda siempre. Los valores
    que vinieran de un formulario o de una importación sólo se usan
    como respaldo cuando no hay exámenes promediables.
    """

    resultado = {}

    for campo, valor_calc in (
        ("promedio_sin_aplazo", calculado.promedio_sin_aplazo),
        ("promedio_con_aplazo", calculado.promedio_con_aplazo),
    ):
        valor_actual = (
            getattr(registro, campo) if registro is not None else None
        )

        if valor_calc is not None:
            resultado[campo] = valor_calc
        elif datos.get(campo) is not None:
            resultado[campo] = datos[campo]
        else:
            resultado[campo] = valor_actual

    return resultado


def _resolver_promedios_guardar(datos, calculado, registro):
    """
    Decide el valor y el origen de cada promedio al validar.

    La fuente de verdad es la previsualización: el valor calculado
    desde los exámenes, o el valor que el usuario editó ahí mismo.
    Los promedios cargados por formulario/importación nunca ganan
    sobre ese valor.
    """

    resolucion = {}
    overrides = []

    for campo, origen_campo, valor_calc, nombre in (
        (
            "promedio_sin_aplazo",
            "origen_promedio_sin_aplazo",
            calculado.promedio_sin_aplazo,
            "sin aplazo",
        ),
        (
            "promedio_con_aplazo",
            "origen_promedio_con_aplazo",
            calculado.promedio_con_aplazo,
            "con aplazo",
        ),
    ):
        valor_actual = (
            getattr(registro, campo) if registro is not None else None
        )
        origen_actual = (
            getattr(registro, origen_campo)
            if registro is not None
            else OrigenPromedio.IMPORTADO
        )
        valor_post = datos.get(campo)

        if valor_post is not None and valor_calc is not None and mismo_promedio(
            valor_post, valor_calc
        ):
            resolucion[campo] = (valor_calc, OrigenPromedio.CALCULADO)
            continue

        if valor_post is not None:
            overrides.append({
                "origen": "previsualizacion",
                "promedio": nombre,
                "anterior": (
                    valor_calc if valor_calc is not None else valor_actual
                ),
                "nuevo": valor_post,
                "calculado": valor_calc,
            })
            resolucion[campo] = (valor_post, OrigenPromedio.MANUAL)
            continue

        if valor_calc is not None:
            resolucion[campo] = (valor_calc, OrigenPromedio.CALCULADO)
            continue

        # Sin exámenes promediables: conservar lo que ya hubiera.
        resolucion[campo] = (valor_actual, origen_actual)

    return resolucion, overrides


def _recalcular(request, tipo_documento):
    """
    Recalcula los promedios desde los exámenes de la previsualización
    y los vuelve a mostrar. Vuelve al valor calculado aunque el
    usuario hubiera editado un promedio a mano.

    No crea materias: la creación automática ocurre al validar.
    """

    datos, errores = _validar_datos(request.POST)
    filas = _filas_desde_post(request)

    carrera = Carrera.objects.filter(
        codigo_carrera=datos["carrera"]
    ).first()

    materias = _materias_disponibles()
    filas = _preparar_filas(carrera, filas, materias)

    if errores or carrera is None:
        for error in errores:
            messages.error(request, error)

        return render(
            request,
            "academico/generacion_analiticos.html",
            {
                **_contexto_preview(
                    request,
                    tipo_documento,
                    datos,
                    filas,
                    materias,
                    validado=False,
                    modo_db=False,
                ),
                "errores_revalidar": True,
            },
        )

    calculado = promedios_desde_filas(filas, carrera)

    datos["promedio_sin_aplazo"] = calculado.promedio_sin_aplazo
    datos["promedio_con_aplazo"] = calculado.promedio_con_aplazo

    return render(
        request,
        "academico/generacion_analiticos.html",
        _contexto_preview(
            request,
            tipo_documento,
            datos,
            filas,
            materias,
            validado=False,
            modo_db=False,
            advertencias=calculado.advertencias,
            promedios_calculados={
                "sin_aplazo": calculado.promedio_sin_aplazo,
                "con_aplazo": calculado.promedio_con_aplazo,
            },
        ),
    )


def _validar(request, tipo_documento):
    url = _url_analitico(tipo_documento)

    datos, errores = _validar_datos(request.POST)

    filas = _filas_desde_post(request)

    errores = list(errores)

    # El analítico se genera con los espacios en blanco que falten:
    # no se exige acta ni nota por fila ni que la materia exista en
    # el catálogo. Si no existe, se crea automáticamente al validar.
    carrera_obj = Carrera.objects.filter(
        codigo_carrera=datos["carrera"]
    ).first()

    if carrera_obj is None:
        errores.append("La carrera elegida no existe.")

    materias = _materias_disponibles()

    # Resolver contra el catálogo y aplicar el plan. Las discrepancias
    # se informan en la previsualización, pero no se agregan a
    # ``errores``: la validación y la descarga siguen habilitadas.
    filas = _preparar_filas(carrera_obj, filas, materias)

    if errores:
        for error in errores:
            messages.error(request, error)

        contexto = _contexto_preview(
            request,
            tipo_documento,
            datos,
            filas,
            materias,
            validado=False,
            modo_db=False,
        )
        contexto["errores_revalidar"] = True

        return render(
            request,
            "academico/generacion_analiticos.html",
            contexto,
        )

    carrera = carrera_obj

    # El DNI es la clave primaria: si ya existe, se actualiza ese
    # mismo graduado. No hay conflicto con otro registro posible.

    calculado = promedios_desde_filas(filas, carrera)

    registro_actual = (
        GraduadoCarrera.objects
        .filter(
            dni_graduado_id=datos["dni"],
            codigo_carrera=carrera,
        )
        .first()
    )

    promedios, overrides = _resolver_promedios_guardar(
        datos,
        calculado,
        registro_actual,
    )

    usuario = getattr(request, "usuario_actual", None)

    with transaction.atomic():
        fecha_egreso = datos["fecha_egreso"]

        graduado, _ = Graduado.objects.update_or_create(
            pk=datos["dni"],
            defaults={
                "nombre": datos["nombre"],
                "apellido": datos["apellido"],
                "anio_ingreso_universidad": datos["anio_ingreso_uarg"],
            },
        )

        registro, _ = GraduadoCarrera.objects.update_or_create(
            dni_graduado=graduado,
            codigo_carrera=carrera,
            defaults={
                "fecha_ingreso_carrera": date(
                    datos["anio_ingreso_carrera"],
                    3,
                    1,
                ),
                "fecha_egreso_carrera": fecha_egreso,
                "promedio_sin_aplazo": promedios[
                    "promedio_sin_aplazo"
                ][0],
                "promedio_con_aplazo": promedios[
                    "promedio_con_aplazo"
                ][0],
                "origen_promedio_sin_aplazo": promedios[
                    "promedio_sin_aplazo"
                ][1],
                "origen_promedio_con_aplazo": promedios[
                    "promedio_con_aplazo"
                ][1],
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
            dni_graduado=graduado,
            defaults={
                "fecha_nacimiento": datos["fecha_nacimiento"],
                "id_provincia": provincia_nac,
                "id_ciudad": ciudad_nac,
            },
        )

        Secundario.objects.update_or_create(
            dni_graduado=graduado,
            defaults={
                "nombre_secundario": datos["nombre_secundario"],
                "id_provincia": provincia_sec,
                "id_ciudad": ciudad_sec,
                "titulo_secundario": datos["titulo_secundario"],
                "anio_egreso_secundario": (
                    datos["anio_egreso_secundario"]
                ),
            },
        )

        titulo_otorgado = datos["titulo_otorgado"]

        if titulo_otorgado:
            Titulo.objects.get_or_create(
                codigo_carrera=carrera,
                nombre_titulo=titulo_otorgado,
            )

        _guardar_resoluciones(carrera, datos)

        # --- Materias del Lincoln que no estaban en el catálogo:
        # se crean con el código/nombre leídos. El plan sólo avisa;
        # nunca impide validar ni genera materias por su cuenta.
        for fila in filas:
            materia = fila.get("materia_obj")

            if materia is None:
                materia = _resolver_materia(
                    fila["materia_codigo"],
                    fila["espacio"],
                )
                fila["materia_obj"] = materia
                fila["materia_codigo"] = materia.codigo_materia

        # --- Exámenes: reemplazar los del graduado para
        # esta carrera (no tocar las otras carreras).
        GraduadoExamen.objects.filter(
            dni_graduado=graduado,
            codigo_carrera=carrera,
        ).delete()

        for fila in filas:
            materia = fila["materia_obj"]

            fecha = (
                date.fromisoformat(fila["fecha_examen"])
                if fila["fecha_examen"] else None
            )

            # Examen: una acta puede respaldar varias materias,
            # por eso la unicidad es (acta, materia).
            acta = fila["acta_respaldatoria"] or None
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

            GraduadoExamen.objects.update_or_create(
                id_examen=examen,
                dni_graduado=graduado,
                codigo_carrera=carrera,
                defaults={
                    "nota": fila["nota"],
                    "resultado": resultado,
                    "es_requisito": fila["es_requisito"],
                    # Año y orden son los que salen de la grilla: el plan
                    # los sugiere, pero el usuario puede cambiarlos.
                    "anio_cursado": fila.get("anio_num"),
                    "orden": fila["orden_num"],
                },
            )

        Analitico.objects.update_or_create(
            dni_graduado=graduado,
            codigo_carrera=carrera,
            tipo_documento=tipo_documento,
            defaults={
                "anio_ingreso_uarg": datos["anio_ingreso_uarg"],
                "id_usuario": usuario,
            },
        )

        registrar_auditoria(
            usuario,
            "analitico_validado",
            entidad="Analitico",
            entidad_id=f"{datos['dni']}|{datos['carrera']}",
            detalle={
                "tipo_documento": tipo_documento.value,
                "promedio_sin_aplazo": promedios[
                    "promedio_sin_aplazo"
                ][0],
                "origen_sin_aplazo": promedios[
                    "promedio_sin_aplazo"
                ][1],
                "promedio_con_aplazo": promedios[
                    "promedio_con_aplazo"
                ][0],
                "origen_con_aplazo": promedios[
                    "promedio_con_aplazo"
                ][1],
                "calculado_sin_aplazo": calculado.promedio_sin_aplazo,
                "calculado_con_aplazo": calculado.promedio_con_aplazo,
                "advertencias": calculado.advertencias,
            },
        )

        for override in overrides:
            registrar_auditoria(
                usuario,
                "promedio_override",
                entidad="GraduadoCarrera",
                entidad_id=f"{datos['dni']}|{datos['carrera']}",
                detalle=override,
            )

        for duplicado in calculado.duplicados:
            registrar_auditoria(
                usuario,
                "promedio_materia_duplicada",
                entidad="GraduadoCarrera",
                entidad_id=f"{datos['dni']}|{datos['carrera']}",
                detalle=duplicado,
            )

    # La previsualización de sesión ya no aplica: el documento se
    # vuelve a leer desde la base. Tampoco el borrador de carga.
    request.session.pop(CLAVE_SESION_PREVIEW, None)
    request.session.pop(CLAVE_SESION_BORRADOR, None)

    for advertencia in calculado.advertencias:
        messages.warning(request, advertencia)

    messages.success(request, "Analítico validado y guardado.")

    destino = (
        f"{url}?{urlencode({'modo': 'preview', 'dni': datos['dni'], 'carrera': datos['carrera']})}"
    )

    return redirect(destino)


def _faltantes_para_descarga(contexto):
    """Datos esenciales que impiden generar el documento del título."""

    graduado = contexto["graduado"]
    registro = contexto["registro"]
    nacimiento = contexto["datos_nacimiento"]
    secundario = contexto["secundario"]

    valores = (
        ("Nombre", getattr(graduado, "nombre", None)),
        ("Apellido", getattr(graduado, "apellido", None)),
        ("DNI", getattr(graduado, "dni", None)),
        (
            "Año de ingreso a la carrera",
            contexto.get("anio_ingreso_carrera"),
        ),
        ("Fecha de egreso", contexto.get("fecha_egreso")),
        (
            "Fecha de nacimiento",
            getattr(nacimiento, "fecha_nacimiento", None),
        ),
        (
            "Nombre del secundario",
            getattr(secundario, "nombre_secundario", None),
        ),
        (
            "Título secundario",
            getattr(secundario, "titulo_secundario", None),
        ),
        (
            "Año de egreso del secundario",
            getattr(secundario, "anio_egreso_secundario", None),
        ),
    )

    faltantes = [
        etiqueta for etiqueta, valor in valores if _vacio(valor)
    ]

    if not contexto.get("filas"):
        faltantes.append("Exámenes")

    return faltantes


def _descargar(request, tipo_documento):
    dni = _limpiar(request.POST.get("dni"))
    carrera_codigo = _limpiar(request.POST.get("carrera"))

    destino = (
        f"{_url_analitico(tipo_documento)}?"
        + urlencode({
            "modo": "preview",
            "dni": dni,
            "carrera": carrera_codigo,
        })
    )

    graduado = Graduado.objects.filter(
        pk=dni
    ).first()
    carrera = Carrera.objects.filter(
        codigo_carrera=carrera_codigo
    ).first()

    if graduado is None or carrera is None:
        messages.error(
            request,
            "No se encontró el graduado o la carrera del analítico.",
        )

        return redirect(destino)

    if not Analitico.objects.filter(
        dni_graduado=graduado,
        codigo_carrera=carrera,
        tipo_documento=tipo_documento,
    ).exists():
        messages.error(
            request,
            "El analítico todavía no fue validado.",
        )

        return redirect(destino)

    # Una edición pendiente en la grilla todavía no está en la base:
    # descargar en ese estado generaría un documento desactualizado.
    pendiente = request.session.get(CLAVE_SESION_PREVIEW) or {}

    if (
        pendiente.get("tipo_documento") == tipo_documento.value
        and pendiente.get("dni") == dni
        and pendiente.get("carrera") == carrera_codigo
    ):
        messages.error(
            request,
            "Tenés cambios sin validar en la previsualización. "
            "Presioná «Validar analítico» antes de descargar.",
        )

        return redirect(destino)

    try:
        contexto = contexto_analitico(graduado, carrera, tipo_documento)

        # El título en trámite es incompleto por definición; el título
        # final sí exige los datos básicos antes de emitirse.
        if tipo_documento == TipoDocumentoAnalitico.TITULO:
            faltantes = _faltantes_para_descarga(contexto)

            if faltantes:
                messages.error(
                    request,
                    "No se puede descargar el título: faltan "
                    + ", ".join(faltantes) + ".",
                )

                return redirect(destino)

        contenido = render_docx(contexto)
    except Exception as error:
        messages.error(
            request,
            "No se pudo generar el documento. Revisá los datos del "
            f"analítico e intentá de nuevo. Detalle: {error}",
        )

        return redirect(destino)

    nombre = (
        f"Analitico_{_slug(graduado.apellido)}_"
        f"{_slug(graduado.nombre)}_{graduado.dni}.docx"
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
