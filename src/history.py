"""Modulo de Historial y Comparacion de Cambios (src/history.py).

Registra versiones de recomendaciones para cada caso, detectando cuando
una nueva evaluacion altera decisiones clave, calcula la diferencia ("Que cambio")
y exporta el JSON final consolidado.
"""

import json

CAMPOS = [
    'action',
    'timing',
    'scheduled_for',
    'confidence',
    'risk_level',
    'requires_human_review'
]


def registrar(hist: dict, case_id: str, rec: dict, meta: dict) -> bool:
    """Registra una nueva version en el historial si cambiaron campos relevantes.

    Args:
        hist: Diccionario del historial acumulado {case_id: [versiones]}.
        case_id: Identificador del caso.
        rec: Diccionario de la recomendacion actual.
        meta: Diccionario con metadatos de auditoria.

    Returns:
        bool: True si se agrego una nueva version; False si la decision no vario y solo se refresco.
    """
    lista = hist.setdefault(case_id, [])
    if lista and all(lista[-1]['rec'][c] == rec[c] for c in CAMPOS):
        lista[-1]['rec'], lista[-1]['meta'] = rec, meta  # Misma decision: refrescamos sin versionar
        return False

    lista.append({
        'version': len(lista) + 1,
        'rec': rec,
        'meta': meta
    })
    return True


def cambios(hist: dict, case_id: str) -> dict | None:
    """Calcula las diferencias entre las ultimas dos decisiones del caso.

    Args:
        hist: Diccionario del historial acumulado.
        case_id: Identificador del caso.

    Returns:
        dict | None: Diccionario con 'campos', 'eventos_nuevos', 'antes', 'ahora' o None si solo hay una version.
    """
    lista = hist.get(case_id, [])
    if len(lista) < 2:
        return None

    antes, ahora = lista[-2], lista[-1]
    campos_cambiados = [
        (c, antes['rec'][c], ahora['rec'][c])
        for c in CAMPOS
        if antes['rec'][c] != ahora['rec'][c]
    ]

    eventos_nuevos = sorted(set(ahora['meta']['ids_evento']) - set(antes['meta']['ids_evento']))

    return {
        'campos': campos_cambiados,
        'eventos_nuevos': eventos_nuevos,
        'antes': antes['rec'],
        'ahora': ahora['rec']
    }


def exportar_json(hist: dict) -> str:
    """Genera la representacion JSON con la ultima recomendacion vigente de cada caso ordenado.

    Args:
        hist: Diccionario del historial acumulado.

    Returns:
        str: Cadena formateada en JSON con indent=2.
    """
    recs = [hist[c][-1]['rec'] for c in sorted(hist)]
    return json.dumps(recs, ensure_ascii=False, indent=2)
