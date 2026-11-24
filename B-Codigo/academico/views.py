from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .autenticacion import (
    cerrar_sesion,
    codigo_valido,
    iniciar_sesion,
    limpiar_intentos,
    obtener_usuario_sesion,
    registrar_intento_fallido,
    requiere_administrador,
    requiere_sesion,
    segundos_restantes_bloqueo,
    url_siguiente_segura,
    usuario_bloqueado,
)
from .models import (
    Analitico,
    Carrera,
    Escuela,
    Graduado,
    GraduadoCarrera,
    Usuario,
)
from .servicios.archivos import validar_archivo
from .servicios.auditoria import registrar_auditoria

from academico.servicios.moduloCarga.carga_datos import CargaDatos

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
    ORDENES_BUSQUEDA,
    SITUACIONES_BUSQUEDA,
    obtener_filas_busqueda,
    obtener_filas_filtradas,
)

from .servicios.moduloGraduados.eliminacion import (
    CONFIRMACION_BORRADO,
    eliminar_carrera,
    eliminar_graduado as eliminar_graduado_servicio,
    resumen_impacto,
)

from .servicios.moduloGraduados.exportar_graduados import (
    generar_excel_filas,
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

    Tras varios intentos fallidos la cuenta se bloquea por un
    período configurable (LOGIN_BLOQUEO_SEGUNDOS).
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

            if usuario is not None and usuario_bloqueado(usuario):
                restantes = segundos_restantes_bloqueo(usuario)
                minutos = max(1, (restantes + 59) // 60)

                error = (
                    "La cuenta está bloqueada por intentos fallidos. "
                    f"Probá de nuevo en {minutos} minuto(s)."
                )

            elif usuario is None or not usuario.activo:
                # Mensaje genérico: no revela si el email existe.
                error = "El email o el código son incorrectos."

            elif not check_password(codigo, usuario.codigo_acceso):
                registrar_intento_fallido(usuario)

                if usuario_bloqueado(usuario):
                    error = (
                        "Demasiados intentos fallidos. La cuenta quedó "
                        "bloqueada temporalmente."
                    )
                else:
                    error = "El email o el código son incorrectos."

            else:
                limpiar_intentos(usuario)
                iniciar_sesion(request, usuario)
                registrar_auditoria(
                    usuario,
                    "login",
                    entidad="Usuario",
                    entidad_id=usuario.id_usuario,
                    detalle={
                        "email": usuario.email,
                        "fecha": timezone.now().isoformat(),
                    },
                )

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
        usuario = obtener_usuario_sesion(request)

        if usuario is not None:
            registrar_auditoria(
                usuario,
                "logout",
                entidad="Usuario",
                entidad_id=usuario.id_usuario,
            )

        cerrar_sesion(request)

    return redirect("login")


# ==========================================
# 1. PÁGINAS PRINCIPALES
# ==========================================

@requiere_sesion
def index(request):
    """Panel principal con indicadores rápidos del sistema."""

    anio_actual = date.today().year

    contexto = {
        "anio_actual": anio_actual,
        "total_graduados": Graduado.objects.count(),
        "total_analiticos": Analitico.objects.count(),
        "total_carreras": Carrera.objects.count(),
        "egresos_anio": GraduadoCarrera.objects.filter(
            fecha_egreso_carrera__year=anio_actual
        ).count(),
    }

    return render(request, "academico/index.html", contexto)


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

    filas = obtener_filas_busqueda(request.GET)
    legajos = {fila.legajo_graduado_id for fila in filas}

    situacion = (request.GET.get("situacion") or "todas").strip()
    if situacion not in SITUACIONES_BUSQUEDA:
        situacion = "todas"

    orden = (request.GET.get("orden") or "inconsistencias").strip()
    if orden not in ORDENES_BUSQUEDA:
        orden = "inconsistencias"

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

    legajos_con_analiticos = set(
        Analitico.objects.filter(
            legajo_graduado_id__in=legajos,
        ).values_list("legajo_graduado_id", flat=True)
    )

    # Querystring sin «pagina» para los enlaces de paginado.
    querystring = request.GET.copy()
    querystring.pop("pagina", None)
    filtros_qs = querystring.urlencode()

    # El Excel conserva sus filtros históricos: «situacion» y «orden»
    # son controles exclusivos del buscador y no se le pasan.
    excel_parametros = {}
    for clave in (
        "nombre",
        "legajo",
        "escuela",
        "carrera",
        "fecha_desde",
        "fecha_hasta",
    ):
        valor = (request.GET.get(clave) or "").strip()
        if valor:
            excel_parametros[clave] = valor

    excel_qs = urlencode(excel_parametros)

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
        "total_filas": len(filas),
        "total_graduados": len(legajos),
        "analiticos_titulo": analiticos_titulo,
        "analiticos_tramite": analiticos_tramite,
        "legajos_con_analiticos": legajos_con_analiticos,
        "filtros_qs": filtros_qs,
        "excel_qs": excel_qs,
        "situacion": situacion,
        "orden": orden,
    })

    return render(
        request,
        "academico/lista_graduados.html",
        contexto,
    )


# ==========================================
# 4.b BORRADO DE GRADUADOS (SOLO ADMIN)
# ==========================================

@require_POST
@requiere_administrador
def eliminar_graduado(request, legajo):
    """
    Elimina una fila de carrera o un graduado completo.

    Conserva los filtros del buscador en el redirect y exige doble
    confirmación cuando hay analíticos validados de por medio.
    """

    accion = request.POST.get("accion", "")
    carrera = (request.POST.get("carrera") or "").strip()
    confirmacion = (request.POST.get("confirmacion") or "").strip()
    filtros_qs = (request.POST.get("filtros_qs") or "").strip()

    destino = reverse("lista_graduados")
    if filtros_qs:
        destino = f"{destino}?{filtros_qs}"

    try:
        if accion == "carrera":
            if not carrera:
                raise ValueError("No se indicó la carrera a quitar.")

            impacto = resumen_impacto(legajo, carrera)

            if (
                impacto["analiticos"]
                and confirmacion != CONFIRMACION_BORRADO
            ):
                raise ValueError(
                    "Esa carrera tiene analíticos validados. "
                    "Confirmá escribiendo ELIMINAR para borrarlos también."
                )

            resultado = eliminar_carrera(
                legajo,
                carrera,
                usuario=request.usuario_actual,
                confirmacion=confirmacion,
            )

            messages.success(
                request,
                (
                    f"Se quitó la carrera {carrera} del legajo {legajo}. "
                    f"Se borraron {resultado['examenes']} examen(es) y "
                    f"{resultado['analiticos']} analítico(s)."
                ),
            )

            if resultado["quedan_carreras"] == 0:
                messages.warning(
                    request,
                    (
                        f"El legajo {legajo} ya no tiene carreras "
                        "asociadas. Podés eliminarlo por completo "
                        "desde el buscador."
                    ),
                )

        elif accion == "graduado":
            impacto = resumen_impacto(legajo)

            if (
                impacto["analiticos"]
                and confirmacion != CONFIRMACION_BORRADO
            ):
                raise ValueError(
                    "El graduado tiene analíticos validados. "
                    "Confirmá escribiendo ELIMINAR para borrarlos también."
                )

            eliminar_graduado_servicio(
                legajo,
                usuario=request.usuario_actual,
                confirmacion=confirmacion,
            )

            messages.success(
                request,
                (
                    f"Se eliminó el graduado {legajo} y toda su "
                    "información asociada."
                ),
            )

        else:
            raise ValueError("Acción de borrado desconocida.")

    except (Graduado.DoesNotExist, GraduadoCarrera.DoesNotExist):
        messages.error(
            request,
            "El graduado o la carrera indicados ya no existen.",
        )

    except ValueError as error:
        messages.error(request, str(error))

    return redirect(destino)


# ==========================================
# 5. EXPORTACIÓN A EXCEL
# ==========================================

@requiere_sesion
def exportar_graduados(request):
    filas = obtener_filas_filtradas(request.GET)

    contenido = generar_excel_filas(filas)

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

    error = validar_archivo(archivo, ["xlsx", "xls"])

    if error:
        return JsonResponse(
            {
                "exito": False,
                "mensaje": error,
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
