
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo


# Caracteres que Excel interpreta como inicio de fórmula.
_PREFIJOS_FORMULA = ("=", "+", "-", "@", "\t", "\r", "\n")


def _celda_segura(valor):
    """
    Evita la inyección de fórmulas en el Excel exportado.

    Los datos de nombre/apellido/carrera provienen de archivos
    externos; si empiezan con «=», «+», «-» o «@», Excel podría
    ejecutarlos como fórmula al abrir el archivo.
    """

    if not isinstance(valor, str):
        return valor

    if valor.startswith(_PREFIJOS_FORMULA):
        return "'" + valor

    return valor


def _encabezados():
    return [
        "DNI",
        "Legajo",
        "Nombre",
        "Apellido",
        "Año de ingreso a la UARG",
        "Carrera",
        "Fecha de ingreso a la carrera",
        "Fecha de egreso de la carrera",
        "Promedio sin aplazo",
        "Promedio con aplazo",
    ]


def _formatear_libro(libro, hoja):
    for celda in hoja[1]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill(
            fill_type="solid",
            fgColor="244062"
        )
        celda.alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True
        )

    # Formato de fechas y promedios (la columna 5 es un año entero)
    for fila in hoja.iter_rows(min_row=2):
        for indice in (7, 8):
            fila[indice - 1].number_format = "dd/mm/yyyy"

        for indice in (9, 10):
            fila[indice - 1].number_format = "0.00"

    # Ancho de columnas (DNI, legajo derivado, nombre, apellido, ...)
    anchos = [14, 22, 22, 22, 20, 42, 24, 24, 20, 20]

    for indice, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(indice)].width = ancho

    hoja.row_dimensions[1].height = 35
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = hoja.dimensions

    # Convertir los datos en una tabla de Excel
    if hoja.max_row >= 2:
        tabla = Table(
            displayName="TablaGraduados",
            ref=hoja.dimensions
        )

        estilo = TableStyleInfo(
            name="TableStyleMedium2",
            showFirstColumn=False,
            showLastColumn=False,
            showRowStripes=True,
            showColumnStripes=False
        )

        tabla.tableStyleInfo = estilo
        hoja.add_table(tabla)

    archivo = BytesIO()
    libro.save(archivo)

    return archivo.getvalue()


def generar_excel_filas(filas):
    """
    Exporta las filas de GRADUADO_CARRERA ya filtradas.

    Cada fila corresponde a una carrera del graduado, por lo que
    los filtros de carrera/escuela/período se respetan.
    """

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Graduados"

    hoja.append(_encabezados())

    for fila in filas.iterator(chunk_size=500):
        graduado = fila.dni_graduado

        hoja.append([
            _celda_segura(graduado.pk),
            _celda_segura(graduado.legajo or ""),
            _celda_segura(graduado.nombre),
            _celda_segura(graduado.apellido),
            graduado.anio_ingreso_universidad,
            _celda_segura(fila.codigo_carrera.nombre_carrera),
            fila.fecha_ingreso_carrera,
            fila.fecha_egreso_carrera,
            float(fila.promedio_sin_aplazo)
            if fila.promedio_sin_aplazo is not None
            else None,
            float(fila.promedio_con_aplazo)
            if fila.promedio_con_aplazo is not None
            else None,
        ])

    return _formatear_libro(libro, hoja)


def generar_excel_graduados(graduados):
    """Compatibilidad: exporta todas las carreras de los graduados."""

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Graduados"

    hoja.append(_encabezados())

    for graduado in graduados.iterator(chunk_size=500):
        carreras = graduado.carreras_cursadas.select_related(
            "codigo_carrera"
        ).all()

        for graduado_carrera in carreras:
            hoja.append([
                _celda_segura(graduado.pk),
                _celda_segura(graduado.legajo or ""),
                _celda_segura(graduado.nombre),
                _celda_segura(graduado.apellido),
                graduado.anio_ingreso_universidad,
                _celda_segura(
                    graduado_carrera.codigo_carrera.nombre_carrera
                ),
                graduado_carrera.fecha_ingreso_carrera,
                graduado_carrera.fecha_egreso_carrera,
                float(graduado_carrera.promedio_sin_aplazo)
                if graduado_carrera.promedio_sin_aplazo is not None
                else None,
                float(graduado_carrera.promedio_con_aplazo)
                if graduado_carrera.promedio_con_aplazo is not None
                else None,
            ])

    return _formatear_libro(libro, hoja)
