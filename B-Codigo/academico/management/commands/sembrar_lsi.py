"""
Siembra datos de prueba para la Licenciatura en Sistemas (LSI)
a partir de un certificado Lincoln de referencia.

Uso:
    python manage.py sembrar_lsi [--archivo LincolnPrueba1.XLS]

Qué hace (idempotente, se puede re-ejecutar):

1. Crea las materias del Lincoln (código + nombre).
2. Crea el plan de estudios «LSI-2020» para la carrera LSI y
   distribuye las materias en año/cuatrimestre/orden
   (layout de prueba, ajustable luego a mano en el ABM).
3. Crea el Título «Licenciado en Sistemas» para la LSI.
4. Crea resoluciones de ejemplo (2 institucionales, 1 nacional
   y 1 instrumento) y las asocia a la carrera LSI.
"""

from pathlib import Path

import xlrd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from academico.models import (
    Carrera,
    CarreraResolucion,
    Materia,
    PlanEstudios,
    PlanEstudiosMateria,
    Resolucion,
    Titulo,
    TipoResolucion,
)


CODIGO_CARRERA = "LSI"
CODIGO_PLAN = "LSI-2020"
TITULO = "Licenciado en Sistemas"

RESOLUCIONES_EJEMPLO = [
    ("218/CS/00", TipoResolucion.INSTITUCIONAL),
    ("186/CS/06", TipoResolucion.INSTITUCIONAL),
    ("1496/99", TipoResolucion.MINISTERIAL_NACIONAL),
    ("1186/14", TipoResolucion.OTRO_INSTRUMENTO),
]


def _leer_materias(ruta):
    try:
        libro = xlrd.open_workbook(ruta, encoding_override="cp1252")
    except Exception as error:
        raise CommandError(f"No se pudo leer «{ruta}»: {error}")

    hoja = libro.sheet_by_index(0)

    if hoja.nrows < 2:
        raise CommandError("El archivo no contiene registros.")

    encabezados = [
        str(hoja.cell_value(0, c)).strip().lower()
        for c in range(hoja.ncols)
    ]

    try:
        idx_codigo = encabezados.index("materia")
        idx_nombre = encabezados.index("nombre_materia")
    except ValueError:
        raise CommandError(
            "No parece un certificado Lincoln: "
            "faltan las columnas «materia» o «nombre_materia»."
        )

    materias = {}

    for fila in range(1, hoja.nrows):
        codigo = hoja.cell_value(fila, idx_codigo)
        nombre = str(hoja.cell_value(fila, idx_nombre)).strip()

        if codigo == "" or not nombre:
            continue

        codigo_texto = str(int(float(codigo)))
        materias[codigo_texto] = " ".join(nombre.split())

    if not materias:
        raise CommandError("El archivo no contiene materias.")

    return materias


class Command(BaseCommand):
    help = "Siembra materias, plan, título y resoluciones de prueba para la LSI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--archivo",
            default="LincolnPrueba1.XLS",
            help="Certificado Lincoln de referencia.",
        )

    def handle(self, *args, **options):
        ruta = Path(options["archivo"])

        if not ruta.exists():
            raise CommandError(f"No se encontró «{ruta}».")

        with transaction.atomic():
            self._sembrar(ruta)

    def _sembrar(self, ruta):
        carrera = Carrera.objects.filter(
            codigo_carrera=CODIGO_CARRERA
        ).first()

        if carrera is None:
            raise CommandError(
                f"No existe la carrera «{CODIGO_CARRERA}»."
            )

        # 1. Materias.
        materias = _leer_materias(ruta)
        creadas = 0

        for codigo, nombre in materias.items():
            _, creada = Materia.objects.get_or_create(
                codigo_materia=codigo,
                defaults={"nombre_materia": nombre},
            )
            creadas += int(creada)

        self.stdout.write(
            f"Materias: {creadas} creadas "
            f"({len(materias)} únicas en el Lincoln)."
        )

        # 2. Plan de estudios y carga de materias al plan.
        plan, plan_creado = PlanEstudios.objects.get_or_create(
            codigo_plan=CODIGO_PLAN,
            defaults={"codigo_carrera": carrera},
        )

        self.stdout.write(
            f"Plan «{CODIGO_PLAN}»: "
            f"{'creado' if plan_creado else 'ya existe'}."
        )

        codigos = sorted(materias, key=int)

        for indice, codigo in enumerate(codigos):
            anio = min(1 + indice // 10, 5)
            cuatrimestre = "1er" if indice % 2 == 0 else "2do"
            orden = indice + 1

            PlanEstudiosMateria.objects.get_or_create(
                codigo_plan=plan,
                codigo_materia_id=codigo,
                defaults={
                    "anio_materia": anio,
                    "cuatrimestre_materia": cuatrimestre,
                    "orden_materia": orden,
                    "materia_requisito": False,
                },
            )

        self.stdout.write(
            f"Materias asociadas al plan «{CODIGO_PLAN}»."
        )

        # 3. Título.
        titulo, titulo_creado = Titulo.objects.get_or_create(
            nombre_titulo=TITULO,
            defaults={"codigo_carrera": carrera},
        )

        self.stdout.write(
            f"Título «{TITULO}»: "
            f"{'creado' if titulo_creado else 'ya existe'}."
        )

        # 4. Resoluciones de ejemplo.
        for codigo, tipo in RESOLUCIONES_EJEMPLO:
            resolucion, _ = Resolucion.objects.get_or_create(
                resolucion=codigo,
                defaults={"tipo_resolucion": tipo},
            )
            CarreraResolucion.objects.get_or_create(
                resolucion=resolucion,
                codigo_carrera=carrera,
            )

        self.stdout.write(
            f"Resoluciones de ejemplo asociadas a «{CODIGO_CARRERA}»."
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Siembra completada. Podés re-ejecutar el comando "
                "en cualquier momento."
            )
        )
