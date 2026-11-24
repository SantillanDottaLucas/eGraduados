"""
Procesadores de contexto compartidos por todas las plantillas.

Además del usuario logueado, expone el mapa de módulos del navbar,
el módulo activo y las migas de pan. Así la navegación se define en
un único lugar y respeta los permisos del rol sin tocar cada vista.
"""

from django.urls import NoReverseMatch, reverse

from .autenticacion import obtener_usuario_sesion


# ==================================================
# MAPA DE MÓDULOS
# ==================================================

MODULOS = (
    {
        "clave": "inicio",
        "etiqueta": "Panel principal",
        "descripcion": "Resumen general del sistema",
        "grupo": "Inicio",
        "url_name": "index",
        "icono": "bi-house-door",
        "admin": False,
    },
    {
        "clave": "generacion_analiticos",
        "etiqueta": "Generar analítico",
        "descripcion": "Cargá los datos y generá el analítico",
        "grupo": "Documentación",
        "url_name": "generacion_analiticos",
        "icono": "bi-file-earmark-text",
        "admin": False,
    },
    {
        "clave": "titulo_en_tramite",
        "etiqueta": "Título en trámite",
        "descripcion": "Certificado de título en trámite",
        "grupo": "Documentación",
        "url_name": "titulo_en_tramite",
        "icono": "bi-patch-check",
        "admin": False,
    },
    {
        "clave": "lista_graduados",
        "etiqueta": "Listado de graduados",
        "descripcion": "Buscá y consultá graduados",
        "grupo": "Consultas",
        "url_name": "lista_graduados",
        "icono": "bi-people",
        "admin": False,
    },
    {
        "clave": "estadisticas",
        "etiqueta": "Estadísticas",
        "descripcion": "Promedios, egresos y tiempos",
        "grupo": "Consultas",
        "url_name": "estadisticas",
        "icono": "bi-bar-chart-line",
        "admin": False,
    },
    {
        "clave": "carga_datos",
        "etiqueta": "Carga de datos",
        "descripcion": "Importá información desde Excel",
        "grupo": "Datos",
        "url_name": "carga_datos",
        "icono": "bi-cloud-arrow-up",
        "admin": False,
    },
    {
        "clave": "carga_graduados",
        "etiqueta": "Carga de graduados",
        "descripcion": "Alta manual con datos mínimos",
        "grupo": "Datos",
        "url_name": "carga_graduados",
        "icono": "bi-person-plus",
        "admin": False,
    },
    {
        "clave": "gestion_academica",
        "etiqueta": "Gestión académica",
        "descripcion": "Escuelas, carreras, planes y materias",
        "grupo": "Gestión",
        "url_name": "gestion_academica",
        "icono": "bi-diagram-3",
        "admin": False,
    },
    {
        "clave": "abm_usuarios",
        "etiqueta": "Usuarios",
        "descripcion": "Altas, bajas y códigos de acceso",
        "grupo": "Administración",
        "url_name": "abm_usuarios",
        "icono": "bi-person-gear",
        "admin": True,
    },
    {
        "clave": "abm_roles",
        "etiqueta": "Roles y permisos",
        "descripcion": "Definí los roles del sistema",
        "grupo": "Administración",
        "url_name": "abm_roles",
        "icono": "bi-shield-lock",
        "admin": True,
    },
)

GRUPOS = (
    "Inicio",
    "Documentación",
    "Consultas",
    "Datos",
    "Gestión",
    "Administración",
)

# Vistas auxiliares que pertenecen a otro módulo (detalle, exportación, etc.).
ALIASES_URL = {
    "exportar_graduados": "lista_graduados",
    "editar_graduado": "lista_graduados",
}


def _url_de(url_name):
    """Devuelve la URL reversa o '#' si la vista no existe."""

    try:
        return reverse(url_name)
    except NoReverseMatch:
        return "#"


def _preparar_modulo(modulo, activo=False):
    item = dict(modulo)
    item["url"] = _url_de(modulo["url_name"])
    item["activo"] = activo
    return item


def usuario_actual(request):
    """
    Agrega el usuario logueado y la navegación al contexto de todas
    las plantillas que extienden base.html.
    """

    usuario = getattr(request, "usuario_actual", None)

    if usuario is None:
        usuario = obtener_usuario_sesion(request)

    puede_administrar = bool(
        getattr(
            getattr(usuario, "id_rol", None),
            "puede_administrar",
            False,
        )
    )

    resolver = getattr(request, "resolver_match", None)
    url_name = getattr(resolver, "url_name", None) or ""
    clave_activa = ALIASES_URL.get(url_name, url_name)

    modulo_activo = None
    for modulo in MODULOS:
        if modulo["clave"] == clave_activa:
            modulo_activo = _preparar_modulo(modulo, activo=True)
            break

    menu_modulos = []
    for grupo in GRUPOS:
        items = [
            _preparar_modulo(
                modulo,
                activo=bool(
                    modulo_activo
                    and modulo["clave"] == modulo_activo["clave"]
                ),
            )
            for modulo in MODULOS
            if modulo["grupo"] == grupo
            and (not modulo["admin"] or puede_administrar)
        ]
        if items:
            menu_modulos.append({"nombre": grupo, "items": items})

    migas = []
    if modulo_activo and modulo_activo["clave"] != "inicio":
        migas.append(
            {
                "etiqueta": "Inicio",
                "url": _url_de("index"),
            }
        )
        migas.append(
            {
                "etiqueta": modulo_activo["etiqueta"],
                "url": modulo_activo["url"],
            }
        )
    elif not modulo_activo and url_name not in ("login", ""):
        migas.append(
            {
                "etiqueta": "Inicio",
                "url": _url_de("index"),
            }
        )

    submodulo = None
    if modulo_activo and modulo_activo["clave"] == "gestion_academica":
        submodulo = request.GET.get("entidad") or None

    return {
        "usuario_actual": usuario,
        "menu_modulos": menu_modulos,
        "modulo_activo": modulo_activo,
        "submodulo_activo": submodulo,
        "ruta_migas": migas,
    }
