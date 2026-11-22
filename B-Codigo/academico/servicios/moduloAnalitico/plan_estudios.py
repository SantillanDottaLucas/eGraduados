"""
Contraste de las filas del analítico con el plan de estudios de la carrera.

El plan sólo se usa para dos cosas:

1. Avisar cuando el código y el nombre leídos del Lincoln no coinciden con
   una materia del plan asignado a la carrera. El aviso **no bloquea** la
   validación ni la descarga.
2. Tomar el ``anio_materia`` y el ``orden_materia`` del plan para ordenar
   el analítico y mostrar el año de cursada (1, 2, 3...), no el año de
   calendario del certificado.

Las filas que no pueden asociarse a una materia del plan van al final,
con el año vacío y el aviso correspondiente. El ``es_requisito`` sigue
siendo un dato manual y no participa de este servicio.
"""

import re
import unicodedata


def pad_codigo(codigo):
    """Código numérico con 4 cifras; los alfanuméricos quedan intactos."""

    texto = str(codigo or "").strip()

    return texto.zfill(4) if texto.isdigit() else texto


def normalizar_nombre(nombre):
    """Comparable sin acentos, sin caso y con espacios colapsados."""

    descompuesto = unicodedata.normalize("NFKD", str(nombre or ""))
    sin_acentos = "".join(
        caracter for caracter in descompuesto
        if not unicodedata.combining(caracter)
    )

    return re.sub(r"\s+", " ", sin_acentos).strip().lower()


def _codigo_de(fila):
    # Si la fila viene del Lincoln, se compara el valor leído del
    # certificado, no el de la materia que eligió el usuario en el
    # selector (que pudo corregirse a mano).
    valor = (
        fila.get("codigo_lincoln")
        or fila.get("codigo_materia")
        or fila.get("materia_codigo")
        or ""
    )
    return str(valor).strip()


def _nombre_de(fila):
    return (
        fila.get("nombre_lincoln")
        or fila.get("nombre_materia")
        or fila.get("espacio")
        or fila.get("nombre")
        or ""
    )


def plan_de_carrera(carrera):
    """
    Devuelve el plan vigente de la carrera o ``None``.

    No se busca un plan alternativo: si la carrera no tiene plan asignado,
    se informa la discrepancia y se conserva el orden anterior.
    """

    if carrera is None:
        return None

    return carrera.plan_vigente


def _indice_del_plan(plan):
    """Índices del plan por código y por nombre normalizado."""

    from academico.models import PlanEstudiosMateria

    filas = (
        PlanEstudiosMateria.objects
        .filter(codigo_plan=plan)
        .select_related("codigo_materia")
    )

    por_codigo = {}
    por_nombre = {}

    for fila in filas:
        codigo = pad_codigo(fila.codigo_materia_id)
        nombre = fila.codigo_materia.nombre_materia

        por_codigo[codigo] = fila
        por_nombre.setdefault(normalizar_nombre(nombre), []).append(fila)

    return por_codigo, por_nombre


def _resultado(estado, mensaje, **extra):
    resultado = {
        "estado": estado,
        "codigo_lincoln": "",
        "nombre_lincoln": "",
        "codigo_esperado": "",
        "nombre_esperado": "",
        "anio_plan": None,
        "orden_plan": None,
        "codigos_sugeridos": [],
        "mensaje": mensaje,
    }
    resultado.update(extra)

    return resultado


def verificar_filas(carrera, filas):
    """
    Devuelve una verificación por fila, en el mismo orden que ``filas``.

    Cada fila debe traer ``codigo_materia``/``materia_codigo`` y
    ``nombre_materia``/``espacio``.
    """

    plan = plan_de_carrera(carrera)
    verificaciones = []

    if plan is None:
        return [
            _resultado(
                "sin_plan",
                "La carrera no tiene un plan de estudios vigente asignado; "
                "no se puede contrastar la materia ni asignar el año del plan.",
                fila=indice,
                codigo_lincoln=pad_codigo(_codigo_de(fila)),
                nombre_lincoln=_nombre_de(fila),
                espacio=fila.get("espacio", ""),
            )
            for indice, fila in enumerate(filas, start=1)
        ]

    por_codigo, por_nombre = _indice_del_plan(plan)

    for numero, fila in enumerate(filas, start=1):
        codigo = _codigo_de(fila)
        nombre = _nombre_de(fila)
        codigo_pad = pad_codigo(codigo)
        nombre_norm = normalizar_nombre(nombre)

        base = {
            "fila": numero,
            "codigo_lincoln": codigo,
            "nombre_lincoln": nombre,
            "espacio": fila.get("espacio", nombre),
        }

        if not codigo_pad:
            verificaciones.append(_resultado(
                "sin_codigo",
                "El Lincoln no informa código de materia; no se puede "
                "contrastar con el plan.",
                **base,
            ))
            continue

        fila_plan = por_codigo.get(codigo_pad)

        if fila_plan is None:
            sugeridas = por_nombre.get(nombre_norm, [])
            codigos = sorted({
                pad_codigo(item.codigo_materia_id) for item in sugeridas
            })
            mensaje = (
                f"El código {codigo_pad} no existe en el plan de estudios "
                f"de la carrera."
            )

            if codigos:
                mensaje += (
                    " El nombre coincide con materia(s) del plan con "
                    f"código {', '.join(codigos)}; revisar."
                )

            verificaciones.append(_resultado(
                "codigo_no_en_plan",
                mensaje,
                codigos_sugeridos=codigos,
                **base,
            ))
            continue

        nombre_plan = fila_plan.codigo_materia.nombre_materia
        anio = fila_plan.anio_materia
        orden = fila_plan.orden_materia
        mensajes = []

        if normalizar_nombre(nombre_plan) != nombre_norm:
            estado = "nombre_distinto"
            mensajes.append(
                f"El código {codigo_pad} corresponde en el plan a "
                f"«{nombre_plan}», pero el Lincoln indica «{nombre}»."
            )
        else:
            estado = "ok"
            mensajes.append(
                "Código y nombre coinciden con el plan de estudios."
            )

        if anio is None or orden is None:
            estado = "plan_incompleto"
            mensajes.append(
                "La fila del plan no tiene año ni orden cargados; se ubica "
                "al final y el año queda vacío."
            )

        verificaciones.append(_resultado(
            estado,
            " ".join(mensajes),
            codigo_esperado=pad_codigo(fila_plan.codigo_materia_id),
            nombre_esperado=nombre_plan,
            anio_plan=anio,
            orden_plan=orden,
            **base,
        ))

    return verificaciones


def aplicar_plan_a_filas(carrera, filas):
    """
    Adjunta la verificación del plan, aplica año/orden y reordena las filas.

    El orden del plan es el criterio principal; el ``orden_num`` que ya
    tuviera la fila (ingresado por el usuario) se usa sólo para desempatar.
    Devuelve las filas ordenadas; cada una incluye ``verificacion``,
    ``anio``, ``anio_txt`` y ``orden_plan``.
    """

    verificaciones = verificar_filas(carrera, filas)
    originales = list(enumerate(filas))

    for indice, fila in originales:
        verificacion = verificaciones[indice]
        anio = verificacion["anio_plan"]

        fila["verificacion"] = verificacion
        fila["orden_plan"] = verificacion["orden_plan"]
        fila["anio"] = anio if anio is not None else ""
        fila["anio_num"] = anio
        fila["anio_txt"] = f"{anio}°" if anio is not None else ""

    def clave(item):
        indice, fila = item
        verificacion = verificaciones[indice]
        orden_plan = verificacion["orden_plan"]
        orden_manual = fila.get("orden_num")

        return (
            orden_plan is None,
            orden_plan if orden_plan is not None else 0,
            orden_manual if orden_manual is not None else 10 ** 6,
            indice,
        )

    ordenadas = sorted(originales, key=clave)
    resultado = []

    for posicion, (_, fila) in enumerate(ordenadas, start=1):
        fila["orden_num"] = posicion
        fila["orden"] = f"{posicion:02d}"
        fila["verificacion"]["fila"] = posicion
        fila["verificacion"]["espacio"] = fila.get("espacio", "")
        resultado.append(fila)

    return resultado
