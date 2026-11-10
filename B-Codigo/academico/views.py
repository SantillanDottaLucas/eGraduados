from datetime import date

from django.contrib.auth.hashers import check_password
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from .autenticacion import (
    CLAVE_SESION,
    codigo_valido,
    obtener_usuario_sesion,
    requiere_sesion,
    url_siguiente_segura,
)
from .models import Carrera, Escuela, GraduadoCarrera, Usuario

from academico.servicios.moduloCarga.carga_datos import CargaDatos

from .servicios.moduloAnalitico import *

from .servicios.moduloEstadistica.consulta_estadisticas import (
    consultar_graduados_por_anio,
    consultar_promedios,
    consultar_total,
    consultar_tiempos,
)

from .servicios.moduloEstadistica.graficador_estadistico import (
    graficar_graduados_por_anio,
    graficar_promedio,
    graficar_total,
    graficar_tiempos,
)

from .servicios.moduloGraduados.consulta_graduados import (
    obtener_graduados_filtrados,
)

from .servicios.moduloGraduados.exportar_graduados import (
    generar_excel_graduados,
)


# ==========================================
# 0. INGRESO Y SALIDA
# ==========================================

def login(request):
    """
    Página de ingreso: el usuario carga su email de Gmail
    (que debe existir en la base de datos) y un código
    alfanumérico de 6 caracteres.
    """

    error = None
    siguiente = request.GET.get("next", "")

    # Un usuario ya logueado no necesita ver el login.
    if obtener_usuario_sesion(request) is not None:
        return redirect("index")

    if request.method == "POST":
        email = (request.POST.get("email") or "").strip().lower()
        codigo = (request.POST.get("codigo") or "").strip()

        if not email or not codigo:
            error = "Completá tu email y tu código de acceso."

        elif not codigo_valido(codigo):
            error = (
                "El código debe tener exactamente 6 "
                "caracteres alfanuméricos."
            )

        else:
            usuario = (
                Usuario.objects
                .filter(email__iexact=email)
                .select_related("id_rol")
                .first()
            )

            # Mensaje genérico: no revela si el email existe.
            if usuario is None or not check_password(
                codigo,
                usuario.codigo_acceso,
            ):
                error = "El email o el código son incorrectos."

            else:
                request.session[CLAVE_SESION] = usuario.id_usuario

                destino = url_siguiente_segura(request, siguiente)
                return redirect(destino or "index")

    return render(
        request,
        "academico/login.html",
        {"error": error},
    )


def logout(request):
    """Cierra la sesión del usuario."""

    if request.method == "POST":
        request.session.flush()

    return redirect("login")


# ==========================================
# 1. PÁGINAS PRINCIPALES
# ==========================================

@requiere_sesion
def index(request):
    return render(request, "academico/index.html")


# ==========================================
# 2. CONTEXTO COMPARTIDO
# ==========================================

def obtener_contexto_base():
    """
    Obtiene las carreras, escuelas y la fecha actual.
    Carrera referencia a Escuela mediante id_escuela.
    """
    carreras = Carrera.objects.all().order_by("nombre_carrera")
    escuelas = Escuela.objects.all().order_by("nombre_escuela")

    return {
        "carreras": carreras,
        "escuelas": escuelas,
        "fechaFin": date.today(),
    }


# ==========================================
# 3. ESTADÍSTICAS
# ==========================================

@requiere_sesion
def estadisticas(request):
    """
    Tablero estadístico unificado.

    Un único panel de filtros alimenta las cuatro
    estadísticas: promedios, cantidades, tiempos de
    graduación y graduados por año.
    """

    contexto = obtener_contexto_base()

    # ==========================================
    # 1. Leer los filtros
    # ==========================================

    tipo_promedio = request.GET.get(
        "promedio",
        "promedio_sin_aplazo",
    )
    filtro = request.GET.get("filtro", "todos")
    carrera = request.GET.get("carrera") or None
    escuela = request.GET.get("escuela") or None
    fecha_inicio = request.GET.get("fechaInicio") or None
    fecha_fin = request.GET.get("fechaFin") or None

    if tipo_promedio not in (
        "promedio_sin_aplazo",
        "promedio_con_aplazo",
    ):
        tipo_promedio = "promedio_sin_aplazo"

    if filtro not in ("todos", "carrera", "escuela"):
        filtro = "todos"

    # ==========================================
    # 2. Validar el período en el servidor
    # ==========================================

    aviso_fechas = None
    fecha_inicio_valida = None
    fecha_fin_valida = None

    if fecha_inicio or fecha_fin:

        try:
            fecha_inicio_valida = (
                date.fromisoformat(fecha_inicio)
                if fecha_inicio else None
            )

            fecha_fin_valida = (
                date.fromisoformat(fecha_fin)
                if fecha_fin else None
            )

        except ValueError:
            aviso_fechas = (
                "El período indicado no es válido y fue ignorado."
            )

        else:
            if (
                fecha_inicio_valida
                and fecha_fin_valida
                and fecha_inicio_valida > fecha_fin_valida
            ):
                aviso_fechas = (
                    "La fecha de inicio no puede ser posterior a "
                    "la fecha de fin; el período fue ignorado."
                )

                fecha_inicio_valida = None
                fecha_fin_valida = None

    # ==========================================
    # 3. Consultar las cuatro estadísticas
    # ==========================================

    resultado_promedios = consultar_promedios(
        tipo_promedio,
        filtro,
        carrera,
        escuela,
        fecha_inicio_valida,
        fecha_fin_valida,
    )

    resultado_total = consultar_total(
        filtro,
        carrera,
        escuela,
        fecha_inicio_valida,
        fecha_fin_valida,
    )

    resultado_tiempos = consultar_tiempos(
        filtro,
        carrera,
        escuela,
        fecha_inicio_valida,
        fecha_fin_valida,
    )

    resultado_anios = consultar_graduados_por_anio(
        filtro,
        carrera,
        escuela,
        fecha_inicio_valida,
        fecha_fin_valida,
    )

    # ==========================================
    # 4. Preparar los datos para Chart.js
    # ==========================================

    contexto.update({
        "tipo_promedio": tipo_promedio,

        "aviso_fechas": aviso_fechas,

        "resultado_promedio": resultado_promedios.get("promedio"),
        "varianza_promedios": resultado_promedios.get("varianza"),
        "resultado_total": resultado_total,
        "resultado_tiempo": resultado_tiempos,
        "resultado_anios": resultado_anios,

        "datos_promedios": graficar_promedio(resultado_promedios),
        "datos_totales": graficar_total(resultado_total),
        "datos_tiempos": graficar_tiempos(resultado_tiempos),
        "datos_anios": graficar_graduados_por_anio(resultado_anios),
    })

    return render(
        request,
        "academico/estadisticas.html",
        contexto,
    )


# ==========================================
# 4. LISTADO DE GRADUADOS
# ==========================================

@requiere_sesion
def lista_graduados(request):
    from django.core.paginator import Paginator

    from .models import Analitico

    graduados = obtener_graduados_filtrados(request.GET)
    legajos = graduados.values_list("legajo_graduado", flat=True)

    filas = (
        GraduadoCarrera.objects
        .filter(legajo_graduado_id__in=legajos)
        .select_related(
            "legajo_graduado",
            "codigo_carrera",
            "codigo_carrera__id_escuela",
        )
        .order_by("legajo_graduado_id", "codigo_carrera_id")
    )

    pagina = request.GET.get("pagina")
    paginator = Paginator(filas, 25)
    filas_pagina = paginator.get_page(pagina)

    analiticos_titulo = set(
        Analitico.objects.filter(
            legajo_graduado_id__in=legajos,
            tipo_documento="titulo",
        ).values_list("legajo_graduado_id", "codigo_carrera_id")
    )

    analiticos_tramite = set(
        Analitico.objects.filter(
            legajo_graduado_id__in=legajos,
            tipo_documento="en_tramite",
        ).values_list("legajo_graduado_id", "codigo_carrera_id")
    )

    # Querystring sin «pagina» para los enlaces de paginado.
    querystring = request.GET.copy()
    querystring.pop("pagina", None)
    filtros_qs = querystring.urlencode()

    # Marcar las filas que tienen analíticos validados.
    for fila in filas_pagina.object_list:
        clave = (fila.legajo_graduado_id, fila.codigo_carrera_id)
        fila.analitico_titulo = clave in analiticos_titulo
        fila.analitico_tramite = clave in analiticos_tramite

    contexto = obtener_contexto_base()
    contexto.update({
        "filas": filas_pagina,
        "page_obj": filas_pagina,
        "paginator": paginator,
        "total_filas": paginator.count,
        "total_graduados": graduados.count(),
        "analiticos_titulo": analiticos_titulo,
        "analiticos_tramite": analiticos_tramite,
        "filtros_qs": filtros_qs,
    })

    return render(
        request,
        "academico/lista_graduados.html",
        contexto,
    )


# ==========================================
# 5. EXPORTACIÓN A EXCEL
# ==========================================

@requiere_sesion
def exportar_graduados(request):
    graduados = obtener_graduados_filtrados(request.GET)

    contenido = generar_excel_graduados(graduados)

    respuesta = HttpResponse(
        contenido,
        content_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    respuesta["Content-Disposition"] = (
        'attachment; filename="graduados.xlsx"'
    )

    return respuesta


# ==========================================
# 6. CARGA DE DATOS POR EXCEL
# ==========================================

@requiere_sesion
def carga_datos(request):

    if request.method == "GET":
        return render(
            request,
            "academico/carga_datos.html"
        )

    archivo = request.FILES.get("archivo_excel")

    if not archivo:
        return JsonResponse(
            {
                "exito": False,
                "mensaje": "No se recibió ningún archivo."
            },
            status=400
        )

    extension = archivo.name.rsplit(".", 1)[-1].lower()

    if "." not in archivo.name or extension not in ["xlsx", "xls"]:
        return JsonResponse(
            {
                "exito": False,
                "mensaje": "El archivo debe tener formato .xlsx o .xls."
            },
            status=400
        )

    try:
        resultado = CargaDatos.cargar_excel(archivo)

        return JsonResponse({
            "exito": True,
            "mensaje": (
                f"Carga completada. "
                f"Filas procesadas: {resultado['filas_procesadas']}. "
                f"Graduados nuevos: {resultado['graduados_nuevos']}. "
                f"Graduados actualizados: "
                f"{resultado['graduados_actualizados']}."
            ),
            "resultado": resultado,
        })

    except ValueError as error:
        return JsonResponse({
            "exito": False,
            "mensaje": str(error),
        }, status=400)
