"""
Construye las plantillas de analíticos a partir de Plantilla.docx.

Genera:
    plantillas/analitico_titulo.docx
    plantillas/analitico_en_tramite.docx

La plantilla de origen contiene los DOS documentos en un mismo
archivo (el primero «Título» y el segundo «Título en trámite»).
Este script:

1. Separa cada documento en su propia plantilla.
2. Fusiona las dos tablas de materias de cada documento en una
   sola tabla con un bucle docxtpl (el contenido de las filas se
   repite para cada fila del contexto, incluidas las recursadas o
   desaprobadas).
3. Reemplaza los datos hardcodeados de la persona de ejemplo por
   marcadores {{ ... }}.
4. Agrega tabuladores con leader «hyphen» al final de cada celda
   de materias (guiones de relleno automáticos, independientemente
   del ancho del contenido y alineados verticalmente con la última
   línea del nombre de la materia), y las filas de materias quedan
   alineadas verticalmente al fondo.
5. NO repite el encabezado de tabla entre páginas (comportamiento
   original conservado).
"""

import copy
import shutil
import zipfile
from pathlib import Path

from docx import Document
from docx.shared import Pt
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ORIGEN = Path("Plantilla.docx")
DIR_SALIDA = Path("plantillas")
SALIDA_TITULO = DIR_SALIDA / "analitico_titulo.docx"
SALIDA_EN_TRAMITE = DIR_SALIDA / "analitico_en_tramite.docx"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ==================================================
# Utilidades de bajo nivel (XML del documento)
# ==================================================

def tag(nombre):
    return f"{{{W}}}{nombre}"


def limpiar_runs(parrafo):
    """Elimina todos los runs (w:r) de un párrafo."""
    for run in parrafo.findall(tag("r")):
        parrafo.remove(run)


def tiene_texto(parrafo, aguja):
    texto = "".join(t.text or "" for t in parrafo.iter(tag("t")))
    return aguja in texto


def buscar_parrafo_por_texto(body, aguja):
    for parrafo in body.iter(tag("p")):
        if tiene_texto(parrafo, aguja):
            return parrafo
    return None


def fijar_rpr(parrafo, bold=None, sz=None):
    """
    Asigna propiedades de fuente uniformes a los runs del párrafo.
    """
    for run in parrafo.findall(tag("r")):
        rpr = run.find(tag("rPr"))

        if rpr is None:
            rpr = OxmlElement("w:rPr")
            run.insert(0, rpr)

        rfonts = rpr.find(tag("rFonts"))

        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)

        rfonts.set(qn("w:cs"), "Arial")

        if bold is not None:
            b = rpr.find(tag("b"))

            if bold:
                if b is None:
                    rpr.append(OxmlElement("w:b"))
            elif b is not None:
                rpr.remove(b)

        if sz is not None:
            elemento = rpr.find(tag("sz"))

            if elemento is None:
                elemento = OxmlElement("w:sz")
                rpr.append(elemento)

            elemento.set(qn("w:val"), str(sz))


def agregar_run(parrafo, texto, bold=False, sz=None):
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rfonts = OxmlElement("w:rFonts")
    rfonts.set(qn("w:cs"), "Arial")

    if bold:
        rpr.append(OxmlElement("w:b"))

    if sz is not None:
        size = OxmlElement("w:sz")
        size.set(qn("w:val"), str(sz))
        rpr.append(size)

    rpr.append(rfonts)
    run.append(rpr)

    elemento = OxmlElement("w:t")
    elemento.set(qn("xml:space"), "preserve")
    elemento.text = texto
    run.append(elemento)
    parrafo.append(run)


def parrafo_vacio():
    p = OxmlElement("w:p")
    return p


def establecer_texto_parrafo(parrafo, texto, bold=False, sz=None):
    limpiar_runs(parrafo)
    agregar_run(parrafo, texto, bold=bold, sz=sz)


def borrar_elementos(body, elementos):
    for el in elementos:
        body.remove(el)


def tablas(body):
    return body.findall(tag("tbl"))


def filas_tabla(tabla):
    return list(tabla.iter(tag("tr")))


def celdas_fila(fila):
    return list(fila.iter(tag("tc")))


def row_es_cierre(fila):
    texto = "".join(t.text or "" for t in fila.iter(tag("t")))
    return "Promedio General" in texto


def extraer_cierre_de_fila(fila):
    """
    Convierte los párrafos de la fila de cierre (span completo)
    en párrafos independientes de nivel superior.
    """
    parrafos = []

    for p in fila.iter(tag("p")):
        clon = copy.deepcopy(p)
        parrafos.append(clon)

    return parrafos


def fijar_celda_v_align_bottom(tc):
    tcpr = tc.find(tag("tcPr"))

    if tcpr is None:
        tcpr = OxmlElement("w:tcPr")
        tc.insert(0, tcpr)

    if tcpr.find(tag("vAlign")) is None:
        valign = OxmlElement("w:vAlign")
        valign.set(qn("w:val"), "bottom")
        tcpr.append(valign)


def fijar_bordes_laterales(tc):
    tcpr = tc.find(tag("tcPr"))

    if tcpr is None:
        tcpr = OxmlElement("w:tcPr")
        tc.insert(0, tcpr)

    if tcpr.find(tag("tcBorders")) is not None:
        return

    borders = OxmlElement("w:tcBorders")
    izq = OxmlElement("w:left")
    izq.set(qn("w:val"), "single")
    izq.set(qn("w:sz"), "4")
    izq.set(qn("w:space"), "0")
    izq.set(qn("w:color"), "auto")
    borders.append(izq)
    der = OxmlElement("w:right")
    der.set(qn("w:val"), "single")
    der.set(qn("w:sz"), "4")
    der.set(qn("w:space"), "0")
    der.set(qn("w:color"), "auto")
    borders.append(der)
    tcpr.append(borders)


def fijar_tab_leader(parrafo, ancho_celda_dxa, lider="hyphen"):
    """
    Define un tabulador derecho al final del área útil de la celda
    con leader de guiones.
    """
    ppr = parrafo.find(tag("pPr"))

    if ppr is None:
        ppr = OxmlElement("w:pPr")
        parrafo.insert(0, ppr)

    tabs = ppr.find(tag("tabs"))

    if tabs is not None:
        ppr.remove(tabs)

    tabs = OxmlElement("w:tabs")
    tab = OxmlElement("w:tab")
    tab.set(qn("w:val"), "right")
    tab.set(qn("w:pos"), str(ancho_celda_dxa - 140))
    tab.set(qn("w:leader"), lider)
    tabs.append(tab)
    ppr.append(tabs)


def agregar_tabulacion(parrafo):
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    rfonts = OxmlElement("w:rFonts")
    rfonts.set(qn("w:cs"), "Arial")
    rpr.append(rfonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "20")
    rpr.append(sz)
    run.append(rpr)
    tab = OxmlElement("w:tab")
    run.append(tab)
    parrafo.append(run)


def marcar_parrafo(parrafo, lider_ancho=None, sz=None):
    """Agrega leader de guiones a la derecha del párrafo."""
    if lider_ancho:
        fijar_tab_leader(parrafo, lider_ancho)
    agregar_tabulacion(parrafo)


def construir_fila_materias(tabla, anchos, template_fila):
    """
    Elimina las filas de ejemplo y construye la fila prototipo
    con los marcadores docxtpl y los tabuladores de guiones.
    """
    filas = filas_tabla(tabla)
    encabezado = filas[0]

    # Eliminar filas de datos (se conservan sólo el encabezado).
    for fila in filas[1:]:
        tabla.remove(fila)

    # Nueva fila prototipo.
    from docx import Document  # noqa: F401  (asegura import)

    nueva = copy.deepcopy(template_fila)
    tabla.append(nueva)

    celdas = celdas_fila(nueva)
    contenidos = [
        "{{ fila.orden }}",
        "{{ fila.anio }}",
        "{{ fila.espacio }}",
        "{{ fila.nota }}",
        "{{ fila.fecha }}",
        "{{ fila.tipo }}",
        "{{ fila.respaldo }}",
        "{{ fila.folio }}",
    ]

    for i, (tc, texto) in enumerate(zip(celdas, contenidos)):
        parrafos_celda = list(tc.iter(tag("p")))

        # Normalizar: una sola línea por celda.
        for p in parrafos_celda[1:]:
            tc.remove(p)

        p = parrafos_celda[0]
        limpiar_runs(p)
        agregar_run(p, texto, sz=20)

        # Guiones de relleno + alineación vertical inferior.
        if i != 2:
            marcar_parrafo(p, anchos[i], sz=20)

        fijar_celda_v_align_bottom(tc)
        fijar_bordes_laterales(tc)

    # Filas de control del bucle {%tr %} de docxtpl:
    # la fila de apertura colapsa a «{% for ... %}» y la de
    # cierre a «{% endfor %}»; la fila de datos se repite.

    fila_for = copy.deepcopy(nueva)
    primera = celdas_fila(fila_for)[0]
    parrafos = list(primera.iter(tag("p")))

    for p in parrafos[1:]:
        primera.remove(p)

    for p in parrafos:
        limpiar_runs(p)
        agregar_run(p, "{%tr for fila in filas %}", sz=1)

    for tc in celdas_fila(fila_for)[1:]:
        parrafos_tc = list(tc.iter(tag("p")))

        for p in parrafos_tc[1:]:
            tc.remove(p)

        for p in parrafos_tc:
            limpiar_runs(p)

    fila_endfor = copy.deepcopy(nueva)
    primera = celdas_fila(fila_endfor)[0]
    parrafos = list(primera.iter(tag("p")))

    for p in parrafos[1:]:
        primera.remove(p)

    for p in parrafos:
        limpiar_runs(p)
        agregar_run(p, "{%tr endfor %}", sz=1)

    for tc in celdas_fila(fila_endfor)[1:]:
        parrafos_tc = list(tc.iter(tag("p")))

        for p in parrafos_tc[1:]:
            tc.remove(p)

        for p in parrafos_tc:
            limpiar_runs(p)

    indice = list(tabla).index(nueva)

    tabla.insert(indice, fila_for)
    tabla.insert(indice + 2, fila_endfor)

    # El ancho de las columnas no cambia: se conserva tblGrid.


def reescribir_certificante(parrafo, tipo):
    texto_titulo = (
        "La que suscribe, Rectora de la Universidad Nacional de la "
        "Patagonia Austral, CERTIFICA que: {{ apellido }}, {{ nombre }}, "
        "Documento Nacional de Identidad N.° {{ dni }}, nacida el "
        "{{ dia_nacimiento }} de {{ mes_nacimiento_letras }} de "
        "{{ anio_nacimiento }}, en {{ ciudad_nacimiento }}, Provincia de "
        "{{ provincia_nacimiento }}, nacionalidad argentina, con el Título "
        "de {{ titulo_secundario }}, expedido por el {{ nombre_secundario }}, "
        "sito en {{ ciudad_secundario }}, del cual egresó en el año "
        "{{ anio_egreso_secundario }}, ingresó a esta Universidad en el año "
        "{{ anio_ingreso_uarg }}, ha cursado la carrera de {{ carrera }} y "
        "ha aprobado todas las asignaturas de la misma, de conformidad al "
        "Plan de Estudios correspondiente a {{ resoluciones_institucionales }} "
        "Resolución del Ministerio de Cultura y Educación de la Nación N.° "
        "{{ resoluciones_ministeriales }} y {{ otros_instrumentos }}, cuyas "
        "asignaturas se detallan, haciéndose acreedora al Título de "
        "{{ titulo_otorgado }}. - - - - - - - - - - - - - - - - - - - - - -"
        " - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -"
    )
    texto_en_tramite = (
        "EL SECRETARIO ACADEMICO DE LA UNIDAD ACADEMICA RIO GALLEGOS DE "
        "LA UNIVERSIDAD NACIONAL DE LA PATAGONIA AUSTRAL, HACE CONSTAR "
        "QUE: {{ apellido }}, {{ nombre }}, Documento Nacional de Identidad "
        "N.° {{ dni }}, nacida el {{ fecha_nacimiento_larga }}, en "
        "{{ ciudad_nacimiento }}, Provincia de {{ provincia_nacimiento }}, "
        "nacionalidad argentina, con el Título de {{ titulo_secundario }}, "
        "expedido por el {{ nombre_secundario }}, sito en "
        "{{ ciudad_secundario }}, del cual egresó en el año "
        "{{ anio_egreso_secundario }}, ingresó a esta Universidad en el "
        "año {{ anio_ingreso_uarg }}, ha cursado la carrera de "
        "{{ carrera }} y ha aprobado todas las asignaturas de la misma, de "
        "conformidad al Plan de Estudios correspondiente a "
        "{{ resoluciones_institucionales }} Resolución del Ministerio de "
        "Cultura y Educación de la Nación N.° {{ resoluciones_ministeriales }} "
        "y {{ otros_instrumentos }}, cuyas asignaturas se detallan, "
        "haciéndose acreedora al Título de {{ titulo_otorgado }}, "
        "encontrándose el mismo EN TRAMITE. - - - - - - - - - - - - - - - - -"
    )

    if tipo == "titulo":
        establecer_texto_parrafo(parrafo, texto_titulo)
    else:
        establecer_texto_parrafo(parrafo, texto_en_tramite)


def reescribir_promedio(parrafo, tipo):
    if tipo == "titulo":
        texto = (
            "Promedio General: {{ promedio }} ({{ promedio_letras }})"
            "            Fecha de Egreso: {{ fecha_egreso_larga }}. -"
        )
    else:
        texto = (
            "Promedio General: {{ promedio }} ({{ promedio_letras }})"
            "            Fecha de Egreso: {{ fecha_egreso_larga }}. -"
        )

    establecer_texto_parrafo(parrafo, texto, sz=20)


def reescribir_emision(parrafo, tipo):
    if tipo == "titulo":
        texto = (
            "Se extiende el presente Certificado en la ciudad de Río "
            "Gallegos, capital de la Provincia de Santa Cruz, a los "
            "{{ fecha_emision_larga }}, para ser presentado ante las "
            "autoridades que así lo requieran. -"
        )
    else:
        texto = (
            "Se extiende la presente CONSTANCIA, a pedido de la "
            "interesada a los efectos de ser presentada ante las "
            "autoridades que correspondan, en la Ciudad de Río Gallegos, "
            "Capital de la Provincia de Santa Cruz, a los "
            "{{ fecha_emision_larga }}. -"
        )

    establecer_texto_parrafo(parrafo, texto, sz=20)


def reescribir_observaciones(parrafo):
    texto = (
        "OBSERVACIONES: ¿Se deja constancia que, en el Promedio General, "
        "no se han promediado los aplazos. (Art. 109 Ordenanza 188/UNPA/15)."
    )
    establecer_texto_parrafo(parrafo, texto, sz=20)


def reescribir_vale(parrafo):
    texto = (
        "La presente tiene validez por trescientos sesenta (360) días. -"
    )
    establecer_texto_parrafo(parrafo, texto, sz=20)


def procesar_documento(tipo):
    print(f"=== {tipo} ===")

    origen = ORIGEN
    destino = SALIDA_TITULO if tipo == "titulo" else SALIDA_EN_TRAMITE
    shutil.copyfile(origen, destino)

    doc = Document(destino)
    body = doc.element.body

    hijos = list(body)

    if tipo == "titulo":
        # Conservar la sección «Título»: hijos 0..11 + sectPr.
        for el in hijos[12:-1]:
            body.remove(el)
    else:
        # Conservar la sección «Título en trámite»: hijos 12..24 + sectPr.
        for el in hijos[:12]:
            body.remove(el)

    # Localizar las dos tablas de materias.
    tbls = tablas(body)

    if tipo == "titulo":
        tabla_materias = tbls[0]
        tabla_continuacion = tbls[1]

        # Localizar la fila de cierre (span completo) en la tabla 2.
        cierre = None

        for fila in filas_tabla(tabla_continuacion):
            if row_es_cierre(fila):
                cierre = fila
                break

        parrafos_cierre = extraer_cierre_de_fila(cierre) if cierre is not None else []

        # Sacar los párrafos de cierre de la tabla y borrarla.
        if cierre is not None:
            tabla_continuacion.remove(cierre)

        body.remove(tabla_continuacion)

        # Insertar los párrafos de cierre después de la tabla de materias.
        idx = list(body).index(tabla_materias)

        for j, p in enumerate(parrafos_cierre):
            body.insert(idx + 1 + j, p)

    else:
        # Título en trámite: el cierre ya está fuera de las tablas.
        tabla_materias = tbls[0]
        tabla_continuacion = tbls[1]
        body.remove(tabla_continuacion)

    # Fusionar materias: construir la fila prototipo en la tabla 1.
    anchos = [637, 567, 2977, 1134, 1276, 1276, 1842, 717]
    template_fila = copy.deepcopy(filas_tabla(tabla_materias)[1])
    construir_fila_materias(tabla_materias, anchos, template_fila)

    # Reescribir los párrafos de texto libre con marcadores.
    for p in body.iter(tag("p")):
        if tiene_texto(p, "CERTIFICA que:") or tiene_texto(p, "HACE CONSTAR"):
            reescribir_certificante(p, tipo)

        elif tiene_texto(p, "Promedio General:"):
            reescribir_promedio(p, tipo)

        elif tiene_texto(p, "OBSERVACIONES"):
            reescribir_observaciones(p)

        elif tiene_texto(p, "Se extiende el presente") or tiene_texto(
            p, "Se extiende la presente"
        ):
            reescribir_emision(p, tipo)

        elif tiene_texto(p, "validez por trescientos sesenta"):
            reescribir_vale(p)

    # Asegurar márgenes de separación entre tabla y cierre.
    if tipo == "titulo":
        marcador = buscar_parrafo_por_texto(body, "Promedio General:")

        if marcador is not None:
            vacio = parrafo_vacio()
            body.insert(list(body).index(marcador), vacio)

    doc.save(destino)

    print(f"Plantilla generada: {destino}")


def main():
    DIR_SALIDA.mkdir(exist_ok=True)

    if not ORIGEN.exists():
        raise SystemExit(f"No se encontró {ORIGEN}")

    procesar_documento("titulo")
    procesar_documento("en_tramite")


if __name__ == "__main__":
    main()
