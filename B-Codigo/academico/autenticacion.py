"""
Autenticación por sesión basada en el modelo Usuario de la app.

El ingreso se realiza con un email (que debe existir en la base de
datos) y un código alfanumérico de 6 caracteres que se almacena
hasheado mediante make_password / check_password.
"""

import functools
import re
import secrets
import string
from urllib.parse import urlencode

from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Usuario


# Clave con la que se guarda el id del usuario en la sesión.
CLAVE_SESION = "usuario_id"

# El código de acceso tiene exactamente 6 caracteres alfanuméricos.
PATRON_CODIGO = re.compile(r"[A-Za-z0-9]{6}")
LONGITUD_CODIGO = 6


def generar_codigo_acceso():
    """Genera un código alfanumérico aleatorio de 6 caracteres."""

    alfabeto = string.ascii_letters + string.digits

    return "".join(
        secrets.choice(alfabeto) for _ in range(LONGITUD_CODIGO)
    )


def codigo_valido(codigo):
    """Comprueba el formato del código de acceso."""

    return bool(PATRON_CODIGO.fullmatch(codigo or ""))


def obtener_usuario_sesion(request):
    """Devuelve el usuario logueado o None si no hay sesión."""

    usuario_id = request.session.get(CLAVE_SESION)

    if usuario_id is None:
        return None

    return (
        Usuario.objects
        .filter(id_usuario=usuario_id)
        .select_related("id_rol")
        .first()
    )


def url_siguiente_segura(request, siguiente):
    """
    Devuelve la URL de redirección sólo si es interna y segura.
    """

    if not siguiente:
        return None

    if url_has_allowed_host_and_scheme(
        siguiente,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return siguiente

    return None


def redirigir_login(request):
    """Redirige al login preservando la URL actual."""

    url_login = reverse("login")
    siguiente = request.get_full_path()

    if url_siguiente_segura(request, siguiente):
        return redirect(
            f"{url_login}?{urlencode({'next': siguiente})}"
        )

    return redirect(url_login)


def requiere_sesion(vista):
    """
    Decorador de vistas: permite el acceso sólo a usuarios
    logueados; si no, redirige al login con ?next=.
    """

    @functools.wraps(vista)
    def envoltura(request, *args, **kwargs):
        usuario = obtener_usuario_sesion(request)

        if usuario is None:
            return redirigir_login(request)

        request.usuario_actual = usuario
        return vista(request, *args, **kwargs)

    return envoltura


def requiere_administrador(vista):
    """
    Decorador de vistas: permite el acceso sólo a usuarios
    cuyo rol tenga permisos de administración.
    """

    @functools.wraps(vista)
    def envoltura(request, *args, **kwargs):
        usuario = obtener_usuario_sesion(request)

        if usuario is None:
            return redirigir_login(request)

        request.usuario_actual = usuario

        if not usuario.id_rol.puede_administrar:
            return render(
                request,
                "academico/acceso_denegado.html",
                status=403,
            )

        return vista(request, *args, **kwargs)

    return envoltura
