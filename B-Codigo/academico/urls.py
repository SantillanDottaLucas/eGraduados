from django.urls import path
from . import views

urlpatterns = [
    # Página principal
    path("", views.index, name="index"),

    # Estadísticas
    path("estadisticas/", views.estadisticas, name="estadisticas"),
    path(
        "estadisticas/promedios/",
        views.estadisticas_promedios,
        name="estadisticas_promedios",
    ),
    path(
        "estadisticas/totales/",
        views.estadisticas_totales,
        name="estadisticas_totales",
    ),
    path(
        "estadisticas/tiempos/",
        views.estadisticas_tiempos,
        name="estadisticas_tiempos",
    ),

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