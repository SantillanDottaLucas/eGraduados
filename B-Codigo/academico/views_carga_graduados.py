"""
Vista de carga manual de graduados (datos mínimos).

El alta directa no pisa información existente sin confirmación:
si el legajo, el DNI o la relación con la carrera ya están
cargados, se muestra qué se sobrescribiría y se pide confirmar.
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from .autenticacion import requiere_sesion
from .forms import CargaGraduadoForm
from .servicios.moduloGraduados.carga_graduados import (
    claves_conflicto,
    claves_pendientes,
    datos_desde_form,
    datos_desde_sesion,
    detectar_conflictos,
    guardar,
    guardar_pendiente,
    limpiar_pendiente,
)


def _confirmar(request, datos, conflictos, token):
    return render(
        request,
        "academico/confirmacion_carga_graduado.html",
        {
            "datos": datos,
            "conflictos": conflictos,
            "token": token,
        },
    )


@requiere_sesion
def carga_graduados(request):
    url = reverse("carga_graduados")

    if request.method != "POST":
        limpiar_pendiente(request.session)

        return render(
            request,
            "academico/carga_graduados.html",
            {"form": CargaGraduadoForm()},
        )

    accion = request.POST.get("accion", "guardar")

    if accion == "cancelar":
        limpiar_pendiente(request.session)
        messages.info(request, "La carga se canceló; no se guardaron cambios.")

        return redirect(url)

    if accion == "confirmar":
        datos, token = datos_desde_sesion(request.session)

        if datos is None or token != request.POST.get("token", ""):
            limpiar_pendiente(request.session)
            messages.error(
                request,
                "La confirmación venció. Volvé a cargar los datos.",
            )

            return redirect(url)

        # Revalidar contra la BD y contra el formulario: los datos
        # viajan en sesión, pero igual pueden quedar desactualizados.
        form = CargaGraduadoForm(datos)

        if not form.is_valid():
            limpiar_pendiente(request.session)
            messages.error(
                request,
                "Los datos ya no son válidos. Volvé a cargarlos.",
            )

            return redirect(url)

        conflictos = detectar_conflictos(datos)
        claves_actuales = claves_conflicto(conflictos)

        # Si apareció un conflicto nuevo durante la confirmación,
        # se vuelve a pedir autorización en vez de sobrescribirlo.
        if claves_actuales - claves_pendientes(request.session):
            nuevo_token = guardar_pendiente(
                request.session, datos, conflictos
            )

            return _confirmar(request, datos, conflictos, nuevo_token)

        guardar(
            datos,
            usuario=getattr(request, "usuario_actual", None),
            sobrescribiendo=bool(conflictos),
        )
        limpiar_pendiente(request.session)
        messages.success(
            request,
            f"Graduado {datos['apellido']}, {datos['nombre']} guardado "
            "correctamente.",
        )

        return redirect(url)

    form = CargaGraduadoForm(request.POST)

    if not form.is_valid():
        return render(
            request,
            "academico/carga_graduados.html",
            {"form": form},
        )

    datos = datos_desde_form(form)
    conflictos = detectar_conflictos(datos)

    if conflictos:
        token = guardar_pendiente(request.session, datos, conflictos)

        return _confirmar(request, datos, conflictos, token)

    guardar(
        datos,
        usuario=getattr(request, "usuario_actual", None),
    )
    messages.success(
        request,
        f"Graduado {datos['apellido']}, {datos['nombre']} guardado "
        "correctamente.",
    )

    return redirect(url)
