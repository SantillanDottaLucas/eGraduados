# Planes de estudio y materias

Los planes de estudio y las materias ya están cargados en MySQL. La carga
se aplicó el **2026-11-22** desde el Excel de construcción, que reemplazó a
los datos de ejemplo y al antiguo flujo de extracción desde PDF.

## Estado actual de la base

| Tabla | Registros |
|---|---:|
| `CARRERA` | 30 |
| `PLAN_ESTUDIOS` | 28 |
| `DETALLE_PLAN_ESTUDIOS` | 28 |
| `MATERIA` | 499 |
| `PLAN_ESTUDIOS_MATERIA` | 850 |
| `EXAMEN` | 18 (sin cambios) |

`MATERIA` incluye 498 códigos del Excel más `453`
(`Idioma Moderno (Inglés)`), que no figura en el Excel pero sigue referida
por un examen y por eso se conserva. Hay 30 nombres con más de un código
real (por ejemplo `Análisis y Diseño de Software` → `1658`, `2706`), y
ningún código con más de un nombre.

Las carreras sin plan vigente son `046`, `047`, `085` y `915`.

## Archivos fuente y respaldo

- Excel de origen: `..\A-Documentacion\C-Construccion\eGraduados_Construccion_PlanesEstudio.xlsx`
  (29 hojas, 856 filas de materias).
- Respaldo de la base anterior a la carga:
  `C:\Users\Usuario\Documents\eGraduados\backups\respaldo_antes_planes_excel_2026-11-22.sql`.

**No hay script de recarga en el repositorio.** Los scripts, CSV y SQL
intermedios usados para la carga se eliminaron después de aplicarla; si
hace falta una nueva carga, se genera desde el Excel y se valida antes de
ejecutarla. El respaldo indicado arriba permite volver al estado previo.

## Modelo de datos

- `DetallePlanEstudios` (OneToOne con `PlanEstudios`): año, tipo
  (`VIGENTE`/`HISTORICO`/`MODIFICATORIA`), PDF, hash, resolución y
  observaciones.
- `Carrera.plan_vigente` (OneToOne): garantiza un único plan vigente
  por carrera en MySQL.
- La UI en **Gestión Académica → Carreras** permite cambiar el plan
  vigente; al hacerlo se actualiza también `DetallePlanEstudios.tipo`.

## Analíticos y promedios

- El orden de los exámenes y el match con el Lincoln usan el plan
  vigente de la carrera.
- **Promedio sin aplazo**: sólo aprobados (nota ≥ 6), una vez por
  materia, excluyendo las materias requisito del plan.
- **Promedio con aplazo**: todas las notas (aprobadas y reprobadas),
  incluidas las materias requisito y equivalencias con nota.
- Si el Lincoln tiene asignaturas que no coinciden con el plan, se
  muestra una **aclaración** en pantalla y hay que seleccionar la
  materia equivalente en cada fila para poder validar.
