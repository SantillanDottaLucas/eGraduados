"""
Vistas del ABM de usuarios y roles.

Acceso exclusivo para roles con permisos de administración.
"""

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.db.models import Count, Q
from django.shortcuts import redirect, render

from .autenticacion import (
    generar_codigo_acceso,
    requiere_administrador,
)
from .forms import RolForm, UsuarioForm
from .models import Rol, Usuario


# Roles base del sistema: no se pueden eliminar.
ROLES_BASE = ("Administrador", "Titulos")

# Clave de sesión para mostrar un código una única vez.
CLAVE_CODIGO_TEMPORAL = "codigo_temporal"


# ==================================================
# CÓDIGO TEMPORAL (SE MUESTRA UNA SOLA VEZ)
# ==================================================

def _guardar_codigo_temporal(request, usuario, codigo):
    request.session[CLAVE_CODIGO_TEMPORAL] = {
        "usuario": str(usuario),
        "codigo": codigo,
    }


def _obtener_codigo_temporal(request):
    return request.session.pop(CLAVE_CODIGO_TEMPORAL, None)


def _buscar_usuario_por_id(valor):
    """Devuelve un Usuario a partir de su id o None."""

    if valor is None or not str(valor).isdigit():
        return None

    return Usuario.objects.filter(
        id_usuario=int(valor)
    ).first()


# ==================================================
# ABM DE USUARIOS
# ==================================================

@requiere_administrador
def abm_usuarios(request):
    """
    Listado, alta, edición, eliminación y regeneración del
    código de acceso de los usuarios del sistema.
    """

    # ==========================================
    # 1. FILTROS DEL LISTADO
    # ==========================================

    busqueda = (request.GET.get("q") or "").strip()
    rol_filtro = request.GET.get("rol") or ""

    usuarios = (
        Usuario.objects
        .select_related("id_rol")
        .order_by("nombre_usuario")
    )

    if busqueda:
        usuarios = usuarios.filter(
            Q(nombre_usuario__icontains=busqueda)
            | Q(email__icontains=busqueda)
        )

    if rol_filtro.isdigit():
        usuarios = usuarios.filter(id_rol_id=int(rol_filtro))

    # Código generado o regenerado, mostrado una sola vez.
    codigo_temporal = _obtener_codigo_temporal(request)

    # ==========================================
    # 2. FORMULARIO (EN BLANCO O PARA EDITAR)
    # ==========================================

    form = UsuarioForm()
    usuario_editar = _buscar_usuario_por_id(
        request.GET.get("editar")
    )

    if usuario_editar is not None:
        form = UsuarioForm(instance=usuario_editar)

    # ==========================================
    # 3. ACCIONES POR POST
    # ==========================================

    if request.method == "POST":
        accion = request.POST.get("accion", "guardar")

        # ELIMINAR UN USUARIO
        if accion == "eliminar":
            objetivo = _buscar_usuario_por_id(
                request.POST.get("id_usuario")
            )

            if objetivo is None:
                messages.error(
                    request,
                    "El usuario indicado no existe.",
                )

            elif (
                objetivo.id_usuario
                == request.usuario_actual.id_usuario
            ):
                messages.error(
                    request,
                    "No podés eliminar tu propio usuario.",
                )

            else:
                nombre = str(objetivo)
                objetivo.delete()
                messages.success(
                    request,
                    f"Usuario {nombre} eliminado.",
                )

            return redirect("abm_usuarios")

        # REGENERAR EL CÓDIGO DE ACCESO
        elif accion == "regenerar":
            objetivo = _buscar_usuario_por_id(
                request.POST.get("id_usuario")
            )

            if objetivo is None:
                messages.error(
                    request,
                    "El usuario indicado no existe.",
                )

            else:
                codigo = generar_codigo_acceso()
                objetivo.codigo_acceso = make_password(codigo)
                objetivo.save(update_fields=["codigo_acceso"])

                _guardar_codigo_temporal(
                    request,
                    objetivo,
                    codigo,
                )

                messages.success(
                    request,
                    f"Se generó un nuevo código para {objetivo}.",
                )

            return redirect("abm_usuarios")

        # GUARDAR (CREAR O EDITAR)
        else:
            instancia = _buscar_usuario_por_id(
                request.POST.get("id_usuario")
            )

            form = UsuarioForm(request.POST, instance=instancia)

            if form.is_valid():
                usuario = form.save(commit=False)

                if instancia is None:
                    # Nuevo usuario: se genera su primer código.
                    codigo = generar_codigo_acceso()
                    usuario.codigo_acceso = make_password(codigo)
                    usuario.save()

                    _guardar_codigo_temporal(
                        request,
                        usuario,
                        codigo,
                    )

                    messages.success(
                        request,
                        f"Usuario {usuario} creado.",
                    )

                else:
                    usuario.save()
                    messages.success(
                        request,
                        f"Usuario {usuario} actualizado.",
                    )

                return redirect("abm_usuarios")

    # ==========================================
    # 4. RENDERIZAR
    # ==========================================

    contexto = {
        "usuarios": usuarios,
        "form": form,
        "usuario_editar": usuario_editar,
        "roles": Rol.objects.order_by("nombre_rol"),
        "busqueda": busqueda,
        "rol_filtro": rol_filtro,
        "codigo_temporal": codigo_temporal,
    }

    return render(
        request,
        "academico/abm_usuarios.html",
        contexto,
    )


# ==================================================
# ABM DE ROLES
# ==================================================

@requiere_administrador
def abm_roles(request):
    """
    Listado, alta, edición y eliminación de los roles
    del sistema.
    """

    roles = (
        Rol.objects
        .annotate(cantidad_usuarios=Count("usuarios"))
        .order_by("nombre_rol")
    )

    form = RolForm()
    rol_editar = None

    id_editar = request.GET.get("editar")

    if id_editar and id_editar.isdigit():
        rol_editar = Rol.objects.filter(
            id_rol=int(id_editar)
        ).first()

        if rol_editar is not None:
            form = RolForm(instance=rol_editar)

    if request.method == "POST":
        accion = request.POST.get("accion", "guardar")

        # ELIMINAR UN ROL
        if accion == "eliminar":
            id_rol = request.POST.get("id_rol") or ""
            rol = None

            if id_rol.isdigit():
                rol = Rol.objects.filter(
                    id_rol=int(id_rol)
                ).first()

            if rol is None:
                messages.error(
                    request,
                    "El rol indicado no existe.",
                )

            elif rol.usuarios.exists():
                messages.error(
                    request,
                    (
                        "No se puede eliminar un rol que tiene "
                        "usuarios asociados."
                    ),
                )

            elif rol.nombre_rol in ROLES_BASE:
                messages.error(
                    request,
                    (
                        "No se pueden eliminar los roles base "
                        "del sistema."
                    ),
                )

            else:
                nombre = rol.nombre_rol
                rol.delete()
                messages.success(
                    request,
                    f"Rol {nombre} eliminado.",
                )

            return redirect("abm_roles")

        # GUARDAR (CREAR O EDITAR)
        else:
            instancia = rol_editar
            id_rol = request.POST.get("id_rol") or ""

            if id_rol.isdigit():
                rol_bd = Rol.objects.filter(
                    id_rol=int(id_rol)
                ).first()

                if rol_bd is not None:
                    instancia = rol_bd

            form = RolForm(request.POST, instance=instancia)

            if form.is_valid():
                rol = form.save()

                messages.success(
                    request,
                    f"Rol {rol.nombre_rol} guardado.",
                )

                return redirect("abm_roles")

    contexto = {
        "roles": roles,
        "form": form,
        "rol_editar": rol_editar,
        "roles_base": ROLES_BASE,
    }

    return render(
        request,
        "academico/abm_roles.html",
        contexto,
    )
