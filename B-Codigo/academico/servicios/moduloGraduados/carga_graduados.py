"""
Carga manual de graduados con los datos mínimos.

Separa tres responsabilidades:

1. convertir el formulario en un dict serializable en sesión;
2. detectar conflictos (DNI o carrera ya cargada) para pedir
   confirmación antes de sobrescribir;
3. guardar en una transacción y registrar la auditoría.

El DNI es la clave del graduado. El legajo es un dato derivado,
calculado a partir del DNI y del año de ingreso a la UARG, y nunca
se ingresa: en el payload viaja sólo para mostrarlo en la
confirmación.

El payload a confirmar viaja en la sesión con un token, no en
campos ocultos del formulario.
"""

import secrets
from datetime import date

from django.db import transaction

from academico.models import Carrera, Graduado, GraduadoCarrera
from academico.servicios.auditoria import registrar_auditoria
from academico.servicios.legajo import generar_legajo


CLAVE_PENDIENTE = "carga_graduados_pendiente"


def _legajo_derivado(dni, anio):
    """Legajo calculado; ``None`` si falta el DNI o el año de ingreso."""

    return generar_legajo(dni, anio)


def datos_desde_form(form):
    """
    Convierte el cleaned_data del formulario a un dict de trabajo.

    Las fechas se dejan como objetos ``date``: ``guardar_pendiente``
    se encarga de serializarlas si hay que pedir confirmación.
    """

    datos = form.cleaned_data
    dni = datos["dni"]
    anio = datos["anio_ingreso_universidad"]

    return {
        "dni": dni,
        # Sólo para mostrar en la confirmación; no es un input.
        "legajo": _legajo_derivado(dni, anio),
        "nombre": datos["nombre"],
        "apellido": datos["apellido"],
        "codigo_carrera": datos["codigo_carrera"].codigo_carrera,
        "anio_ingreso_universidad": anio,
        "fecha_ingreso_carrera": datos["fecha_ingreso_carrera"],
        "fecha_egreso_carrera": datos["fecha_egreso_carrera"],
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

    valor_anio = datos.get("anio_ingreso_universidad")

    if valor_anio in (None, ""):
        datos["anio_ingreso_universidad"] = None
    else:
        try:
            datos["anio_ingreso_universidad"] = int(valor_anio)
        except (TypeError, ValueError):
            return None, None

    # El legajo se recalcula: la sesión puede venir de una versión
    # anterior o el año pudo cambiar mientras se confirmaba.
    datos["legajo"] = _legajo_derivado(
        datos.get("dni"), datos["anio_ingreso_universidad"]
    )

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
    La identidad del graduado es el DNI (su clave primaria); el
    legajo derivado nunca se usa para detectar conflictos.
    """

    conflictos = []
    dni = datos["dni"]

    nuevo = _descripcion_persona_simple(datos)

    por_dni = Graduado.objects.filter(pk=dni).first()

    if por_dni is not None:
        conflictos.append({
            "entidad": "Datos personales del DNI",
            "clave": dni,
            "actual": _descripcion_persona(por_dni),
            "nuevo": nuevo,
        })

    relacion = GraduadoCarrera.objects.filter(
        dni_graduado_id=dni,
        codigo_carrera_id=datos["codigo_carrera"],
    ).first()

    if relacion is not None:
        conflictos.append({
            "entidad": "Datos de la carrera",
            "clave": datos["codigo_carrera"],
            "actual": (
                f"Ingreso {relacion.fecha_ingreso_carrera.isoformat()} · "
                f"Egreso {relacion.fecha_egreso_carrera.isoformat()}"
            ),
            "nuevo": (
                f"Ingreso {datos['fecha_ingreso_carrera'].isoformat()} · "
                f"Egreso {datos['fecha_egreso_carrera'].isoformat()}"
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

    El DNI identifica al graduado. El legajo se calcula solo en
    ``Graduado.save()`` con el DNI y el año de ingreso a la UARG.

    Los promedios no se informan en esta pantalla: se calculan en la
    previsualización del analítico y se guardan al validar.
    """

    carrera = Carrera.objects.get(
        codigo_carrera=datos["codigo_carrera"]
    )

    graduado, _ = Graduado.objects.update_or_create(
        pk=datos["dni"],
        defaults={
            "nombre": datos["nombre"],
            "apellido": datos["apellido"],
            "anio_ingreso_universidad": (
                datos["anio_ingreso_universidad"]
            ),
        },
    )

    relacion, _ = GraduadoCarrera.objects.update_or_create(
        dni_graduado=graduado,
        codigo_carrera=carrera,
        defaults={
            "fecha_ingreso_carrera": datos["fecha_ingreso_carrera"],
            "fecha_egreso_carrera": datos["fecha_egreso_carrera"],
        },
    )

    registrar_auditoria(
        usuario,
        "graduado_cargado_manualmente",
        entidad="Graduado",
        entidad_id=graduado.pk,
        detalle={
            "codigo_carrera": carrera.codigo_carrera,
            "anio_ingreso_universidad": (
                graduado.anio_ingreso_universidad
            ),
            "sobrescribiendo": sobrescribiendo,
        },
    )

    return graduado, relacion
