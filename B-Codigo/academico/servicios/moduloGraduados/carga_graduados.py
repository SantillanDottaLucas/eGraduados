"""
Carga manual de graduados con los datos mínimos.

Separa tres responsabilidades:

1. convertir el formulario en un dict serializable en sesión;
2. detectar conflictos (legajo, DNI o carrera ya cargada) para
   pedir confirmación antes de sobrescribir;
3. guardar en una transacción y registrar la auditoría.

El payload a confirmar viaja en la sesión con un token, no en
campos ocultos del formulario.
"""

import secrets
from datetime import date

from django.db import transaction

from academico.models import Carrera, Graduado, GraduadoCarrera, OrigenPromedio
from academico.servicios.auditoria import registrar_auditoria


CLAVE_PENDIENTE = "carga_graduados_pendiente"


def datos_desde_form(form):
    """
    Convierte el cleaned_data del formulario a un dict de trabajo.

    Las fechas se dejan como objetos ``date``: ``guardar_pendiente``
    se encarga de serializarlas si hay que pedir confirmación.
    """

    datos = form.cleaned_data

    return {
        "legajo": datos["legajo"],
        "dni": datos["dni"],
        "nombre": datos["nombre"],
        "apellido": datos["apellido"],
        "codigo_carrera": datos["codigo_carrera"].codigo_carrera,
        "anio_ingreso_universidad": datos["anio_ingreso_universidad"],
        "fecha_ingreso_carrera": datos["fecha_ingreso_carrera"],
        "fecha_egreso_carrera": datos["fecha_egreso_carrera"],
        "promedio_sin_aplazo": datos["promedio_sin_aplazo"],
    }


def datos_desde_sesion(sesion):
    """Recupera el payload pendiente y lo convierte a tipos de Python."""

    pendiente = sesion.get(CLAVE_PENDIENTE)

    if not isinstance(pendiente, dict) or not pendiente.get("token"):
        return None, None

    datos = dict(pendiente["datos"])

    for campo in ("fecha_ingreso_carrera", "fecha_egreso_carrera"):
        try:
            datos[campo] = date.fromisoformat(datos[campo])
        except (KeyError, TypeError, ValueError):
            return None, None

    try:
        datos["promedio_sin_aplazo"] = float(datos["promedio_sin_aplazo"])
        datos["anio_ingreso_universidad"] = int(
            datos["anio_ingreso_universidad"]
        )
    except (KeyError, TypeError, ValueError):
        return None, None

    return datos, pendiente["token"]


def claves_conflicto(conflictos):
    """Claves estables para comparar conflictos entre dos momentos."""

    return {f"{item['entidad']}|{item['clave']}" for item in conflictos}


def guardar_pendiente(sesion, datos, conflictos):
    """Guarda el payload en sesión y devuelve su token."""

    serializados = dict(datos)

    for campo in ("fecha_ingreso_carrera", "fecha_egreso_carrera"):
        serializados[campo] = serializados[campo].isoformat()

    token = secrets.token_urlsafe(16)
    sesion[CLAVE_PENDIENTE] = {
        "token": token,
        "datos": serializados,
        "claves": sorted(claves_conflicto(conflictos)),
    }
    sesion.modified = True

    return token


def claves_pendientes(sesion):
    """Devuelve el conjunto de claves que el usuario ya confirmó."""

    pendiente = sesion.get(CLAVE_PENDIENTE) or {}

    return set(pendiente.get("claves") or [])


def limpiar_pendiente(sesion):
    sesion.pop(CLAVE_PENDIENTE, None)
    sesion.modified = True


def _descripcion_persona(graduado):
    return (
        f"{graduado.apellido}, {graduado.nombre} · DNI {graduado.dni} · "
        f"ingreso UARG {graduado.anio_ingreso_universidad}"
    )


def detectar_conflictos(datos):
    """
    Devuelve la lista de datos que se sobrescribirían.

    Cada ítem tiene ``entidad``, ``clave``, ``actual`` y ``nuevo``
    ya formateados para mostrar en la pantalla de confirmación.
    """

    conflictos = []
    legajo = datos["legajo"]

    nuevo = _descripcion_persona_simple(datos)

    por_legajo = Graduado.objects.filter(
        legajo_graduado=legajo
    ).first()

    if por_legajo is not None:
        conflictos.append({
            "entidad": "Datos personales del legajo",
            "clave": legajo,
            "actual": _descripcion_persona(por_legajo),
            "nuevo": nuevo,
        })

    por_dni = Graduado.objects.filter(
        dni=datos["dni"]
    ).exclude(legajo_graduado=legajo).first()

    if por_dni is not None:
        conflictos.append({
            "entidad": "DNI ya registrado en otro legajo",
            "clave": datos["dni"],
            "actual": (
                f"{por_dni.legajo_graduado} · "
                f"{_descripcion_persona(por_dni)}"
            ),
            "nuevo": f"{legajo} · {nuevo}",
        })

    relacion = GraduadoCarrera.objects.filter(
        legajo_graduado_id=legajo,
        codigo_carrera_id=datos["codigo_carrera"],
    ).first()

    if relacion is not None:
        conflictos.append({
            "entidad": "Datos de la carrera",
            "clave": datos["codigo_carrera"],
            "actual": (
                f"Ingreso {relacion.fecha_ingreso_carrera.isoformat()} · "
                f"Egreso {relacion.fecha_egreso_carrera.isoformat()} · "
                f"Promedio sin aplazo {relacion.promedio_sin_aplazo}"
            ),
            "nuevo": (
                f"Ingreso {datos['fecha_ingreso_carrera'].isoformat()} · "
                f"Egreso {datos['fecha_egreso_carrera'].isoformat()} · "
                f"Promedio sin aplazo {datos['promedio_sin_aplazo']}"
            ),
        })

    return conflictos


def _descripcion_persona_simple(datos):
    return (
        f"{datos['apellido']}, {datos['nombre']} · DNI {datos['dni']} · "
        f"ingreso UARG {datos['anio_ingreso_universidad']}"
    )


@transaction.atomic
def guardar(datos, usuario=None, sobrescribiendo=False):
    """
    Crea o actualiza al graduado y su relación con la carrera.

    El promedio con aplazo no se informa en esta pantalla: se
    conserva el valor que ya estuviera cargado.
    """

    carrera = Carrera.objects.get(
        codigo_carrera=datos["codigo_carrera"]
    )

    graduado, _ = Graduado.objects.update_or_create(
        legajo_graduado=datos["legajo"],
        defaults={
            "dni": datos["dni"],
            "nombre": datos["nombre"],
            "apellido": datos["apellido"],
            "anio_ingreso_universidad": (
                datos["anio_ingreso_universidad"]
            ),
        },
    )

    relacion, _ = GraduadoCarrera.objects.update_or_create(
        legajo_graduado=graduado,
        codigo_carrera=carrera,
        defaults={
            "fecha_ingreso_carrera": datos["fecha_ingreso_carrera"],
            "fecha_egreso_carrera": datos["fecha_egreso_carrera"],
            "promedio_sin_aplazo": datos["promedio_sin_aplazo"],
            "origen_promedio_sin_aplazo": OrigenPromedio.MANUAL,
        },
    )

    registrar_auditoria(
        usuario,
        "graduado_cargado_manualmente",
        entidad="Graduado",
        entidad_id=graduado.legajo_graduado,
        detalle={
            "codigo_carrera": carrera.codigo_carrera,
            "anio_ingreso_universidad": (
                graduado.anio_ingreso_universidad
            ),
            "promedio_sin_aplazo": datos["promedio_sin_aplazo"],
            "sobrescribiendo": sobrescribiendo,
        },
    )

    return graduado, relacion
