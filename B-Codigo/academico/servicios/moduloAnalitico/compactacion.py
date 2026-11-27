"""
Compactación y verificación de los documentosWord generados.

Las plantillas históricas tienen muchos párrafos vacíos y márgenes
anchos que pueden empujar el analítico a tres o más páginas. Antes
de entregarlo se compacta el resultado y, si hay un convertidor
disponible (LibreOffice), se verifica que no supere dos páginas.

Si no hay convertidor, la verificación se omite: no se bloquea la
descarga por una herramienta que puede no estar instalada.
"""

from io import BytesIO
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.shared import Cm, Pt


LIMITE_PAGINAS = 2


def _candidatos_libreoffice():
    """Rutas habituales de soffice/LibreOffice."""

    for nombre in ("soffice", "libreoffice"):
        ruta = shutil.which(nombre)

        if ruta:
            yield Path(ruta)

    yield from (
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        Path("/usr/bin/soffice"),
        Path("/usr/lib/libreoffice/program/soffice"),
        Path("/opt/libreoffice/program/soffice"),
    )


def ruta_libreoffice():
    """Devuelve el ejecutable disponible o ``None``."""

    return next(
        (ruta for ruta in _candidatos_libreoffice() if ruta.is_file()),
        None,
    )


def contar_paginas(docx_bytes):
    """
    Cuenta las páginas convirtiendo a PDF con LibreOffice.

    Devuelve ``None`` cuando no hay convertidor o la conversión
    falla: en ese caso llamador decide qué hacer (en la app,
    entregar el documento igual).
    """

    ejecutable = ruta_libreoffice()

    if ejecutable is None:
        return None

    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as temporal:
        directorio = Path(temporal)
        entrada = directorio / "analitico.docx"

        entrada.write_bytes(docx_bytes)

        try:
            subprocess.run(
                [
                    str(ejecutable),
                    "--headless",
                    "--norestore",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(directorio),
                    str(entrada),
                ],
                capture_output=True,
                check=False,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        pdf = directorio / "analitico.pdf"

        if not pdf.is_file():
            return None

        try:
            from pypdf import PdfReader

            return len(PdfReader(str(pdf)).pages)
        except Exception:
            # Último recurso: contar objetos /Type /Page del PDF.
            import re

            contenido = pdf.read_bytes()

            return len(
                re.findall(rb"/Type\s*/Page[^s]", contenido)
            ) or None


def _parrafos(documento):
    yield from documento.paragraphs

    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                yield from celda.paragraphs

    for seccion in documento.sections:
        yield from seccion.header.paragraphs
        yield from seccion.footer.paragraphs


def _colapsar_vacios(documento, conservar=1):
    """Quita párrafos vacíos consecutivos dejando a lo sumo «conservar»."""

    vacios = 0

    for parrafo in list(documento.paragraphs):
        tiene_contenido = bool(parrafo.text.strip())

        if any(
            run._element.xpath(".//w:drawing")
            for run in parrafo.runs
        ):
            tiene_contenido = True

        if tiene_contenido:
            vacios = 0
            continue

        vacios += 1

        if vacios > conservar:
            elemento = parrafo._element
            elemento.getparent().remove(elemento)


def compactar(documento, agresivo=False):
    """
    Aplica espaciado, márgenes y fuentes compactos a un ``Document``.

    Se usa al preparar las plantillas y como segunda pasada cuando
    la verificación detecta más de dos páginas.
    """

    for seccion in documento.sections:
        seccion.top_margin = Cm(1.0 if agresivo else 1.2)
        seccion.bottom_margin = Cm(1.0 if agresivo else 1.2)
        seccion.left_margin = Cm(1.0)
        seccion.right_margin = Cm(1.0)

    _colapsar_vacios(documento, conservar=0 if agresivo else 1)

    objetivo = Pt(8.5 if agresivo else 9)

    # Los estilos definen el tamaño cuando el run no lo fija: bajar
    # «Normal» compacta el cuerpo sin achatar el título.
    documento.styles["Normal"].font.size = objetivo

    for parrafo in _parrafos(documento):
        formato = parrafo.paragraph_format
        formato.space_before = Pt(0)
        formato.space_after = Pt(0)
        formato.line_spacing = 1.0

        for run in parrafo.runs:
            if run.font.size is not None and run.font.size > objetivo:
                run.font.size = objetivo


def asegurar_dos_paginas(docx_bytes, limite=LIMITE_PAGINAS):
    """
    Devuelve el documento, compactado de más si pasa de «limite».

    Sin LibreOffice no se puede medir: se devuelve tal cual (las
    plantillas ya vienen compactadas).
    """

    paginas = contar_paginas(docx_bytes)

    if paginas is None or paginas <= limite:
        return docx_bytes

    documento = Document(BytesIO(docx_bytes))
    compactar(documento, agresivo=True)

    buffer = BytesIO()
    documento.save(buffer)

    return buffer.getvalue()
