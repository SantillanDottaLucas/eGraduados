"""
Genera los artefactos editables que se usan antes de cargar datos reales:

  scripts/datos_reales_escuelas.csv
  scripts/datos_reales_carreras.csv
  scripts/datos_reales.sql
  scripts/planes_estudio_catalogo.csv
  scripts/plan_duplicados.csv

Los archivos se pueden editar a mano; los comandos de carga los leen
tal cual. Este script sólo los (re)genera cuando se ejecuta
explícitamente con --forzar.
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PLANES = BASE / "PlanesEstudio"
SCRIPTS = BASE / "scripts"

# Escuelas: las mismas de academico/Datos.sql.
ESCUELAS = [
    (1, "Escuela de Ingeniería y Prevención de Riesgos"),
    (2, "Escuela de Sistemas e Informática"),
    (3, "Escuela de Administración y Economía"),
    (4, "Escuela de Ciencias Básicas y Exactas"),
    (5, "Escuela de Comunicación"),
    (6, "Escuela de Enfermería"),
    (7, "Escuela de Geografía, Ordenamiento Territorial y Geoinformación"),
    (8, "Escuela de Historia"),
    (9, "Escuela de Letras"),
    (10, "Escuela de Psicopedagogía"),
    (11, "Escuela de Recursos Naturales"),
    (12, "Escuela de Trabajo Social"),
    (13, "Escuela de Turismo"),
]

# Carreras reales. Se completan las que faltaban en Datos.sql
# (074, 915) y se asigna escuela a todas las que no la tenían.
CARRERAS = [
    ("001", "Profesorado en Letras", 9),
    ("003", "Profesorado en Historia", 8),
    ("004", "Profesorado en Geografía", 7),
    ("016", "Analista de Sistemas", 2),
    ("023", "Ingeniería en Recursos Naturales", 11),
    ("045", "Licenciatura en Psicopedagogía", 10),
    ("046", "Enfermero Universitario", 6),
    ("047", "Licenciatura en Enfermería", 6),
    ("049", "Profesorado de Matemática", 4),
    ("060", "Licenciatura en Letras", 9),
    ("061", "Licenciatura en Turismo", 13),
    ("062", "Tecnicatura Universitaria en Turismo", 13),
    ("064", "Licenciatura en Geografía", 7),
    ("069", "Ingeniería Química", 1),
    ("072", "Licenciatura en Sistemas", 2),
    ("074", "Licenciatura en Trabajo Social", 12),
    ("076", "Tecnicatura Universitaria en Acompañamiento Terapéutico", 6),
    ("083", "Ciclo Complementario en Geografía", 7),
    ("085", "Ciclo Complementario en Turismo", 13),
    ("092", "Licenciatura en Gestión y Administración de Universidades", 3),
    ("093", "Licenciatura en Enfermería", 6),
    ("096", "Licenciatura en Historia", 8),
    ("912", "Tecn. Univ. en Gestión de Organizaciones", 3),
    ("913", "Licenciatura en Administración", 3),
    ("914", "Profesorado en Economía y Gestión de Organizaciones", 3),
    ("915", "Tecn. Univ. en Agronegocios y Recursos Naturales", 11),
    ("918", "Licenciatura en Comunicación Social", 5),
]

# (patrón de archivo, carrera, año, tipo, resolución, observaciones)
# El patrón usa '*' porque algunos nombres tienen caracteres dañados
# por encoding ('Geograf?a', 'Qu?mico', etc.).
PLANES_MAP = [
    ("001 - Profesorado en Letras_2006.pdf", "001", 2006, "PLAN", "", ""),
    ("003 - Profesorado en Historia_2000.pdf", "003", 2000, "PLAN", "", ""),
    ("004 - Profesorado en Geograf*a_2006.pdf", "004", 2006, "PLAN", "", ""),
    ("016 - Analista de Sistema_2012.pdf", "016", 2012, "PLAN", "", ""),
    ("016 - Analista de Sistemas_2023.pdf", "016", 2023, "PLAN", "", ""),
    ("023 - IRNR_1995.pdf", "023", 1995, "PLAN", "", ""),
    ("023 - IRNR_2001.pdf", "023", 2001, "PLAN", "", ""),
    ("023 - IRNR_2008.pdf", "023", 2008, "PLAN", "", ""),
    ("045 - Licenciatura en Psicopedagogia_2006.pdf", "045", 2006, "PLAN", "", ""),
    ("049 - Profesorado en Matem*tica_2006.pdf", "049", 2006, "PLAN", "", ""),
    ("060 - Licenciatura en Letras_2000.pdf", "060", 2000, "PLAN", "", ""),
    ("060 - Licenciatura en Letras_2006.pdf", "060", 2006, "PLAN", "", ""),
    ("061 - Licenciatura en Turismo_2005.pdf", "061", 2005, "PLAN", "", ""),
    ("062 - Tecnicatura Universitaria en Turismo_2005.pdf", "062", 2005, "PLAN", "", ""),
    ("064 - Licenciatura en Geograf*a_2006.pdf", "064", 2006, "PLAN", "", ""),
    ("069 - Ing en Quimica _2008.pdf", "069", 2008, "PLAN", "", ""),
    ("069 - Ing en Quimica_2007.pdf", "069", 2007, "PLAN", "", ""),
    ("069 - Ingenieria Quimica_2023.pdf", "069", 2023, "PLAN", "", ""),
    ("069_TECNICATURA EN ANALISIS QU*MICO_TIT INTERMEDIO_2023.pdf", "915", 2023, "PLAN", "", "Título intermedio de Ingeniería Química"),
    ("072 - Lic. en Sistemas_2023 - RCS 15923*", "072", 2023, "MODIFICATORIA", "159/23-CS-UNPA", "Modifica Anexo de Res. 086/23"),
    ("072 - Lic. en Sistemas_2023 - RCS 16023*", "072", 2023, "MODIFICATORIA", "160/23-CS-UNPA", "Modifica Anexo de Res. 087/23"),
    ("072 - Lic. en Sistemas_2023 - RCS 16323*", "072", 2023, "MODIFICATORIA", "163/23-CS-UNPA", "Tablas de homologación"),
    ("072 - Lic. en Sistemas_2023.pdf", "072", 2023, "PLAN", "", ""),
    ("072 - Licenciatura en Sistemas_2012.pdf", "072", 2012, "PLAN", "", ""),
    ("074 - Licenciatura en Trabajo Social_2007.pdf", "074", 2007, "PLAN", "", ""),
    ("076 - Tecn. Univ. en Acomp. Terapeutico_2008.pdf", "076", 2008, "PLAN", "", ""),
    ("093 - Lic. en Enfermeria y Enfermeria Univ_1998.pdf", "093", 1998, "PLAN", "", "Incluye Enfermería Universitaria (046)"),
    ("093 - Licenciatura en Enfermeria_2017.pdf", "093", 2017, "PLAN", "", ""),
    ("401 - Programa de Movilidad Estudiantil*", "401", 0, "NO_PLAN", "895-10-R", "Programa de movilidad: no es plan de estudios"),
    ("912 - TUGO-Tecn. Univ. en Gest. de Org_2001.pdf", "912", 2001, "PLAN", "", ""),
    ("913 - Licenciatura en Administraci?n con homologaci?n_2001.pdf", "913", 2001, "PLAN", "", "Versión con homologación"),
    ("913 - Licenciatura en Administraci?n_2001.pdf", "913", 2001, "PLAN", "", "Vigente: se prefiere la versión sin homologación"),
    ("914 - PREGO-Profesorado en Econ. y Gest. de Organiz_2001.pdf", "914", 2001, "PLAN", "", ""),
    ("918 - Licenciatura en Comunicacion Social_2005.pdf", "918", 2005, "PLAN", "", ""),
    ("Analista de Sistemas (016).pdf", "016", 2007, "PLAN", "", "Año estimado del PDF (2007); revisar"),
    ("Licenciatura en Geograf*a - Ciclo Complementario.pdf", "083", 1999, "PLAN", "", "Año estimado; revisar"),
    ("Licenciatura en psicopedagogia (Plan Viejo).pdf", "045", 1999, "PLAN", "", "Plan viejo, año estimado; revisar"),
    ("Licenciatura en Sistemas (072).pdf", "072", 1999, "PLAN", "", "Año estimado del PDF (1999); revisar"),
    ("Licenciatura en Turismo- ciclo complementario119-10 CS UNPA.pdf", "085", 2010, "PLAN", "119/10-CS-UNPA", ""),
    ("TUAGRIES (915).pdf", "915", 2001, "PLAN", "", "Año estimado del PDF (2001); revisar"),
    ("Analista de Sistemas.pdf", "", 0, "DUPLICADO", "", ""),
    ("Licenciatura en Sistemas.pdf", "", 0, "DUPLICADO", "", ""),
    ("TUAGRIES.pdf", "", 0, "DUPLICADO", "", ""),
]

# Duplicados exactos por hash: se conserva el que tiene código entre paréntesis.
DUPLICADOS_CONOCIDOS = {
    "Analista de Sistemas.pdf",
    "Licenciatura en Sistemas.pdf",
    "TUAGRIES.pdf",
}


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def escribir_csv(ruta: Path, campos: list[str], filas: list[dict]):
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=campos)
        escribir = escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: fila.get(c, "") for c in campos})
    print(f"Generado {ruta.relative_to(BASE)} ({len(filas)} filas)")


def generar_datos_reales():
    escribir_csv(
        SCRIPTS / "datos_reales_escuelas.csv",
        ["id_escuela", "nombre_escuela"],
        [{"id_escuela": i, "nombre_escuela": n} for i, n in ESCUELAS],
    )

    escribir_csv(
        SCRIPTS / "datos_reales_carreras.csv",
        ["codigo_carrera", "nombre_carrera", "id_escuela"],
        [
            {
                "codigo_carrera": c,
                "nombre_carrera": n,
                "id_escuela": e,
            }
            for c, n, e in CARRERAS
        ],
    )

    lineas = [
        "-- Datos reales de eGraduados.",
        "-- Generado por scripts/preparar_carga.py a partir de Datos.sql.",
        "-- Revisar antes de ejecutar. TODO: se carga con",
        "-- `python manage.py cargar_datos_reales`.",
        "",
        "INSERT INTO ESCUELA (`id_escuela`, `nombre_escuela`) VALUES",
    ]
    lineas.append(
        ",\n".join(f"({i}, '{n.replace(chr(39), chr(39)*2)}')" for i, n in ESCUELAS)
        + ";"
    )
    lineas += ["", "INSERT INTO CARRERA (`codigo_carrera`, `nombre_carrera`, `id_escuela`) VALUES"]
    lineas.append(
        ",\n".join(
            f"('{c}', '{n.replace(chr(39), chr(39)*2)}', {e})"
            for c, n, e in CARRERAS
        )
        + ";"
    )
    (SCRIPTS / "datos_reales.sql").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8"
    )
    print("Generado scripts/datos_reales.sql")


def generar_catalogo():
    archivos = sorted(PLANES.glob("*.pdf"))
    hashes = {a.name: sha256(a) for a in archivos}

    duplicados = []
    filas = []
    usados = set()

    for patron, carrera, anio, tipo, resolucion, observaciones in PLANES_MAP:
        coincidencias = [a for a in archivos if fnmatch.fnmatch(a.name, patron)]
        if len(coincidencias) != 1:
            raise SystemExit(
                f"El patrón {patron!r} coincide con {len(coincidencias)} archivos: "
                + ", ".join(a.name for a in coincidencias)
            )
        archivo = coincidencias[0]
        usados.add(archivo.name)

        if archivo.name in DUPLICADOS_CONOCIDOS:
            original = next(
                (
                    a.name
                    for a in archivos
                    if a.name not in DUPLICADOS_CONOCIDOS
                    and hashes[a.name] == hashes[archivo.name]
                ),
                "",
            )
            duplicados.append(
                {
                    "archivo": archivo.name,
                    "hash_sha256": hashes[archivo.name],
                    "conservado_como": original,
                }
            )
            continue

        sufijo = "-HOM" if "homologaci" in archivo.name.lower() else ""
        filas.append(
            {
                "codigo_plan": f"{carrera}-{anio}{sufijo}" if anio else "",
                "archivo": archivo.name,
                "archivo_real": archivo.name,
                "hash_sha256": hashes[archivo.name],
                "codigo_carrera": carrera,
                "nombre_carrera": next(
                    (n for c, n, _ in CARRERAS if c == carrera), ""
                ),
                "anio": anio,
                "tipo": tipo,
                "resolucion": resolucion,
                "vigente": "",
                "observaciones": observaciones,
            }
        )

    sin_mapear = [a.name for a in archivos if a.name not in usados]
    if sin_mapear:
        raise SystemExit("Archivos sin mapear: " + ", ".join(sin_mapear))

    # Vigente: año más alto por carrera entre los PLAN.
    # Desempate: para 913 se prefiere la versión sin "homologación".
    mejores: dict[str, tuple[int, str]] = {}
    for fila in filas:
        if fila["tipo"] != "PLAN":
            continue
        # Sin "homologación" puntaje 1 (preferido); con homologación 0.
        es_homologacion = "homologaci" in fila["archivo"].lower()
        clave = (fila["anio"], 0 if es_homologacion else 1)
        if fila["codigo_carrera"] not in mejores or clave > mejores[fila["codigo_carrera"]][0]:
            mejores[fila["codigo_carrera"]] = (clave, fila["archivo"])

    for fila in filas:
        if fila["tipo"] == "PLAN":
            fila["vigente"] = (
                "SI" if mejores.get(fila["codigo_carrera"], (None, ""))[1] == fila["archivo"] else "NO"
            )

    campos = [
        "codigo_plan",
        "archivo",
        "archivo_real",
        "hash_sha256",
        "codigo_carrera",
        "nombre_carrera",
        "anio",
        "tipo",
        "vigente",
        "resolucion",
        "observaciones",
    ]
    escribir_csv(SCRIPTS / "planes_estudio_catalogo.csv", campos, filas)
    escribir_csv(
        SCRIPTS / "plan_duplicados.csv",
        ["archivo", "hash_sha256", "conservado_como"],
        duplicados,
    )
    print(
        f"Catálogo: {len(filas)} documentos, "
        f"{sum(f['tipo'] == 'PLAN' for f in filas)} planes, "
        f"{len(duplicados)} duplicados"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Sobrescribe los archivos aunque ya existan.",
    )
    args = parser.parse_args()

    destinos = [
        SCRIPTS / "datos_reales_escuelas.csv",
        SCRIPTS / "datos_reales_carreras.csv",
        SCRIPTS / "datos_reales.sql",
        SCRIPTS / "planes_estudio_catalogo.csv",
        SCRIPTS / "plan_duplicados.csv",
    ]
    existentes = [d for d in destinos if d.exists()]
    if existentes and not args.forzar:
        raise SystemExit(
            "Ya existen artefactos. Revisalos y ejecutá con --forzar "
            "si querés regenerarlos:\n" + "\n".join(str(d) for d in existentes)
        )

    generar_datos_reales()
    generar_catalogo()


if __name__ == "__main__":
    main()
