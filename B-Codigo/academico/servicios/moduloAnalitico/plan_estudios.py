"""
Contraste de las filas del analítico con el plan de estudios de la carrera.

El plan se usa como **ayuda asistida**:

1. Avisar cuando el código y el nombre leídos del Lincoln no coinciden con
   una materia del plan asignado a la carrera. El aviso **no bloquea** la
   validación ni la descarga.
2. Sugerir el ``anio_materia`` y el ``orden_materia`` del plan. Lo que el
   usuario escribió en la previsualización tiene prioridad: el plan sólo
   completa los valores que quedaron vacíos y desempata el orden.

Si el código del Lincoln no existe en el plan pero el nombre coincide (o
es muy parecido), se toma la fila del plan por nombre y se avisa
``codigo_distinto``. El ``es_requisito`` sigue siendo un dato manual.
"""

import difflib
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


def _anio_o_none(valor):
    """Entero tolerante con años ya numericados o escritos en un input."""

    if valor is None or valor == "":
        return None

    try:
        return int(float(str(valor).strip()))
    except (TypeError, ValueError):
        return None


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
    Devuelve el plan a sugerir para la carrera o ``None``.

    Se prefiere el plan vigente. Si no hay ninguno marcado como vigente
    pero la carrera tiene un solo plan cargado, se usa ese y se avisa
    (``plan_no_vigente``) para que el usuario pueda corregir la marca.
    """

    if carrera is None:
        return None

    if carrera.plan_vigente is not None:
        return carrera.plan_vigente

    planes = list(carrera.planes_estudio.all()[:2])

    return planes[0] if len(planes) == 1 else None


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


def _sugerencia_por_nombre(nombre_norm, por_nombre):
    """
    Busca una fila del plan por nombre.

    Devuelve ``(fila_del_plan, tipo, codigos_sugeridos)``. El tipo es
    ``exacto``/``similar`` cuando se adoptó una única fila con seguridad;
    si hay ambigüedad, no se adopta nada y se devuelven códigos para el
    aviso.
    """

    exactas = por_nombre.get(nombre_norm, [])

    if len(exactas) == 1:
        return exactas[0], "exacto", []

    if len(exactas) > 1:
        codigos = sorted({
            pad_codigo(item.codigo_materia_id) for item in exactas
        })

        return None, "ambiguo", codigos

    if not nombre_norm:
        return None, "", []

    candidatos = []

    for nombre, filas_plan in por_nombre.items():
        if not nombre:
            continue

        proporcion = difflib.SequenceMatcher(
            None, nombre_norm, nombre
        ).ratio()
        candidatos.append((proporcion, filas_plan))

    candidatos.sort(key=lambda item: item[0], reverse=True)

    if not candidatos:
        return None, "", []

    codigos = sorted({
        pad_codigo(fila.codigo_materia_id)
        for _, filas_plan in candidatos[:3]
        for fila in filas_plan
    })

    mejor = candidatos[0]
    segundo = candidatos[1][0] if len(candidatos) > 1 else 0

    if (
        mejor[0] >= 0.9
        and mejor[0] - segundo >= 0.05
        and len(mejor[1]) == 1
    ):
        return mejor[1][0], "similar", []

    return None, "similar", codigos


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
        "tipo_sugerencia": "",
        "plan_no_vigente": False,
        "plan_codigo": "",
        "mensaje": mensaje,
    }
    resultado.update(extra)

    return resultado


def verificar_filas(carrera, filas):
    """
    Devuelve una verificación por fila, en el mismo orden que ``filas``.

    Cada fila debe traer ``codigo_materia``/``materia_codigo`` y
    ``nombre_materia``/``espacio``. Un código ausente en el plan se
    contrasta por nombre: si hay una sola coincidencia confiable, se
    adoptan su año y orden como sugerencia del plan.
    """

    plan = plan_de_carrera(carrera)
    plan_no_vigente = (
        plan is not None
        and getattr(carrera, "plan_vigente_id", None) != plan.pk
    )
    verificaciones = []

    if plan is None:
        return [
            _resultado(
                "sin_plan",
                "La carrera no tiene un plan de estudios asignado; "
                "no se puede contrastar la materia ni sugerir el año. "
                "Completá el año y el orden en la grilla.",
                fila=indice,
                codigo_lincoln=pad_codigo(_codigo_de(fila)),
                nombre_lincoln=_nombre_de(fila),
                espacio=fila.get("espacio", ""),
            )
            for indice, fila in enumerate(filas, start=1)
        ]

    por_codigo, por_nombre = _indice_del_plan(plan)
    comunes = {
        "plan_no_vigente": plan_no_vigente,
        "plan_codigo": str(plan.pk),
    }

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

        fila_plan = por_codigo.get(codigo_pad) if codigo_pad else None
        tipo_sugerencia = ""
        codigos_sugeridos = []

        if fila_plan is None:
            fila_plan, tipo_sugerencia, codigos_sugeridos = (
                _sugerencia_por_nombre(nombre_norm, por_nombre)
            )

        if fila_plan is None:
            if not codigo_pad:
                mensaje = (
                    "El Lincoln no informa código de materia y el nombre "
                    "no coincide con el plan. Completá el año a mano."
                )
                estado = "sin_codigo"
            else:
                mensaje = (
                    f"El código {codigo_pad} no existe en el plan de "
                    "estudios de la carrera."
                )

                if codigos_sugeridos:
                    mensaje += (
                        " Posibles materias del plan: "
                        + ", ".join(codigos_sugeridos)
                        + "."
                    )

                estado = "codigo_no_en_plan"

            verificaciones.append(_resultado(
                estado,
                mensaje,
                codigos_sugeridos=codigos_sugeridos,
                **base,
                **comunes,
            ))
            continue

        nombre_plan = fila_plan.codigo_materia.nombre_materia
        anio = fila_plan.anio_materia
        orden = fila_plan.orden_materia
        mensajes = []

        if tipo_sugerencia:
            como = (
                "por nombre" if tipo_sugerencia == "exacto"
                else "por nombre similar"
            )
            mensajes.append(
                f"El código {codigo_pad or 'sin código'} no está en el "
                f"plan; se tomó «{nombre_plan}» "
                f"({pad_codigo(fila_plan.codigo_materia_id)}) del plan "
                f"{como}. Revisá que sea la materia correcta."
            )
            estado = "codigo_distinto"
        elif normalizar_nombre(nombre_plan) != nombre_norm:
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
                "La fila del plan no tiene año ni orden cargados: "
                "completalos en la grilla si corresponde."
            )

        if plan_no_vigente:
            mensajes.append(
                f"Se usó el plan {plan} aunque no está marcado como "
                "vigente para la carrera."
            )

        verificaciones.append(_resultado(
            estado,
            " ".join(mensajes),
            codigo_esperado=pad_codigo(fila_plan.codigo_materia_id),
            nombre_esperado=nombre_plan,
            anio_plan=anio,
            orden_plan=orden,
            codigos_sugeridos=codigos_sugeridos,
            tipo_sugerencia=tipo_sugerencia,
            **base,
            **comunes,
        ))

    return verificaciones


def aplicar_plan_a_filas(carrera, filas, respetar_edicion=False):
    """
    Adjunta la verificación del plan y completa año/orden de las filas.

    Con ``respetar_edicion=True`` (modo de la previsualización) gana lo
    que escribió el usuario: el ``orden_num`` mantiene las posiciones
    elegidas y el ``anio``/``anio_num`` escrito se conserva. El plan
    completa los valores vacíos y desempata. Sin esa opción se mantiene
    el comportamiento histórico de ordenar por el plan.

    Devuelve las filas ordenadas; cada una incluye ``verificacion``,
    ``anio``, ``anio_txt`` y ``orden_plan``.
    """

    verificaciones = verificar_filas(carrera, filas)
    originales = list(enumerate(filas))

    for indice, fila in originales:
        verificacion = verificaciones[indice]
        anio_plan = verificacion["anio_plan"]
        valor_anio = (
            fila.get("anio_num")
            if fila.get("anio_num") is not None
            else fila.get("anio")
        )
        anio_manual = _anio_o_none(valor_anio)
        anio = (
            anio_manual
            if respetar_edicion and anio_manual is not None
            else anio_plan
        )

        fila["verificacion"] = verificacion
        fila["orden_plan"] = verificacion["orden_plan"]
        fila["anio"] = anio if anio is not None else ""
        fila["anio_num"] = anio
        fila["anio_cursado"] = anio
        fila["anio_txt"] = f"{anio}°" if anio is not None else ""

    def clave(item):
        indice, fila = item
        verificacion = verificaciones[indice]
        orden_plan = verificacion["orden_plan"]
        orden_manual = fila.get("orden_num")
        ultimo = 10 ** 6

        if respetar_edicion and orden_manual is not None:
            return (0, orden_manual, indice)

        if orden_plan is not None:
            return (
                1,
                orden_plan,
                orden_manual if orden_manual is not None else ultimo,
                indice,
            )

        return (
            2,
            0,
            orden_manual if orden_manual is not None else ultimo,
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
