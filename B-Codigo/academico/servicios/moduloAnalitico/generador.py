"""
Construcción del contexto completo de un analítico a partir de la
base de datos (opción B: los datos del documento siempre se leen
de la base; no hay snapshots).

También genera el .docx descargable a partir de ese contexto.
"""

import re
from datetime import date

from django.db.models import Prefetch

from academico.models import (
    Carrera,
    CarreraResolucion,
    DatosNacimiento,
    Graduado,
    GraduadoCarrera,
    GraduadoExamen,
    Materia,
    PlanEstudiosMateria,
    Resolucion,
    Secundario,
    Titulo,
    TipoResolucion,
)
from academico.servicios.moduloAnalitico.utilidades_texto import (
    dni_con_puntos,
    fecha_larga,
    fecha_larga_letras,
    fecha_nacimiento_larga,
    nota_a_letras,
    promedio_a_letras,
    anio_con_punto,
)


def _resoluciones_de_carrera(carrera):
    """Resoluciones asociadas a la carrera, agrupadas por tipo."""

    orden = [
        TipoResolucion.INSTITUCIONAL,
        TipoResolucion.MINISTERIAL_NACIONAL,
        TipoResolucion.OTRO_INSTRUMENTO,
    ]
    etiquetas = dict(TipoResolucion.choices)

    asociadas = (
        carrera.resoluciones
        .select_related("resolucion")
        .order_by("resolucion")
    )

    grupos = []

    for clave in orden:
        grupos.append({
            "clave": clave,
            "etiqueta": etiquetas[clave],
            "items": [
                fila.resolucion
                for fila in asociadas
                if fila.resolucion.tipo_resolucion == clave
            ],
        })

    return grupos


def resoluciones_seleccionadas(carrera):
    """Ids de resoluciones asociadas a la carrera."""

    return set(
        carrera.resoluciones.values_list("resolucion", flat=True)
    )


def texto_resoluciones(agrupadas):
    """
    Arma las cadenas de resoluciones para el documento:
    institucionales, ministeriales y otros instrumentos.
    """

    institucionales = next(
        (g["items"] for g in agrupadas
         if g["clave"] == TipoResolucion.INSTITUCIONAL),
        [],
    )
    ministeriales = next(
        (g["items"] for g in agrupadas
         if g["clave"] == TipoResolucion.MINISTERIAL_NACIONAL),
        [],
    )
    otros = next(
        (g["items"] for g in agrupadas
         if g["clave"] == TipoResolucion.OTRO_INSTRUMENTO),
        [],
    )

    if institucionales:
        cuerpo = ", ".join(f"N.° {r}" for r in institucionales)
        texto_institucionales = f"Resoluciones {cuerpo}"
    else:
        texto_institucionales = "-"

    if ministeriales:
        texto_ministeriales = " y ".join(str(r) for r in ministeriales)
    else:
        texto_ministeriales = "-"

    if otros:
        texto_otros = " y ".join(str(r) for r in otros)
    else:
        texto_otros = "-"

    return (
        texto_institucionales,
        texto_ministeriales,
        texto_otros,
    )


def examenes_ordenados_por_anio(graduado, carrera):
    """
    Exámenes con año y orden derivados del plan de la carrera:
    cada materia se ubica según su posición en el cronograma
    (año, cuatrimestre, orden); las materias ajenas al plan van
    al final.
    """

    examenes = (
        GraduadoExamen.objects
        .filter(legajo_graduado=graduado)
        .select_related(
            "id_examen",
            "id_examen__codigo_materia",
        )
    )

    posicion = {}

    plan_materias = (
        PlanEstudiosMateria.objects
        .filter(codigo_plan__codigo_carrera=carrera)
        .select_related("codigo_materia", "id_grupo_optativo")
    )

    ubicaciones_grupo = {}

    for fila in plan_materias:
        if fila.id_grupo_optativo_id:
            continue

        posicion[fila.codigo_materia_id] = (
            fila.anio_materia or 99,
            fila.cuatrimestre_materia or "zz",
            fila.orden_materia or 99,
        )

    from academico.models import PlanEstudiosGrupoOptativo

    ubicaciones_grupo = {
        (u.codigo_plan_id, u.id_grupo_optativo_id): (
            u.anio_materia,
            u.cuatrimestre_materia,
            u.orden_materia,
        )
        for u in PlanEstudiosGrupoOptativo.objects.filter(
            codigo_plan__codigo_carrera=carrera,
        )
    }

    for fila in plan_materias:
        if fila.id_grupo_optativo_id:
            plan = fila.codigo_plan_id
            grupo = fila.id_grupo_optativo_id
            posicion[fila.codigo_materia_id] = (
                ubicaciones_grupo.get(
                    (plan, grupo),
                    (99, "zz", 99),
                )
            )

    def _clave(fila_examen):
        materia = fila_examen.id_examen.codigo_materia
        return posicion.get(materia.codigo_materia, (99, "zz", 99))

    ordenados = sorted(examenes, key=_clave)

    filas = []

    for indice, examen in enumerate(ordenados, start=1):
        exam = examen.id_examen
        materia = exam.codigo_materia
        acta = exam.acta_respaldatoria
        match_folio = re.search(r"\d{3}$", acta) if acta else None

        if match_folio:
            folio = match_folio.group(0)
        elif acta:
            folio = "—"
        else:
            folio = ""

        if examen.nota is None:
            nota_txt = "-"
        else:
            nota_txt = nota_a_letras(examen.nota)

        filas.append({
            "orden": f"{indice:02d}",
            "anio": (
                f"{posicion[materia.codigo_materia][0]}º"
                if materia.codigo_materia in posicion
                and posicion[materia.codigo_materia][0] != 99
                else ""
            ),
            "espacio": materia.nombre_materia,
            "nota": examen.nota,
            "nota_txt": (
                nota_a_letras(examen.nota)
                if examen.nota is not None else "-"
            ),
            "fecha": (
                exam.fecha_examen.strftime("%d-%m-%Y")
                if exam.fecha_examen else ""
            ),
            "fecha_examen": (
                exam.fecha_examen.isoformat()
                if exam.fecha_examen else ""
            ),
            "tipo": exam.tipo_examen or "Examen",
            "respaldo": acta,
            "folio": folio,
            "materia_codigo": materia.codigo_materia,
            "nota_valor": examen.nota,
        })

    return filas


def contexto_analitico(graduado, carrera, tipo_documento):
    """
    Contexto completo para renderizar el analítico (preview o
    documento) desde la base de datos.
    """

    registro = (
        GraduadoCarrera.objects
        .filter(
            legajo_graduado=graduado,
            codigo_carrera=carrera,
        )
        .first()
    )

    datos_nacimiento = (
        DatosNacimiento.objects
        .filter(legajo_graduado=graduado)
        .select_related("id_ciudad", "id_provincia")
        .first()
    )

    secundario = (
        Secundario.objects
        .filter(legajo_graduado=graduado)
        .select_related("id_ciudad", "id_provincia")
        .first()
    )

    resoluciones = _resoluciones_de_carrera(carrera)
    texto_inst, texto_minist, texto_otros = texto_resoluciones(
        resoluciones
    )

    titulo = (
        Titulo.objects
        .filter(codigo_carrera=carrera)
        .first()
    )

    fecha_egreso = (
        registro.fecha_egreso_carrera if registro else None
    )
    promedio = (
        registro.promedio_sin_aplazo if registro else None
    )

    filas = examenes_ordenados_por_anio(graduado, carrera)

    fecha_ingreso_universidad = graduado.fecha_ingreso_universidad

    return {
        "tipo_documento": tipo_documento,
        "graduado": graduado,
        "carrera": carrera,
        "registro": registro,
        "datos_nacimiento": datos_nacimiento,
        "secundario": secundario,
        "titulo": titulo,
        "resoluciones": resoluciones,
        "texto_resoluciones_institucionales": texto_inst,
        "texto_resoluciones_ministeriales": texto_minist,
        "texto_otros_instrumentos": texto_otros,
        "anio_ingreso_universidad": (
            fecha_ingreso_universidad.year
            if fecha_ingreso_universidad else ""
        ),
        "anio_ingreso_carrera": (
            registro.fecha_ingreso_carrera.year if registro else ""
        ),
        "fecha_egreso": fecha_egreso,
        "promedio_general": promedio,
        "promedio_general_str": (
            f"{promedio:.2f}".replace(".", ",")
            if promedio is not None else "-"
        ),
        "promedio_general_letras": (
            promedio_a_letras(promedio)
            if promedio is not None else ""
        ),
        "fecha_egreso_larga": fecha_larga(fecha_egreso),
        "dni_con_puntos": dni_con_puntos(graduado.dni),
        "dia_nacimiento": (
            f"{datos_nacimiento.fecha_nacimiento.day:02d}"
            if datos_nacimiento and datos_nacimiento.fecha_nacimiento
            else ""
        ),
        "mes_nacimiento": (
            datos_nacimiento.fecha_nacimiento.strftime("%m")
            if datos_nacimiento and datos_nacimiento.fecha_nacimiento
            else ""
        ),
        "anio_nacimiento": (
            anio_con_punto(datos_nacimiento.fecha_nacimiento.year)
            if datos_nacimiento and datos_nacimiento.fecha_nacimiento
            else ""
        ),
        "fecha_nacimiento_larga": fecha_nacimiento_larga(
            datos_nacimiento.fecha_nacimiento
            if datos_nacimiento else None
        ),
        "filas": filas,
        "fecha_emision_larga": fecha_larga_letras(date.today()),
        "fecha_hoy_larga": fecha_larga_letras(date.today()),
    }

def render_docx(contexto):
    """
    Genera el .docx del analítico a partir del contexto.
    Devuelve los bytes del documento.
    """

    from io import BytesIO

    from docxtpl import DocxTemplate

    tipo = contexto["tipo_documento"]

    ruta = (
        "analitico_titulo.docx"
        if tipo == "titulo"
        else "analitico_en_tramite.docx"
    )

    doc = DocxTemplate(f"plantillas/{ruta}")

    fecha_emision = date.today()

    mes_letras = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ][fecha_emision.month - 1]

    fecha_egreso = contexto.get("fecha_egreso")

    dia_egreso_letras = (
        f"{fecha_egreso.day} de {mes_letras} "
        f"de {anio_con_punto(fecha_egreso.year)}"
        if fecha_egreso else "-"
    )

    datos = {
        "apellido": contexto["graduado"].apellido.upper(),
        "nombre": contexto["graduado"].nombre.upper(),
        "dni": contexto["dni_con_puntos"],
        "dia_nacimiento": contexto.get("dia_nacimiento", ""),
        "mes_nacimiento_letras": (
            [
                "enero", "febrero", "marzo", "abril", "mayo", "junio",
                "julio", "agosto", "septiembre", "octubre",
                "noviembre", "diciembre",
            ][
                (contexto["datos_nacimiento"].fecha_nacimiento.month - 1)
            ] if contexto["datos_nacimiento"]
            and contexto["datos_nacimiento"].fecha_nacimiento
            else ""
        ),
        "anio_nacimiento": contexto.get("anio_nacimiento", ""),
        "fecha_nacimiento_larga": contexto.get("fecha_nacimiento_larga", ""),
        "ciudad_nacimiento": (
            contexto["datos_nacimiento"].id_ciudad.nombre_ciudad
            if contexto["datos_nacimiento"] else ""
        ),
        "provincia_nacimiento": (
            contexto["datos_nacimiento"].id_provincia.nombre_provincia
            if contexto["datos_nacimiento"] else ""
        ),
        "titulo_secundario": (
            contexto["secundario"].titulo_secundario
            if contexto["secundario"] else ""
        ),
        "nombre_secundario": (
            contexto["secundario"].nombre_secundario
            if contexto["secundario"] else ""
        ),
        "ciudad_secundario": (
            contexto["secundario"].id_ciudad.nombre_ciudad
            if contexto["secundario"] else ""
        ),
        "anio_egreso_secundario": (
            anio_con_punto(contexto["secundario"].anio_egreso_secundario)
            if contexto["secundario"]
            and contexto["secundario"].anio_egreso_secundario
            else ""
        ),
        "anio_ingreso_uarg": contexto.get("anio_ingreso_universidad", ""),
        "anio_ingreso_carrera": contexto.get("anio_ingreso_carrera", ""),
        "carrera": contexto["carrera"].nombre_carrera,
        "resoluciones_institucionales": contexto[
            "texto_resoluciones_institucionales"
        ],
        "resoluciones_ministeriales": contexto[
            "texto_resoluciones_ministeriales"
        ],
        "otros_instrumentos": contexto[
            "texto_otros_instrumentos"
        ],
        "titulo_otorgado": (
            contexto["titulo"].nombre_titulo
            if contexto["titulo"] else ""
        ),
        "promedio": contexto.get("promedio_general_str", "-"),
        "promedio_letras": contexto.get("promedio_general_letras", ""),
        "fecha_egreso_larga": dia_egreso_letras,
        "fecha_emision_larga": contexto.get("fecha_emision_larga", ""),
        "filas": [
            {
                **fila,
                "nota": fila.get("nota_txt", ""),
            }
            for fila in contexto["filas"]
        ],
    }

    doc.render(datos)

    buffer = BytesIO()
    doc.save(buffer)

    return buffer.getvalue()
