
import csv
from io import StringIO


def generar_csv_graduados(graduados):
    archivo = StringIO()
    escritor = csv.writer(archivo)

    escritor.writerow([
        'Legajo',
        'DNI',
        'Nombre',
        'Apellido',
        'Fecha de ingreso a la universidad',
        'Promedio sin aplazo',
        'Promedio con aplazo',
    ])

    for graduado in graduados.iterator(chunk_size=500):
        nombres = ' '.join(
            graduado.nombres_asociados.values_list('nombre', flat=True)
        )

        apellidos = ' '.join(
            graduado.apellidos_asociados.values_list('apellido', flat=True)
        )

        escritor.writerow([
            graduado.legajo_graduado,
            graduado.dni_graduado,
            nombres,
            apellidos,
            graduado.fecha_ingreso_universidad,
            graduado.promedio_sin_aplazo,
            graduado.promedio_con_aplazo,
        ])

    return '\ufeff' + archivo.getvalue()
