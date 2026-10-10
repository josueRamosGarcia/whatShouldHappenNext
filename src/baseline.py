"""Módulo de Decisión Base sin IA (src/baseline.py).

Este módulo implementa la lógica de respaldo (modo manual) para generar recomendaciones
estrictamente basadas en reglas de negocio y el estado del caso, sin depender de modelos
de inteligencia artificial. Sirve como mecanismo de contingencia para garantizar el
funcionamiento continuo del sistema.
"""

from src.ingest import fmt_fecha


def _rec(case_id: str, action: str, timing: str, sched: str | None,
         reason: str, ev: list, conf: str, conf_reason: str,
         riesgo: str, revision: bool, faltantes: list) -> dict:
    """Construye un diccionario de recomendación estandarizado acorde al contrato.

    Args:
        case_id (str): Identificador único del caso.
        action (str): Acción recomendada.
        timing (str): Momento de ejecución de la acción.
        sched (str | None): Fecha programada en ISO-8601 UTC si aplica.
        reason (str): Justificación en texto libre.
        ev (list): Lista de event_id que sirven como evidencia.
        conf (str): Nivel de confianza ('low', 'medium', 'high').
        conf_reason (str): Explicación del nivel de confianza.
        riesgo (str): Nivel de riesgo ('low', 'medium', 'high').
        revision (bool): Indica si requiere revisión humana obligatoria.
        faltantes (list): Lista de datos o información faltante.

    Returns:
        dict: Estructura completa de la recomendación con los 11 campos del contrato.
    """
    return {
        'case_id': case_id,
        'action': action,
        'timing': timing,
        'scheduled_for': sched,
        'reason': reason,
        'evidence_event_ids': ev,
        'confidence': conf,
        'confidence_reason': conf_reason,
        'risk_level': riesgo,
        'requires_human_review': revision,
        'missing_information': faltantes
    }


def recomendacion_base(case_id: str, estado: dict, reglas: dict, now) -> dict:
    """Genera una recomendación segura y determinista basada únicamente en estado y reglas.

    Aplica la siguiente jerarquía de decisión:
    1. Si el caso está cerrado (R1) -> `no_action`.
    2. Si hay bloqueos activos (R2, R3, R4):
       - Con fecha de desbloqueo conocida -> `wait` a la fecha (`at_date`).
       - Con mensajes del cliente -> `escalate` (revisión humana).
       - Sin fecha de desbloqueo ni mensajes -> `wait` en espera de info (`on_new_information`).
    3. Si el contacto está permitido y hay mensajes:
       - Contiene pregunta ('?' o '¿') -> `resolve_objection`.
       - Mensaje general -> `contact`.
    4. Sin mensajes o solo aperturas -> `wait` en espera de nueva información (`on_new_information`).

    Args:
        case_id (str): Identificador del caso a evaluar.
        estado (dict): Estado del caso producido por `construir_estado`.
        reglas (dict): Resultado de la evaluación de reglas producido por `evaluar_reglas`.
        now (datetime): Fecha y hora de evaluación actual (UTC).

    Returns:
        dict: Recomendación completa conforme al contrato compartido.
    """
    msgs = estado['mensajes']

    # 1. Caso cerrado
    if estado['cerrado']:
        return _rec(
            case_id, 'no_action', 'not_applicable', None,
            'Caso cerrado (' + str(estado['cierre_status']) + '). R1: solo no_action.',
            [estado['id_cierre']], 'high', 'El cierre es definitivo y explicito.',
            'low', False, []
        )

    # 2. Caso con bloqueos activos (R2, R3 o R4)
    if reglas['bloqueos']:
        motivos = ', '.join(reglas['bloqueos'].values())
        ev = ([msgs[-1]['id']] if msgs else []) + [i for i in reglas['evidencia'] if i]
        ev = list(dict.fromkeys(ev))
        falt = [] if msgs else ['Respuesta del cliente tras el ultimo contacto']

        if reglas['desbloqueo']:
            f = fmt_fecha(reglas['desbloqueo'])
            return _rec(
                case_id, 'wait', 'at_date', f,
                'Contacto bloqueado (' + motivos + '). Reevaluar el ' + f + '.',
                ev, 'high', 'La restriccion es explicita y verificable; no se conoce la intencion de compra.',
                'low', False, falt
            )

        if msgs:
            return _rec(
                case_id, 'escalate', 'within_24h', None,
                'El contacto esta prohibido (' + motivos + ') pero el cliente escribio (' + msgs[-1]['id'] + '). Se solicita revision interna de una persona responsable; no se contacta al cliente.',
                ev, 'medium', 'Restriccion explicita; la intencion del cliente es ambigua y no se puede aclarar contactandolo.',
                'medium', True, ['Motivo y vigencia de la prohibicion de contacto']
            )

        return _rec(
            case_id, 'wait', 'on_new_information', None,
            'Contacto prohibido (' + motivos + '). Reevaluar cuando se actualice la restriccion o llegue un evento nuevo.',
            ev, 'medium', 'Restriccion explicita pero sin fecha de fin.',
            'low', False, falt
        )

    # 3. Caso sin bloqueos y con mensajes del cliente
    if msgs:
        ult = msgs[-1]
        if '?' in ult['texto'] or '¿' in ult['texto']:
            return _rec(
                case_id, 'resolve_objection', 'within_24h', None,
                'El cliente hizo una pregunta (' + ult['id'] + ') y no hay bloqueos: conviene responderla.',
                [ult['id']], 'medium', 'Pregunta explicita; falta el dato interno para responder con precision.',
                'low', False, ['Dato interno necesario para responder la pregunta del cliente']
            )

        return _rec(
            case_id, 'contact', 'within_24h', None,
            'El cliente escribio (' + ult['id'] + ') y el contacto esta permitido: seguimiento breve sin afirmar intencion de compra.',
            [ult['id']], 'medium', 'Hay mensaje del cliente, pero su intencion de compra no esta confirmada.',
            'low', False, ['Intencion real de compra del cliente']
        )

    # 4. Caso sin mensajes (solo aperturas o sin señales explícitas)
    ev = [estado['aperturas'][-1]['id']] if estado['aperturas'] else [estado['ultimo_id']]
    return _rec(
        case_id, 'wait', 'on_new_information', None,
        'Solo hay aperturas o ninguna senal del cliente (R5): no justifican contacto urgente ni descuentos. Reevaluar cuando llegue un mensaje o un evento nuevo.',
        ev, 'low', 'Las aperturas no demuestran intencion de compra.',
        'low', False, ['Mensaje o respuesta del cliente que indique su intencion']
    )