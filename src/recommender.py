"""Modulo de Recomendacion con IA (src/recommender.py).

Transforma la interpretacion del modelo en una recomendacion formal que cumple
con los 11 campos del contrato, calcula timing, scheduled_for, niveles de confianza
y niveles de riesgo basados en reglas objetivas.
"""

from src.interpreter import interpretar
from src.ingest import fmt_fecha, parse_fecha


def _timing(accion: str, reglas: dict, interp: dict, now) -> tuple[str, str | None]:
    """Calcula timing y scheduled_for segun la accion y restricciones activas."""
    if accion == 'no_action':
        return 'not_applicable', None
    if accion == 'wait':
        fechas = []
        if reglas.get('desbloqueo'):
            fechas.append(reglas['desbloqueo'])
        try:
            f = parse_fecha(interp['fecha_reevaluacion']) if interp.get('fecha_reevaluacion') else None
            if f and f > now:
                fechas.append(f)
        except Exception:
            pass
        if fechas:
            return 'at_date', fmt_fecha(max(fechas))
        return 'on_new_information', None
    return 'within_24h', None


def _confianza(estado: dict, interp: dict) -> tuple[str, str]:
    """Determina el nivel de confianza y su justificacion explicable."""
    if estado.get('cerrado'):
        return 'high', 'El cierre es definitivo y explicito.'
    if not estado.get('mensajes'):
        return 'low', 'Solo hay aperturas o ninguna senal del cliente; no demuestran intencion de compra.'
    if interp.get('intencion_cliente') == 'ambigua':
        return 'low', 'El mensaje del cliente es ambiguo.'
    if interp.get('informacion_faltante'):
        return 'medium', 'Hay mensaje claro del cliente, pero falta: ' + '; '.join(interp['informacion_faltante'])
    return 'high', 'Mensaje explicito y sin datos faltantes relevantes.'


def _riesgo(accion: str, reglas: dict, interp: dict) -> str:
    """Evalua el nivel de riesgo de la recomendacion."""
    if interp.get('intencion_cliente') == 'rechaza':
        return 'high'
    if accion == 'escalate' or (
        reglas.get('bloqueos') and interp.get('intencion_cliente') in ('interesado', 'tiene_duda', 'pide_informacion')
    ):
        return 'medium'
    return 'low'


def recomendar(case_id: str, eventos: list, estado: dict, reglas: dict, now) -> tuple[dict, dict] | None:
    """Genera la recomendacion completa estructurada a partir de la interpretacion de la IA.

    Args:
        case_id: Identificador del caso.
        eventos: Lista de eventos del caso.
        estado: Diccionario con el estado procesado.
        reglas: Diccionario con las reglas y bloqueos.
        now: Timestamp actual de evaluacion.

    Returns:
        tuple[dict, dict] | None: (recomendacion, interpretacion) o None si la IA fallo.
    """
    interp = interpretar(case_id, eventos, estado, reglas, now)
    if interp is None:
        return None

    accion = interp['accion_sugerida']
    timing, sched = _timing(accion, reglas, interp, now)

    # Recoleccion de evidencias validadas
    evid = [h['event_id'] for h in interp.get('hechos_observados', []) if 'event_id' in h]
    for i in interp.get('inferencias', []):
        evid += i.get('basada_en', [])
    evid = [e for e in dict.fromkeys(evid + reglas.get('evidencia', [])) if e in estado['ids']]

    if not evid:
        evid = [estado['mensajes'][-1]['id']] if estado.get('mensajes') else [estado.get('ultimo_id')]

    conf, conf_razon = _confianza(estado, interp)
    riesgo = _riesgo(accion, reglas, interp)
    razon = str(interp.get('razon') or 'Recomendacion basada en los eventos del caso.').strip()

    if accion == 'wait' and 'reevaluar' not in razon.lower():
        razon += ' Reevaluar ' + (sched if sched else 'cuando llegue informacion nueva') + '.'

    rec = {
        'case_id': case_id,
        'action': accion,
        'timing': timing,
        'scheduled_for': sched,
        'reason': razon,
        'evidence_event_ids': evid,
        'confidence': conf,
        'confidence_reason': conf_razon,
        'risk_level': riesgo,
        'requires_human_review': accion == 'escalate' or riesgo == 'high',
        'missing_information': list(interp.get('informacion_faltante', []))
    }
    return rec, interp
