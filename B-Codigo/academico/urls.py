from django.urls import path
from . import views
from . import views_abm
from . import views_gestion
from django.urls import path, re_path

urlpatterns = [
    # Ingreso y salida
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),

    # Página principal
    path("", views.index, name="index"),

    # Estadísticas
    path("estadisticas/", views.estadisticas, name="estadisticas"),

    # Graduados
    path(
        "lista_graduados/",
        views.lista_graduados,
        name="lista_graduados",
    ),
    path(
        "descargar_graduados/",
        views.exportar_graduados,
        name="exportar_graduados",
    ),    
    re_path(
        r'^graduados/(?P<legajo>.+)/(?P<carrera>[^/]+)/editar/$',
        views_gestion.editar_graduado,
        name='editar_graduado'
    ),

    # Gestión académica (escuelas, carreras, planes y materias)
    path(
        "gestion/",
        views_gestion.gestion_academica,
        name="gestion_academica",
    ),

    # ABM de usuarios y roles (solo administradores)
    path(
        "usuarios/",
        views_abm.abm_usuarios,
        name="abm_usuarios",
    ),
    path(
        "roles/",
        views_abm.abm_roles,
        name="abm_roles",
    ),

    # Analíticos y títulos
    path(
        "generacion_analiticos/",
        views.generacion_analiticos,
        name="generacion_analiticos",
    ),
    path(
        "titulo_en_tramite/",
        views.titulo_en_tramite,
        name="titulo_en_tramite",
    ),
    path(
        "carga_datos/",
        views.carga_datos,
        name="carga_datos"
    ),

]
