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
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
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

    usuario = (
        Usuario.objects
        .filter(id_usuario=usuario_id)
        .select_related("id_rol")
        .first()
    )

    # Un usuario desactivado pierde la sesión de inmediato.
    if usuario is None or not usuario.activo:
        request.session.pop(CLAVE_SESION, None)
        return None

    return usuario


def iniciar_sesion(request, usuario):
    """
    Inicia la sesión rotando la clave (evita fijación de sesión) y
    fija la expiración por inactividad.
    """

    request.session.cycle_key()
    request.session[CLAVE_SESION] = usuario.id_usuario
    request.session.set_expiry(settings.SESSION_COOKIE_AGE)
    request.session.modified = True


def cerrar_sesion(request):
    request.session.flush()


# ==================================================
# LÍMITE DE INTENTOS
# ==================================================

def usuario_bloqueado(usuario, ahora=None):
    """True si el usuario está bloqueado por intentos fallidos."""

    if usuario is None or usuario.bloqueado_hasta is None:
        return False

    ahora = ahora or timezone.now()

    return usuario.bloqueado_hasta > ahora


def segundos_restantes_bloqueo(usuario, ahora=None):
    if not usuario_bloqueado(usuario, ahora):
        return 0

    ahora = ahora or timezone.now()

    return max(0, int((usuario.bloqueado_hasta - ahora).total_seconds()))


def registrar_intento_fallido(usuario):
    """
    Suma un intento fallido y bloquea la cuenta al llegar al máximo.
    """

    if usuario is None:
        return

    usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1

    if usuario.intentos_fallidos >= settings.LOGIN_MAX_INTENTOS:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = timezone.now() + timedelta(
            seconds=settings.LOGIN_BLOQUEO_SEGUNDOS,
        )

    usuario.save(
        update_fields=["intentos_fallidos", "bloqueado_hasta"],
    )


def limpiar_intentos(usuario):
    if usuario is None:
        return

    if not usuario.intentos_fallidos and usuario.bloqueado_hasta is None:
        return

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.save(
        update_fields=["intentos_fallidos", "bloqueado_hasta"],
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


def requiere_rol(*nombres_rol):
    """
    Decorador de vistas: permite el acceso sólo a los roles
    indicados (comparación sin distinguir mayúsculas).
    """

    permitidos = {nombre.strip().lower() for nombre in nombres_rol}

    def decorador(vista):
        @functools.wraps(vista)
        def envoltura(request, *args, **kwargs):
            usuario = obtener_usuario_sesion(request)

            if usuario is None:
                return redirigir_login(request)

            request.usuario_actual = usuario

            rol = (usuario.id_rol.nombre_rol or "").strip().lower()

            if rol not in permitidos and not usuario.id_rol.puede_administrar:
                return render(
                    request,
                    "academico/acceso_denegado.html",
                    status=403,
                )

            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
