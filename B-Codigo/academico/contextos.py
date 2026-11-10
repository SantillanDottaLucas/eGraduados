"""
Procesadores de contexto compartidos por todas las plantillas.
"""

from .autenticacion import obtener_usuario_sesion


def usuario_actual(request):
    """
    Agrega el usuario logueado (o None) al contexto de
    todas las plantillas que extienden base.html.
    """

    return {
        "usuario_actual": obtener_usuario_sesion(request)
    }
