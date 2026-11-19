"""
Extrae materias de los PDF de planes de estudio a un CSV revisable.

Uso:
    python scripts/extraer_materias.py [--forzar] [--max-paginas 14]
    python scripts/extraer_materias.py --solo 001 --forzar

Salida:
    scripts/materias_por_plan.csv
    scripts/extraccion_reporte.csv

La extracción es best-effort: los PDF escaneados se OCR con
RapidOCR y los que tienen texto se leen con PyMuPDF. El CSV se
puede (y debe) revisar a mano antes de cargarlo con
`python manage.py importar_planes_estudio`.

El parser es posicional: procesa los items (x, y, texto) en orden
de coordenada Y, actualizando el contexto de año/cuatrimestre a
medida que encuentra encabezados. Cada fila se arma a partir del
NOMBRE de la materia (no del número de orden), porque algunos
planes no tienen columna de orden en el primer año. A la izquierda
del nombre se buscan el número de orden y/o el código de 4 cifras;
si no hay orden se asigna uno secuencial.

Los resultados se escriben incrementalmente: si el proceso se corta,
lo ya extraído queda en el CSV. Además se paraleliza con 4 procesos.
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import re
import unicodedata
from functools import partial
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

BASE = Path(__file__).resolve().parent.parent
CATALOGO = BASE / "scripts" / "planes_estudio_catalogo.csv"
SALIDA = BASE / "scripts" / "materias_por_plan.csv"
REPORTE = BASE / "scripts" / "extraccion_reporte.csv"
CARPETA_PDF = BASE / "PlanesEstudio"

CAMPOS = [
    "codigo_plan",
    "codigo_carrera",
    "archivo",
    "anio_materia",
    "cuatrimestre_materia",
    "orden_materia",
    "nombre_materia",
    "codigo_materia_pdf",
    "materia_requisito",
    "pagina",
    "metodo",
]
CAMPOS_REPORTE = [
    "archivo",
    "codigo_plan",
    "paginas",
    "metodo",
    "materias_extraidas",
    "anios_detectados",
    "cuatrimestres_detectados",
    "observaciones",
]

ANIOS = {
    "PRIMER": 1,
    "PRIMERO": 1,
    "SEGUNDO": 2,
    "TERCER": 3,
    "TERCERO": 3,
    "CUARTO": 4,
    "QUINTO": 5,
    "SEXTO": 6,
}

RE_ANIO = re.compile(
    r"\b(PRIMER[O]?|SEGUNDO|TERCER[O]?|CUARTO|QUINTO|SEXTO|[1-6])\s*"
    r"(?:ER|DO|RO|°|º)?\s*(AÑO|ANO)\b",
    re.I,
)
RE_CUATRI = re.compile(
    r"\b(?:([12]|PRIMER[O]?|SEGUNDO)\s*(?:ER|DO|°|º)?\s*"
    r"CUATRIM|CUATRIM\s*([12]))",
    re.I,
)
RE_ANUAL = re.compile(r"\bANUAL\b", re.I)

IGNORAR = re.compile(
    r"^(UNPA|UNIVERSIDAD|FACULTAD|ESCUELA|ANEXO|RESOLUCION|RESOLUCI"
    r"N|CONTENIDOS|CARRERA|TITULO|DURACION|CANTIDAD|OBJETIVOS|"
    r"ALCANCES|PERFIL|OBSERVACIONES|PLAN\s+DE\s+ESTUDIOS|"
    r"PRIMER|SEGUNDO|TERCER|CUARTO|QUINTO|SEXTO|CUATRIMESTRE|"
    r"ANUAL|REQUISITOS|CORRELATIV|ASIGNATURAS|MATERIAS|"
    r"ORDEN|CODIGO|DEDICACION|HORAS|TOTAL|ESTRUCTURA|"
    r"ASIGNATURA|RESOLUCI[O6]N|PATAGONIA|BOLETIN|"
    r"DE\s+LA\s+PATAGONIA)\b",
    re.I,
)

# Inicio de los programas analíticos: después de acá ya no hay
# materias, sino el contenido de cada asignatura.
RE_FIN_PLANILLA = re.compile(
    r"CONTENIDOS\s+MINIM|PROGRAMA\s+ANALITIC",
    re.I,
)

CAMBIOS_OCR = (
    (re.compile(r"(?<=[A-Za-z])6(?=[A-Za-z])"), "o"),
    (re.compile(r"(?<=[A-Za-z])0(?=[A-Za-z])\b"), "o"),
    (re.compile(r"(?<=[A-Za-z])!(?=[A-Za-z])\b"), "i"),
    (re.compile(r"[|•]"), " "),
    (re.compile(r"\bANO\b"), "AÑO"),
    (re.compile(r"\s+"), " "),
)

# Un RapidOCR por proceso (evita el costo de inicializarlo por PDF).
_OCR = None


def obtener_ocr():
    global _OCR
    if _OCR is None:
        _OCR = RapidOCR()
    return _OCR


def limpiar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    for patron, reemplazo in CAMBIOS_OCR:
        texto = patron.sub(reemplazo, texto)
    return texto.strip(" |•-")


def clave(texto: str) -> str:
    return re.sub(r"[^a-z0-9]", "", limpiar(texto).lower())


def es_nombre_valido(texto: str) -> bool:
    if len(texto) < 4 or sum(c.isalpha() for c in texto) < 4:
        return False
    if IGNORAR.match(texto):
        return False
    if re.fullmatch(r"[0-9\-\s\.]+", texto):
        return False
    return True


def es_encabezado_anio(texto: str):
    m = RE_ANIO.search(limpiar(texto))
    if not m:
        return None
    valor = m.group(1).upper()
    return ANIOS.get(valor, int(valor) if valor.isdigit() else None)


def es_encabezado_cuatri(texto: str):
    limpio = limpiar(texto)
    if RE_ANUAL.search(limpio) and len(limpio) < 25:
        return "A"
    m = RE_CUATRI.search(limpio)
    if not m:
        return None
    valor = (m.group(1) or m.group(2) or "").upper()
    if valor in {"1", "PRIMER", "PRIMERO"}:
        return "1er"
    if valor in {"2", "SEGUNDO"}:
        return "2do"
    return None


def items_texto(pagina):
    items = []
    for bloque in pagina.get_text("dict").get("blocks", []):
        if bloque.get("type") != 0:
            continue
        for linea in bloque.get("lines", []):
            texto = "".join(s.get("text", "") for s in linea.get("spans", []))
            if texto.strip():
                x0, y0, _, _ = linea["bbox"]
                items.append((x0, y0, texto))
    return items


def items_ocr(pagina, ocr, escala=1.6):
    pix = pagina.get_pixmap(
        matrix=pymupdf.Matrix(escala, escala),
        colorspace=pymupdf.csRGB,
        alpha=False,
    )
    imagen = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    try:
        resultado, _ = ocr(np.array(imagen))
    except Exception:
        return []
    items = []
    factor = pagina.rect.width / pix.width
    for fila in resultado or []:
        caja, texto = fila[0], str(fila[1])
        try:
            if float(fila[2]) < 0.45:
                continue
        except (TypeError, ValueError):
            pass
        if texto.strip():
            x = min(p[0] for p in caja) * factor
            y = min(p[1] for p in caja) * factor
            items.append((x, y, texto))
    return items


def numeros_en_banda(items, y, tolerancia=6):
    """Números a la izquierda del nombre, en la misma fila."""
    return [
        (x, int(t))
        for x, yy, t in items
        if t.isdigit() and abs(yy - y) <= tolerancia
    ]


def tiene_orden(items, y, x_nombre):
    """¿Hay un número de orden (1-2 cifras) en la columna izquierda?"""
    for x, numero in numeros_en_banda(items, y):
        if numero <= 99 and x < x_nombre - 55:
            return True
    return False


def armar_fila(items, indice, consumidos):
    """
    Arma una fila de materia a partir del item ``indice`` (un nombre).

    Devuelve (nombre, orden, codigo, siguiente_indice) o None.
    """
    x0, y0, texto0 = items[indice]
    if indice in consumidos or not es_nombre_valido(texto0):
        return None

    banda = 7
    # Fragmentos del nombre en la misma línea, hasta antes de la
    # columna de horas (que es numérica y ya se descarta).
    partes = [texto0]
    consumidos.add(indice)
    for j in range(indice + 1, len(items)):
        xj, yj, tj = items[j]
        if yj > y0 + banda:
            break
        if j in consumidos or not es_nombre_valido(tj):
            continue
        if xj < x0 - 3 or xj > x0 + 220:
            continue
        partes.append(tj)
        consumidos.add(j)

    # Continuación en la línea siguiente (mismo nombre partido).
    for j in range(indice + 1, len(items)):
        xj, yj, tj = items[j]
        if yj < y0 + banda:
            continue
        # Ventana angosta: en algunos planes las materias consecutivas
        # están a ~12 px; una ventana mayor las fusiona en una sola.
        if yj > y0 + 11:
            break
        if j in consumidos or not es_nombre_valido(tj):
            continue
        if xj < x0 - 8 or xj > x0 + 220:
            continue
        if tiene_orden(items, yj, x0):
            break
        partes.append(tj)
        consumidos.add(j)

    nombre = re.sub(r"\s+", " ", " ".join(partes)).strip(" .,-")
    if not es_nombre_valido(nombre):
        return None

    # A la izquierda: orden (1-2 cifras, más lejos) y código (4 cifras).
    numeros = [
        (x, n)
        for x, n in numeros_en_banda(items, y0, banda + 2)
        if x < x0 - 8
    ]
    orden = None
    codigo = ""
    for x, n in sorted(numeros, key=lambda par: par[0]):
        if 1 <= n <= 99:
            if orden is None:
                orden = n
        elif 100 <= n <= 9999:
            codigo = str(n).zfill(4)

    return nombre, orden, codigo


def extraer_plan(ruta: Path, max_paginas: int, escala=1.6):
    documento = pymupdf.open(ruta)
    total_paginas = len(documento)
    texto_total = sum(len(p.get_text().strip()) for p in documento)
    usar_ocr = texto_total < 500
    ocr = obtener_ocr() if usar_ocr else None

    filas = []
    anio_actual = None
    cuatri_actual = None
    contador = 1
    vistas = set()

    for numero_pagina, pagina in enumerate(documento, start=1):
        if numero_pagina > max_paginas:
            break

        items = items_ocr(pagina, ocr, escala) if usar_ocr else items_texto(pagina)
        if not items:
            continue

        texto_pagina = " ".join(t for _, _, t in items)
        if RE_FIN_PLANILLA.search(texto_pagina):
            # Se terminó la planilla y empiezan los contenidos.
            break

        items = [(x, y, limpiar(t)) for x, y, t in items]
        items.sort(key=lambda it: (round(it[1] / 4), it[0]))
        consumidos = set()

        i = 0
        while i < len(items):
            x, y, texto = items[i]

            anio = es_encabezado_anio(texto)
            if anio:
                anio_actual = anio
                cuatri_actual = None
                i += 1
                continue

            cuatri = es_encabezado_cuatri(texto)
            if cuatri:
                cuatri_actual = cuatri
                i += 1
                continue

            if anio_actual and texto not in consumidos:
                fila = armar_fila(items, i, consumidos)
                if fila:
                    nombre, orden, codigo = fila
                    if orden is None:
                        orden = contador
                    else:
                        contador = max(contador, orden + 1)
                    contador = max(contador, orden + 1)

                    clave_nombre = clave(nombre)
                    if clave_nombre not in vistas:
                        vistas.add(clave_nombre)
                        filas.append({
                            "orden_materia": orden,
                            "nombre_materia": nombre,
                            "codigo_materia_pdf": codigo,
                            "anio_materia": anio_actual,
                            "cuatrimestre_materia": cuatri_actual or "",
                            "pagina": numero_pagina,
                            "metodo": "ocr" if usar_ocr else "texto",
                        })

            i += 1

    documento.close()
    return filas, usar_ocr, min(total_paginas, max_paginas)


def procesar_plan(entrada, max_paginas):
    """Worker de multiprocessing: procesa un PDF y devuelve sus filas."""
    ruta = CARPETA_PDF / entrada["archivo_real"]
    if not ruta.exists():
        return entrada, None, f"FALTA ARCHIVO: {ruta.name}"

    try:
        filas, metodo_ocr, paginas = extraer_plan(ruta, max_paginas)
    except Exception as error:  # noqa: BLE001 - best effort
        return entrada, None, f"ERROR: {type(error).__name__}: {error}"

    return entrada, (filas, metodo_ocr, paginas), None


def filas_csv(entrada, filas):
    return [
        {
            "codigo_plan": entrada["codigo_plan"],
            "codigo_carrera": entrada["codigo_carrera"],
            "archivo": entrada["archivo_real"],
            "anio_materia": fila["anio_materia"],
            "cuatrimestre_materia": fila["cuatrimestre_materia"],
            "orden_materia": fila["orden_materia"],
            "nombre_materia": fila["nombre_materia"],
            "codigo_materia_pdf": fila["codigo_materia_pdf"],
            "materia_requisito": "NO",
            "pagina": fila["pagina"],
            "metodo": fila["metodo"],
        }
        for fila in filas
    ]


def fila_reporte(entrada, filas, metodo_ocr, paginas):
    anios = sorted({f["anio_materia"] for f in filas if f["anio_materia"]})
    cuatris = sorted({f["cuatrimestre_materia"] for f in filas if f["cuatrimestre_materia"]})
    observaciones = []
    if len(filas) < 10:
        observaciones.append("REVISAR: pocas materias")
    if not anios:
        observaciones.append("sin años detectados")
    if not cuatris:
        observaciones.append("sin cuatrimestres detectados")
    return {
        "archivo": entrada["archivo_real"],
        "codigo_plan": entrada["codigo_plan"],
        "paginas": paginas,
        "metodo": "ocr" if metodo_ocr else "texto",
        "materias_extraidas": len(filas),
        "anios_detectados": ",".join(map(str, anios)),
        "cuatrimestres_detectados": ",".join(cuatris),
        "observaciones": "; ".join(observaciones),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forzar", action="store_true")
    parser.add_argument("--max-paginas", type=int, default=14)
    parser.add_argument("--solo", help="Sólo procesa PDFs cuyo nombre contenga este texto.")
    parser.add_argument("--procesos", type=int, default=4)
    args = parser.parse_args()

    if SALIDA.exists() and not args.forzar:
        raise SystemExit(f"Ya existe {SALIDA.name}. Revisala y ejecutá con --forzar.")

    with CATALOGO.open(encoding="utf-8-sig", newline="") as archivo:
        catalogo = [
            e for e in csv.DictReader(archivo)
            if e["tipo"] == "PLAN"
            and (not args.solo or args.solo.lower() in e["archivo_real"].lower())
        ]

    if not catalogo:
        raise SystemExit("No se procesaron planes.")

    archivo_salida = SALIDA.open("w", encoding="utf-8-sig", newline="")
    archivo_reporte = REPORTE.open("w", encoding="utf-8-sig", newline="")
    escritor = csv.DictWriter(archivo_salida, fieldnames=CAMPOS)
    escritor_reporte = csv.DictWriter(archivo_reporte, fieldnames=CAMPOS_REPORTE)
    escritor.writeheader()
    escritor_reporte.writeheader()

    total_filas = 0
    total_planes = 0
    tarea = partial(procesar_plan, max_paginas=args.max_paginas)

    if args.procesos > 1 and len(catalogo) > 1:
        with mp.Pool(processes=min(args.procesos, len(catalogo))) as pool:
            resultados = pool.imap_unordered(tarea, catalogo)
            for entrada, datos, error in resultados:
                if error:
                    print(f"{entrada['archivo_real']}: {error}", flush=True)
                    continue
                filas, metodo_ocr, paginas = datos
                filas_a_escribir = filas_csv(entrada, filas)
                escritor.writerows(filas_a_escribir)
                escritor_reporte.writerow(
                    fila_reporte(entrada, filas, metodo_ocr, paginas)
                )
                archivo_salida.flush()
                archivo_reporte.flush()
                total_filas += len(filas_a_escribir)
                total_planes += 1
                print(
                    f"[{total_planes}/{len(catalogo)}] {entrada['archivo_real']}: "
                    f"{len(filas)} materias ({'OCR' if metodo_ocr else 'texto'})",
                    flush=True,
                )
    else:
        for entrada in catalogo:
            _, datos, error = tarea(entrada)
            if error:
                print(f"{entrada['archivo_real']}: {error}", flush=True)
                continue
            filas, metodo_ocr, paginas = datos
            filas_a_escribir = filas_csv(entrada, filas)
            escritor.writerows(filas_a_escribir)
            escritor_reporte.writerow(fila_reporte(entrada, filas, metodo_ocr, paginas))
            archivo_salida.flush()
            archivo_reporte.flush()
            total_filas += len(filas_a_escribir)
            total_planes += 1
            print(
                f"[{total_planes}/{len(catalogo)}] {entrada['archivo_real']}: "
                f"{len(filas)} materias ({'OCR' if metodo_ocr else 'texto'})",
                flush=True,
            )

    archivo_salida.close()
    archivo_reporte.close()
    print(f"\n{SALIDA.name}: {total_filas} filas")
    print(f"{REPORTE.name}: {total_planes} planes")


if __name__ == "__main__":
    main()
