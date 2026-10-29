import pandas as pd

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction

from academico.models import Graduado, Carrera, GraduadoCarrera


class CargaDatos:
    """
    Servicio encargado de validar e importar datos académicos
    desde un archivo Excel a la base de datos.
    """

    COLUMNAS_REQUERIDAS = [
        "legajo",
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

        # Normalizar los espacios de los encabezados.
        datos.columns = [
            str(columna).strip()
            for columna in datos.columns
        ]

        # Verificar encabezados y orden.
        if list(datos.columns) != cls.COLUMNAS_REQUERIDAS:
            raise ValueError(
                "La estructura del Excel es incorrecta. "
                "Verificá los nombres y el orden de las diez columnas."
            )

        # Ignorar filas completamente vacías.
        datos = datos.dropna(how="all")

        if datos.empty:
            raise ValueError(
                "El archivo no contiene registros para importar."
            )

        registros = []
        errores = []
        legajos_archivo = {}
        relaciones_archivo = set()

        # ==========================================
        # 1. VALIDAR TODOS LOS REGISTROS
        # ==========================================

        for indice, fila in datos.iterrows():

            numero_fila = indice + 2

            try:
                legajo = cls._texto(
                    fila["legajo"], "legajo"
                )

                dni = cls._texto(
                    fila["dni"], "dni"
                )

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
                    fila["promedio_con_aplazo"],
                    "promedio_con_aplazo"
                )

                fecha_ingreso_universidad = cls._fecha(
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

                # Comprobar coherencia cronológica.
                if fecha_ingreso_universidad > fecha_ingreso_carrera:
                    raise ValueError(
                        "El ingreso a la carrera no puede ser anterior "
                        "al ingreso a la universidad."
                    )

                if fecha_ingreso_carrera > fecha_egreso_carrera:
                    raise ValueError(
                        "El egreso de la carrera no puede ser anterior "
                        "al ingreso a la carrera."
                    )

                # No admitir dos registros para la misma carrera
                # del mismo graduado dentro del archivo.
                clave_relacion = (legajo, codigo_carrera)

                if clave_relacion in relaciones_archivo:
                    raise ValueError(
                        "El graduado tiene más de una fila para "
                        "la misma carrera en el archivo."
                    )

                relaciones_archivo.add(clave_relacion)

                # Un mismo legajo debe identificar a una persona.
                persona = {
                    "dni": dni,
                    "nombre": nombre,
                    "apellido": apellido,
                    "fecha_ingreso_universidad":
                        fecha_ingreso_universidad,
                }

                if legajo in legajos_archivo:
                    if legajos_archivo[legajo] != persona:
                        raise ValueError(
                            "El mismo legajo aparece con datos "
                            "personales diferentes."
                        )
                else:
                    legajos_archivo[legajo] = persona

                registros.append({
                    "legajo": legajo,
                    "dni": dni,
                    "nombre": nombre,
                    "apellido": apellido,
                    "fecha_ingreso_universidad":
                        fecha_ingreso_universidad,
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

            # Validar que ningún DNI pertenezca a otro legajo.
            dni_por_legajo = {
                legajo: persona["dni"]
                for legajo, persona in legajos_archivo.items()
            }

            for legajo, dni in dni_por_legajo.items():
                graduado_por_legajo = Graduado.objects.filter(
                    legajo_graduado=legajo
                ).first()

                graduado_por_dni = Graduado.objects.filter(
                    dni=dni
                ).first()

                if (
                    graduado_por_dni is not None
                    and graduado_por_dni.legajo_graduado != legajo
                ):
                    raise ValueError(
                        f"El DNI {dni} ya está asociado a otro legajo."
                    )

                if (
                    graduado_por_legajo is not None
                    and graduado_por_legajo.dni != dni
                ):
                    raise ValueError(
                        f"El legajo {legajo} ya está registrado "
                        "con otro DNI."
                    )

            # Crear o actualizar los graduados.
            for legajo, persona in legajos_archivo.items():

                graduado, creado = Graduado.objects.update_or_create(
                    legajo_graduado=legajo,
                    defaults={
                        "dni": persona["dni"],
                        "nombre": persona["nombre"],
                        "apellido": persona["apellido"],
                        "fecha_ingreso_universidad":
                            persona["fecha_ingreso_universidad"],
                    }
                )

                if creado:
                    cantidad_nuevos += 1
                else:
                    cantidad_actualizados += 1

            # Crear o actualizar las relaciones graduado-carrera.
            for registro in registros:

                graduado = Graduado.objects.get(
                    legajo_graduado=registro["legajo"]
                )

                carrera = Carrera.objects.get(
                    codigo_carrera=registro["codigo_carrera"]
                )

                _, creado = GraduadoCarrera.objects.update_or_create(
                    legajo_graduado=graduado,
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

        texto = str(valor).strip()

        if not texto:
            raise ValueError(
                f"El campo '{campo}' es obligatorio."
            )

        return texto

    @staticmethod
    def _promedio(valor, campo):
        """Valida un promedio numérico entre 0 y 10."""

        if pd.isna(valor):
            raise ValueError(
                f"El campo '{campo}' es obligatorio."
            )

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