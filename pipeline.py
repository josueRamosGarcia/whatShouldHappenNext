"""Módulo de Pipeline de Evaluación y Carga de Manifest (src/pipeline.py).

Este módulo orquesta el flujo completo de evaluación para cada caso:
obtiene el estado, aplica las reglas de negocio, intenta obtener la recomendación
de la IA (si está habilitada), aplica el validador/corrector final y emite la
estructura final con los metadatos correspondientes.
"""

import json
from src.ingest import parse_fecha
from src.state import construir_estado
from src.rules import evaluar_reglas
from src.baseline import recomendacion_base
from src.validator import validar_y_corregir
from src.recommender import recomendar  # Generado por la Persona B (stub que devuelve None al inicio)


def cargar_manifest(ruta: str = 'data/manifest.json'):
    """Carga el archivo de configuración manifest.json y extrae la fecha oficial de evaluación.

    Args:
        ruta (str): Ruta relativa o absoluta hacia el archivo manifest.json.
            Por defecto 'data/manifest.json'.

    Returns:
        datetime: Fecha y hora oficial de evaluación en UTC (evaluation_at).
    """
    with open(ruta, encoding='utf-8') as f:
        return parse_fecha(json.load(f)['evaluation_at'])


def evaluar_caso(case_id: str, store, now, usar_ia: bool = True) -> tuple[dict, dict]:
    """Evalúa un caso individual integrando estado, reglas, IA, respaldo base y validación.

    Obtiene los eventos del caso desde el Store, calcula su estado actual y determina
    las reglas vigentes. Si `usar_ia` es True, consulta el módulo de la Persona B. Si la IA
    falla o no propone una respuesta, se utiliza la decisión base. Finalmente, pasa la
    recomendación por el validador para corregir cualquier anomalía.

    Args:
        case_id (str): Identificador único del caso a evaluar.
        store (Store): Instancia del almacén con los eventos cargados.
        now (datetime): Fecha y hora de evaluación oficial (UTC).
        usar_ia (bool): Indica si se debe intentar generar una recomendación vía IA.
            Por defecto es True.

    Returns:
        tuple[dict, dict]:
            - dict: Recomendación final estandarizada (11 campos del contrato).
            - dict: Metadatos de la evaluación ('origen', 'correcciones', 'bloqueos',
              'ids_evento', 'interpretacion').
    """
    eventos = store.casos[case_id]
    estado = construir_estado(eventos)
    reglas = evaluar_reglas(estado, now)
    rec, interp, origen = None, None, 'reglas'

    if usar_ia:
        try:
            salida = recomendar(case_id, eventos, estado, reglas, now)
            if salida:
                rec, interp = salida
                origen = 'ia'
        except Exception as ex:
            store.errores.append({
                'linea': None,
                'error': 'IA fallo en case_id : ' + str(ex),
                'texto': ''
            })

    # Si la IA no produjo una respuesta válida o está desactivada, usar la decisión base
    if rec is None:
        rec = recomendacion_base(case_id, estado, reglas, now)

    # Validar y corregir la recomendación final
    rec, problemas = validar_y_corregir(rec, case_id, estado, reglas, now)
    if problemas:
        origen = 'reglas (corregida)'

    meta = {
        'origen': origen,
        'correcciones': problemas,
        'bloqueos': reglas['bloqueos'],
        'ids_evento': sorted(estado['ids']),
        'interpretacion': interp
    }

    return rec, meta


def evaluar_todo(store, now, usar_ia: bool = True, casos: list | None = None) -> dict:
    """Evalúa un conjunto de casos o la totalidad de casos presentes en el Store.

    Args:
        store (Store): Instancia del almacén con los eventos cargados.
        now (datetime): Fecha y hora de evaluación oficial (UTC).
        usar_ia (bool): Indica si se debe utilizar el componente de IA. Por defecto True.
        casos (list | None): Lista opcional de `case_id` a evaluar. Si es None, evalúa
            todos los casos presentes en el Store.

    Returns:
        dict: Mapeo de `case_id` a la tupla `(recomendacion, meta)`.
    """
    ids = casos or sorted(store.casos)
    return {c: evaluar_caso(c, store, now, usar_ia) for c in ids}