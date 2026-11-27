import pandas as pd

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction

from academico.models import Graduado, Carrera, GraduadoCarrera
from academico.servicios.validaciones import (
    anio_desde_valor,
    validar_datos_graduado,
)


class CargaDatos:
    """
    Servicio encargado de validar e importar datos académicos
    desde un archivo Excel a la base de datos.

    El DNI identifica al graduado. El legajo no se importa: se
    deriva del DNI y del año de ingreso a la UARG, que es opcional
    en esta carga (en blanco significa «sin legajo»).

    Son obligatorias DNI, nombre, apellido, ingreso y egreso de la
    carrera, código de carrera y promedio sin aplazo. El año UARG,
    el legajo y el promedio con aplazo son opcionales.
    """

    COLUMNAS_OBLIGATORIAS = [
        "dni",
        "nombre",
        "apellido",
        "promedio_sin_aplazo",
        "fecha_ingreso_carrera",
        "fecha_egreso_carrera",
        "codigo_carrera",
    ]

    COLUMNAS_OPCIONALES = [
        "promedio_con_aplazo",
        "fecha_ingreso_universidad",
        "anio_ingreso_uarg",
        "legajo",
    ]

    # Orden canónico de las planillas históricas. Se conserva para
    # generar plantillas y tests, pero la validación es por nombre.
    COLUMNAS_REQUERIDAS = [
        "dni",
        "nombre",
        "apellido",
        "promedio_sin_aplazo",
        "promedio_con_aplazo",
        "fecha_ingreso_carrera",
        "fecha_egreso_carrera",
        "codigo_carrera",
        "fecha_ingreso_universidad",
    ]

    ALIAS_COLUMNAS = {
        "anio_ingreso_uarg": "fecha_ingreso_universidad",
        "anio_uarg": "fecha_ingreso_universidad",
    }

    @classmethod
    def cargar_excel(cls, archivo):
        """
        Valida el archivo Excel e importa sus registros.

        Si existen errores, no guarda ningún registro.

        Devuelve un resumen de la importación.
        """

        extension = archivo.name.rsplit(".", 1)[-1].lower()

        if extension not in ("xlsx", "xls"):
            raise ValueError(
                "El archivo debe tener extensión .xlsx o .xls."
            )

        try:
            if extension == "xlsx":
                datos = pd.read_excel(archivo, engine="openpyxl")
            else:
                datos = pd.read_excel(archivo, engine="xlrd")

        except Exception as error:
            raise ValueError(
                "No se pudo leer el archivo Excel. "
                "Verificá que sea un archivo válido."
            ) from error

        # Normalizar los espacios de los encabezados y aceptar alias
        # del año de ingreso a la UARG.
        datos.columns = [
            cls.ALIAS_COLUMNAS.get(
                str(columna).strip().lower(),
                str(columna).strip().lower(),
            )
            for columna in datos.columns
        ]

        # El legajo no es dato de entrada: se ignora donde aparezca.
        if "legajo" in datos.columns:
            datos = datos.drop(columns=["legajo"])

        faltantes = [
            columna for columna in cls.COLUMNAS_OBLIGATORIAS
            if columna not in datos.columns
        ]

        if faltantes:
            raise ValueError(
                "Faltan columnas obligatorias en el Excel: "
                + ", ".join(faltantes)
                + ". El DNI reemplaza al legajo."
            )

        # Las columnas opcionales ausentes se toman como vacías.
        for columna in ("promedio_con_aplazo", "fecha_ingreso_universidad"):
            if columna not in datos.columns:
                datos[columna] = None

        # Ignorar filas completamente vacías.
        datos = datos.dropna(how="all")

        if datos.empty:
            raise ValueError(
                "El archivo no contiene registros para importar."
            )

        registros = []
        errores = []
        dnis_archivo = {}
        relaciones_archivo = set()

        # ==========================================
        # 1. VALIDAR TODOS LOS REGISTROS
        # ==========================================

        for indice, fila in datos.iterrows():

            numero_fila = indice + 2

            try:
                dni = cls._texto(fila["dni"], "dni")

                nombre = cls._texto(
                    fila["nombre"], "nombre"
                )

                apellido = cls._texto(
                    fila["apellido"], "apellido"
                )

                codigo_carrera = cls._texto(
                    fila["codigo_carrera"], "codigo_carrera"
                )

                promedio_sin_aplazo = cls._promedio(
                    fila["promedio_sin_aplazo"],
                    "promedio_sin_aplazo"
                )

                promedio_con_aplazo = cls._promedio(
                    fila.get("promedio_con_aplazo"),
                    "promedio_con_aplazo",
                    obligatorio=False,
                )

                # La planilla histórica trae una fecha, pero sólo
                # interesa el año. También se acepta un año suelto;
                # una celda vacía significa «sin año de ingreso».
                anio_ingreso_universidad = cls._anio_opcional(
                    fila["fecha_ingreso_universidad"],
                    "fecha_ingreso_universidad"
                )

                fecha_ingreso_carrera = cls._fecha(
                    fila["fecha_ingreso_carrera"],
                    "fecha_ingreso_carrera"
                )

                fecha_egreso_carrera = cls._fecha(
                    fila["fecha_egreso_carrera"],
                    "fecha_egreso_carrera"
                )

                # Reglas de negocio compartidas: DNI, año y
                # cronología de las fechas. El legajo se deriva acá.
                normalizados, errores_fila = validar_datos_graduado({
                    "dni": dni,
                    "anio_ingreso_universidad": (
                        anio_ingreso_universidad
                    ),
                    "anio_ingreso_carrera": (
                        fecha_ingreso_carrera.year
                        if fecha_ingreso_carrera else None
                    ),
                    "fecha_ingreso_carrera": fecha_ingreso_carrera,
                    "fecha_egreso_carrera": fecha_egreso_carrera,
                })

                if errores_fila:
                    raise ValueError(" ".join(errores_fila))

                dni = normalizados["dni"]
                anio_ingreso_universidad = (
                    normalizados["anio_ingreso_universidad"]
                )
                legajo = normalizados["legajo"]

                # No admitir dos registros para la misma carrera
                # del mismo DNI dentro del archivo.
                clave_relacion = (dni, codigo_carrera)

                if clave_relacion in relaciones_archivo:
                    raise ValueError(
                        "El graduado tiene más de una fila para "
                        "la misma carrera en el archivo."
                    )

                relaciones_archivo.add(clave_relacion)

                # Un mismo DNI debe identificar a una persona.
                persona = {
                    "dni": dni,
                    "nombre": nombre,
                    "apellido": apellido,
                    "anio_ingreso_universidad":
                        anio_ingreso_universidad,
                }

                if dni in dnis_archivo:
                    if dnis_archivo[dni] != persona:
                        raise ValueError(
                            "El mismo DNI aparece con datos "
                            "personales diferentes."
                        )
                else:
                    dnis_archivo[dni] = persona

                registros.append({
                    "dni": dni,
                    # Informativo: no se guarda como dato de entrada.
                    "legajo": legajo,
                    "nombre": nombre,
                    "apellido": apellido,
                    "anio_ingreso_universidad":
                        anio_ingreso_universidad,
                    "codigo_carrera": codigo_carrera,
                    "fecha_ingreso_carrera": fecha_ingreso_carrera,
                    "fecha_egreso_carrera": fecha_egreso_carrera,
                    "promedio_sin_aplazo": promedio_sin_aplazo,
                    "promedio_con_aplazo": promedio_con_aplazo,
                })

            except ValueError as error:
                errores.append(
                    f"Fila {numero_fila}: {error}"
                )

        if errores:
            raise ValueError(
                "Se encontraron errores en el archivo:\n"
                + "\n".join(errores[:30])
                + (
                    f"\nHay {len(errores) - 30} errores adicionales."
                    if len(errores) > 30 else ""
                )
            )

        # ==========================================
        # 2. VERIFICAR EXISTENCIA DE LAS CARRERAS
        # ==========================================

        codigos = {
            registro["codigo_carrera"]
            for registro in registros
        }

        carreras_existentes = set(
            Carrera.objects.filter(
                codigo_carrera__in=codigos
            ).values_list("codigo_carrera", flat=True)
        )

        carreras_inexistentes = codigos - carreras_existentes

        if carreras_inexistentes:
            raise ValueError(
                "No existen las siguientes carreras en la BD: "
                + ", ".join(sorted(carreras_inexistentes))
            )

        # ==========================================
        # 3. GUARDAR EN LA BASE DE DATOS
        # ==========================================

        cantidad_nuevos = 0
        cantidad_actualizados = 0
        relaciones_nuevas = 0
        relaciones_actualizadas = 0

        with transaction.atomic():

            # El DNI es la clave primaria: no puede haber dos
            # graduados con el mismo DNI. Los que ya existen se
            # actualizan; Graduado.save() recalcula el legajo.
            for dni, persona in dnis_archivo.items():

                graduado, creado = Graduado.objects.update_or_create(
                    pk=dni,
                    defaults={
                        "nombre": persona["nombre"],
                        "apellido": persona["apellido"],
                        "anio_ingreso_universidad":
                            persona["anio_ingreso_universidad"],
                    }
                )

                if creado:
                    cantidad_nuevos += 1
                else:
                    cantidad_actualizados += 1

            # Crear o actualizar las relaciones graduado-carrera.
            for registro in registros:

                graduado = Graduado.objects.get(
                    pk=registro["dni"]
                )

                carrera = Carrera.objects.get(
                    codigo_carrera=registro["codigo_carrera"]
                )

                _, creado = GraduadoCarrera.objects.update_or_create(
                    dni_graduado=graduado,
                    codigo_carrera=carrera,
                    defaults={
                        "fecha_ingreso_carrera":
                            registro["fecha_ingreso_carrera"],
                        "fecha_egreso_carrera":
                            registro["fecha_egreso_carrera"],
                        "promedio_sin_aplazo":
                            registro["promedio_sin_aplazo"],
                        "promedio_con_aplazo":
                            registro["promedio_con_aplazo"],
                    }
                )

                if creado:
                    relaciones_nuevas += 1
                else:
                    relaciones_actualizadas += 1

        return {
            "filas_procesadas": len(registros),
            "graduados_nuevos": cantidad_nuevos,
            "graduados_actualizados": cantidad_actualizados,
            "relaciones_nuevas": relaciones_nuevas,
            "relaciones_actualizadas": relaciones_actualizadas,
        }

    @staticmethod
    def _texto(valor, campo):
        """Valida un dato de texto obligatorio."""

        if pd.isna(valor):
            raise ValueError(
                f"El campo '{campo}' es obligatorio."
            )

        # Los DNI cargados como número en Excel llegan como float
        # (45000001.0): se convierten a texto sin decimales.
        if isinstance(valor, (float, Decimal)) and valor == int(valor):
            valor = int(valor)

        texto = str(valor).strip()

        if not texto:
            raise ValueError(
                f"El campo '{campo}' es obligatorio."
            )

        return texto

    @staticmethod
    def _anio_opcional(valor, campo):
        """
        Normaliza el año de ingreso a la UARG, aceptando celda vacía.

        Un año vacío se guarda como None: el graduado queda sin
        legajo derivado hasta que se informe el año.
        """

        if valor is None:
            return None

        try:
            if pd.isna(valor):
                return None
        except (TypeError, ValueError):
            pass

        if isinstance(valor, str) and not valor.strip():
            return None

        return anio_desde_valor(valor, campo)

    @staticmethod
    def _promedio(valor, campo, obligatorio=True):
        """Valida un promedio numérico entre 0 y 10."""

        if pd.isna(valor):
            if obligatorio:
                raise ValueError(
                    f"El campo '{campo}' es obligatorio."
                )
            return None

        if isinstance(valor, str) and not valor.strip():
            if obligatorio:
                raise ValueError(
                    f"El campo '{campo}' es obligatorio."
                )
            return None

        try:
            promedio = Decimal(str(valor).strip())
        except (InvalidOperation, ValueError):
            raise ValueError(
                f"El campo '{campo}' debe ser numérico."
            )

        if not promedio.is_finite() or not Decimal("0") <= promedio <= Decimal("10"):
            raise ValueError(
                f"El campo '{campo}' debe estar entre 0 y 10."
            )

        return float(promedio)

    @staticmethod
    def _fecha(valor, campo):
        """Convierte una fecha de Excel en datetime.date."""

        if pd.isna(valor):
            raise ValueError(
                f"El campo '{campo}' es obligatorio."
            )

        try:
            if isinstance(valor, (datetime, date)):
                fecha = valor.date() if isinstance(
                    valor, datetime
                ) else valor
            else:
                fecha_convertida = pd.to_datetime(
                    valor,
                    dayfirst=True,
                    errors="raise"
                )
                fecha = fecha_convertida.date()

            return fecha

        except (ValueError, TypeError, OverflowError):
            raise ValueError(
                f"El campo '{campo}' no contiene una fecha válida."
            )
